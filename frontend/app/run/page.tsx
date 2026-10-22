"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { COMMAND_CATALOGUE, CommandRun } from "@/lib/commands";
import { CommandCard } from "@/components/CommandCard";
import { connectEvents } from "@/lib/websocket";

export default function CommandCenterPage() {
  const [runs, setRuns] = useState<Record<string, CommandRun>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Initial load of latest runs
    api
      .runs()
      .then((items) => {
        const byCommand: Record<string, CommandRun> = {};
        for (const item of items) {
          if (!byCommand[item.command]) {
            byCommand[item.command] = item;
          }
        }
        setRuns(byCommand);
      })
      .catch((err) => setError(err.message));

    // Connect to live WebSocket feed for progress and completion updates
    const stop = connectEvents((msg) => {
      if (msg.type === "command" && msg.run) {
        setRuns((prev) => ({
          ...prev,
          [msg.run.command]: msg.run,
        }));
      }
    });

    return () => stop();
  }, []);

  const handleLaunch = async (name: string, params: Record<string, unknown>) => {
    try {
      const res = await api.launchCommand(name, params);
      const active = await api.getRun(res.run_id);
      setRuns((prev) => ({ ...prev, [name]: active }));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : String(err));
    }
  };

  const handleCancel = async (runId: string) => {
    try {
      await api.cancelRun(runId);
      const updated = await api.getRun(runId);
      setRuns((prev) => ({ ...prev, [updated.command]: updated }));
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
