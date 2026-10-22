"use client";

import { CommandProgress } from "@/lib/commands";

export function StageBars({ progress }: { progress?: CommandProgress }) {
  if (!progress || (!progress.stage && !progress.total)) {
    return null;
  }

  const done = progress.done ?? 0;
  const total = progress.total ?? 0;
  const percent = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;

  return (
    <div className="space-y-1.5 rounded-md bg-zinc-50 p-2.5 text-xs dark:bg-zinc-900" data-testid="stage-bars">
      <div className="flex items-center justify-between font-medium text-zinc-700 dark:text-zinc-300">
        <span className="capitalize">{progress.stage || "In progress"}</span>
        <span>
          {done} / {total} {total > 0 && `(${percent}%)`}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
        <div
          className="h-full bg-blue-600 transition-all duration-300 dark:bg-blue-500"
          style={{ width: `${percent}%` }}
        />
      </div>
      {progress.detail && (
        <p className="truncate text-zinc-500 dark:text-zinc-400" title={progress.detail}>
          {progress.detail}
        </p>
      )}
    </div>
  );
}
