import { create } from "zustand";

import { api } from "@/lib/api";
import type { CommandRun } from "@/lib/commands";

export type WorkflowStep =
  | "idle"
  | "tailoring"
  | "tailoring_skipped"
  | "filling_form"
  | "awaiting_review"
  | "needs_input"
  | "blocked"
  | "failed";

export type ApplicationWorkflowState = {
  jobId: string | null;
  step: WorkflowStep;
  progressDetail: string | null;
  progressStage: string | null;
  progressDone: number;
  progressTotal: number;
  error: string | null;
  activeRunId: string | null;
  isHeaded: boolean;
  setHeaded: (headed: boolean) => void;
  startWorkflow: (job: { id: string; resume_url?: string | null; status?: string }) => Promise<void>;
  updateFromRun: (run: CommandRun) => void;
  reset: () => void;
};

const POLL_INTERVAL_MS = 250;
const MAX_POLL_ATTEMPTS = 120; // 30 seconds max wait per step in tests/dev

async function pollRunUntilComplete(runId: string): Promise<CommandRun> {
  let run = await api.getRun(runId);
  let attempts = 0;
  while (run && (run.status === "queued" || run.status === "running") && attempts < MAX_POLL_ATTEMPTS) {
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    run = await api.getRun(runId);
    attempts++;
  }
  return run;
}

export const useApplicationWorkflowStore = create<ApplicationWorkflowState>()((set, get) => ({
  jobId: null,
  step: "idle",
  progressDetail: null,
  progressStage: null,
  progressDone: 0,
  progressTotal: 0,
  error: null,
  activeRunId: null,
  isHeaded: false,

  setHeaded: (isHeaded) => set({ isHeaded }),

  reset: () =>
    set({
      jobId: null,
      step: "idle",
      progressDetail: null,
      progressStage: null,
      progressDone: 0,
      progressTotal: 0,
      error: null,
      activeRunId: null,
    }),

  updateFromRun: (run) => {
    if (run.id !== get().activeRunId) return;
    if (run.progress) {
      set({
        progressStage: run.progress.stage ?? get().progressStage,
        progressDetail: run.progress.detail ?? get().progressDetail,
        progressDone: run.progress.done ?? get().progressDone,
        progressTotal: run.progress.total ?? get().progressTotal,
      });
    }
  },

  startWorkflow: async (job) => {
    set({
      jobId: job.id,
      error: null,
      step: "idle",
    });

    const isAlreadyTailored = Boolean(job.resume_url || job.status === "tailored");

    try {
      // Phase 1: Tailoring (skip if already tailored)
      if (!isAlreadyTailored) {
        set({
          step: "tailoring",
          progressStage: "tailoring",
          progressDetail: "Initiating resume tailoring...",
          progressDone: 0,
          progressTotal: 4,
        });

        const { run_id: tailorRunId } = await api.launchCommand("tailor_one", { job_id: job.id });
        set({ activeRunId: tailorRunId });
        const finishedTailor = await pollRunUntilComplete(tailorRunId);

        if (finishedTailor.status === "failed") {
          throw new Error(finishedTailor.error ?? "Resume tailoring failed");
        }
      } else {
        set({
          step: "tailoring_skipped",
          progressDetail: "Resume already tailored. Skipping to application preparation.",
        });
      }

      // Phase 2: Playwright Form Autofill & Verification
      set({
        step: "filling_form",
        progressStage: "navigating",
        progressDetail: "Launching browser navigator...",
        progressDone: 0,
        progressTotal: 5,
      });

      const { run_id: prepRunId } = await api.launchCommand("prepare_application", {
        job_id: job.id,
        headless: !get().isHeaded,
      });
      set({ activeRunId: prepRunId });
      const finishedPrep = await pollRunUntilComplete(prepRunId);

      if (finishedPrep.status === "failed") {
        throw new Error(finishedPrep.error ?? "Application preparation failed");
      }

      // Phase 3: Refresh Application Details
      const app = await api.application(job.id);
      set({
        step: app.status as WorkflowStep,
        progressDetail: null,
        activeRunId: null,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      set({
        step: "failed",
        error: msg,
        progressDetail: null,
        activeRunId: null,
      });
    }
  },
}));
