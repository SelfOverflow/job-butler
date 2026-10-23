// App-wide tailoring state: the latest `tailor_one` run per job, kept in sync from the
// runs API (on every mount, so navigating back or reloading restores progress), live
// WebSocket command events, and polling while a run is active (if the socket drops).

import { useEffect } from "react";
import { create } from "zustand";

import { api } from "@/lib/api";
import type { CommandRun } from "@/lib/commands";
import { connectEvents } from "@/lib/websocket";

const POLL_MS = 1500;

export const isActive = (run?: CommandRun): boolean => run?.status === "queued" || run?.status === "running";

type TailorState = {
  runs: Record<string, CommandRun>; // Keyed by job id.
  upsert: (run: CommandRun) => void;
  hydrate: () => Promise<void>;
  start: (jobId: string) => Promise<void>;
};

let pollTimer: ReturnType<typeof setTimeout> | undefined;
let stopEvents: (() => void) | undefined;
let subscribers = 0;

export const useTailorStore = create<TailorState>()((set, get) => ({
  runs: {},
  upsert: (run) => {
    const jobId = run.params?.job_id;
    if (run.command !== "tailor_one" || typeof jobId !== "string") return;
    const current = get().runs[jobId];
    if (current && current.id !== run.id && current.created_at > run.created_at) return;
    set((state) => ({ runs: { ...state.runs, [jobId]: run } }));
    schedulePoll();
  },
  hydrate: async () => {
    const runs = await api.runs();
    if (!Array.isArray(runs)) return;
    [...runs].reverse().forEach(get().upsert); // API is newest first; newest must win.
  },
  start: async (jobId) => {
    const { run_id } = await api.launchCommand("tailor_one", { job_id: jobId });
    const run = await api.getRun(run_id);
    get().upsert(run);
    const tracked = run.params?.job_id;
    if (typeof tracked === "string" && tracked !== jobId) {  // Single-flight: another job is running.
      throw new Error("Another resume is being tailored; try again when it finishes.");
    }
  },
}));

function schedulePoll() {
  if (pollTimer || !Object.values(useTailorStore.getState().runs).some((run) => isActive(run))) return;
  pollTimer = setTimeout(async () => {
    pollTimer = undefined;
    const active = Object.values(useTailorStore.getState().runs).filter((run) => isActive(run));
    const fresh = await Promise.all(active.map((run) => api.getRun(run.id).catch(() => run)));
    fresh.forEach(useTailorStore.getState().upsert);
  }, POLL_MS);
}

/** Subscribes to live updates while mounted and re-syncs from the server on mount. */
export function useTailorSync(): void {
  useEffect(() => {
    if (subscribers++ === 0) {
      stopEvents = connectEvents((msg) => {
        if (msg.type === "command") useTailorStore.getState().upsert(msg.run);
      });
    }
    useTailorStore.getState().hydrate().catch(() => {});
    return () => {
      if (--subscribers === 0) {
        stopEvents?.();
        stopEvents = undefined;
      }
    };
  }, []);
}

export function useTailorRun(jobId: string | null): CommandRun | undefined {
  useTailorSync();
  return useTailorStore((state) => (jobId ? state.runs[jobId] : undefined));
}

/** Test helper: clear runs, timers, and subscriptions. */
export function resetTailorStore(): void {
  clearTimeout(pollTimer);
  pollTimer = undefined;
  stopEvents?.();
  stopEvents = undefined;
  subscribers = 0;
  useTailorStore.setState({ runs: {} });
}
