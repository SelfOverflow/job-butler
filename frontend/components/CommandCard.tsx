"use client";

import { useState } from "react";
import { CommandDef, CommandRun } from "@/lib/commands";
import { StageBars } from "@/components/StageBars";

export function CommandCard({
  command,
  activeRun,
  onLaunch,
  onCancel,
}: {
  command: CommandDef;
  activeRun?: CommandRun;
  onLaunch: (name: string, params: Record<string, unknown>) => Promise<void>;
  onCancel: (runId: string) => Promise<void>;
}) {
  const [params, setParams] = useState<Record<string, unknown>>(command.defaultParams);
  const [submitting, setSubmitting] = useState(false);

  const isRunning = activeRun?.status === "queued" || activeRun?.status === "running";

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onLaunch(command.name, params);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col justify-between rounded-lg border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
      <div>
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">{command.label}</h3>
          {activeRun && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wider ${
                activeRun.status === "succeeded"
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400"
                  : activeRun.status === "failed"
                    ? "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-400"
                    : activeRun.status === "cancelled"
                      ? "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400"
                      : "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-400"
              }`}
            >
              {activeRun.status}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">{command.description}</p>

        <form onSubmit={handleRun} className="mt-4 space-y-3">
          {Object.entries(command.defaultParams).map(([key, defaultVal]) => (
            <div key={key} className="flex items-center gap-2">
              <label htmlFor={`${command.name}-${key}`} className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                {key}:
              </label>
              <input
                id={`${command.name}-${key}`}
                type="number"
                disabled={isRunning || submitting}
                value={String(params[key] ?? defaultVal)}
                onChange={(e) => setParams({ ...params, [key]: Number(e.target.value) })}
                className="w-24 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
              />
            </div>
          ))}

          {isRunning && activeRun?.progress && (
            <div className="pt-2">
              <StageBars progress={activeRun.progress} />
            </div>
          )}

          {activeRun?.error && (
            <p className="rounded bg-rose-50 p-2 text-xs text-rose-600 dark:bg-rose-950/50 dark:text-rose-400">
              Error: {activeRun.error}
            </p>
          )}

          <div className="flex gap-2 pt-2">
            <button
              type="submit"
              disabled={isRunning || submitting}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              {submitting ? "Launching..." : isRunning ? "Running..." : "Run"}
            </button>
            {isRunning && activeRun && (
              <button
                type="button"
                onClick={() => onCancel(activeRun.id)}
                className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
