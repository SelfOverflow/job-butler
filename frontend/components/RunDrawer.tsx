"use client";

import { CommandRun } from "@/lib/commands";
import { X } from "lucide-react";

export function RunDrawer({
  run,
  onClose,
}: {
  run: CommandRun | null;
  onClose: () => void;
}) {
  if (!run) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs">
      <div className="flex h-full w-full max-w-md flex-col justify-between border-l border-zinc-200 bg-white p-6 shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="space-y-5 overflow-y-auto">
          <div className="flex items-center justify-between border-b border-zinc-200 pb-3 dark:border-zinc-800">
            <div>
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">{run.command}</h2>
              <p className="text-xs text-zinc-500 font-mono">{run.id}</p>
            </div>
            <button
              onClick={onClose}
              aria-label="Close drawer"
              className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800"
            >
              <X size={18} />
            </button>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between">
              <span className="text-zinc-500">Status:</span>
              <span className="font-medium uppercase">{run.status}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Requested by:</span>
              <span>{run.requested_by}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Created:</span>
              <span>{new Date(run.created_at).toLocaleString()}</span>
            </div>
            {run.started_at && (
              <div className="flex justify-between">
                <span className="text-zinc-500">Started:</span>
                <span>{new Date(run.started_at).toLocaleString()}</span>
              </div>
            )}
            {run.finished_at && (
              <div className="flex justify-between">
                <span className="text-zinc-500">Finished:</span>
                <span>{new Date(run.finished_at).toLocaleString()}</span>
              </div>
            )}
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold text-zinc-700 dark:text-zinc-300">Parameters</h3>
            <pre className="overflow-x-auto rounded-md bg-zinc-100 p-3 text-xs font-mono dark:bg-zinc-900">
              {JSON.stringify(run.params, null, 2)}
            </pre>
          </div>

          {run.result && (
            <div>
              <h3 className="mb-1 text-xs font-semibold text-zinc-700 dark:text-zinc-300">Result</h3>
              <pre className="overflow-x-auto rounded-md bg-zinc-100 p-3 text-xs font-mono dark:bg-zinc-900">
                {JSON.stringify(run.result, null, 2)}
              </pre>
            </div>
          )}

          {run.error && (
            <div>
              <h3 className="mb-1 text-xs font-semibold text-rose-600 dark:text-rose-400">Error</h3>
              <p className="rounded-md bg-rose-50 p-3 text-xs text-rose-700 dark:bg-rose-950/50 dark:text-rose-400 font-mono">
                {run.error}
              </p>
            </div>
          )}
        </div>

        <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800">
          <button
            onClick={onClose}
            className="w-full rounded-md bg-zinc-900 py-2 text-xs font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
