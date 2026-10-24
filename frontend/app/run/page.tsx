"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { COMMAND_CATALOGUE, CommandRun } from "@/lib/commands";
import { CommandCard } from "@/components/CommandCard";
import { useCancelRunMutation, useLaunchCommandMutation, useRunsQuery } from "@/lib/queries";
import { connectEvents } from "@/lib/websocket";

export default function CommandCenterPage() {
  const { data: runItems, error: runsError } = useRunsQuery();
  const launchMutation = useLaunchCommandMutation();
  const cancelMutation = useCancelRunMutation();

  const [liveRuns, setLiveRuns] = useState<Record<string, CommandRun>>({});
  const error = runsError ? runsError.message : null;

  const runs = useMemo(() => {
    const byCommand: Record<string, CommandRun> = {};
    for (const item of runItems ?? []) {
      if (!byCommand[item.command]) {
        byCommand[item.command] = item;
      }
    }
    return { ...byCommand, ...liveRuns };
  }, [runItems, liveRuns]);

  useEffect(() => {
    // Connect to live WebSocket feed for progress and completion updates
    const stop = connectEvents((msg) => {
      if (msg.type === "command" && msg.run) {
        setLiveRuns((prev) => ({
          ...prev,
          [msg.run.command]: msg.run,
        }));
      }
    });

    return () => stop();
  }, []);

  const handleLaunch = async (name: string, params: Record<string, unknown>) => {
    try {
      const res = await launchMutation.mutateAsync({ name, params });
      const active = await api.getRun(res.run_id);
      setLiveRuns((prev) => ({ ...prev, [name]: active }));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : String(err));
    }
  };

  const handleCancel = async (runId: string) => {
    try {
      await cancelMutation.mutateAsync(runId);
      const updated = await api.getRun(runId);
      setLiveRuns((prev) => ({ ...prev, [updated.command]: updated }));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">Command Center</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Launch automated background operations with custom parameters and watch live progress bars.
        </p>
      </div>

      {error && (
        <div className="rounded-md bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/50 dark:text-rose-400">
          Failed to load runs: {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {COMMAND_CATALOGUE.map((cmd) => (
          <CommandCard
            key={cmd.name}
            command={cmd}
            activeRun={runs[cmd.name]}
            onLaunch={handleLaunch}
            onCancel={handleCancel}
          />
        ))}
      </div>
    </div>
  );
}
