"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CommandRun } from "@/lib/commands";
import { RunDrawer } from "@/components/RunDrawer";

export default function RunsHistoryPage() {
  const [runs, setRuns] = useState<CommandRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<CommandRun | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .runs()
      .then(setRuns)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">Run History</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Audit history of background operations, parameters, execution times, and results.
          </p>
        </div>
      </div>

      {loading ? (
        <p className="text-xs text-zinc-500">Loading runs...</p>
      ) : runs.length === 0 ? (
        <p className="text-xs text-zinc-500">No runs recorded yet.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              <tr>
                <th className="px-4 py-3 font-medium">Command</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Requested By</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {runs.map((run) => (
                <tr key={run.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-900/50">
                  <td className="px-4 py-3 font-medium text-zinc-900 dark:text-zinc-100">{run.command}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-2xs font-medium uppercase tracking-wider ${
                        run.status === "succeeded"
                          ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400"
                          : run.status === "failed"
                            ? "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-400"
                            : run.status === "cancelled"
                              ? "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400"
                              : "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-400"
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">{run.requested_by}</td>
                  <td className="px-4 py-3 text-zinc-500">{new Date(run.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setSelectedRun(run)}
                      className="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
                    >
                      Inspect
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <RunDrawer run={selectedRun} onClose={() => setSelectedRun(null)} />
    </div>
  );
}
