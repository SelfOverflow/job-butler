"use client";

import { useState } from "react";

import { formatTime } from "@/components/AuditLogViewer";
import type { Backup } from "@/lib/api";

export function BackupList(props: { backups: Backup[]; onRestore: (name: string) => Promise<void> }) {
  const [message, setMessage] = useState<string | null>(null);
  if (props.backups.length === 0) return <p className="text-sm text-zinc-500">No backups yet: one is made before every save.</p>;

  const newestFirst = [...props.backups].sort((a, b) => b.modified.localeCompare(a.modified));
  async function restore(name: string) {
    try {
      await props.onRestore(name);
      setMessage(`Restored ${name}. The version it replaced was backed up.`);
    } catch (error) {
      setMessage(`Restore failed: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
        {newestFirst.map((b) => (
          <li key={b.name} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
            <span className="font-mono text-xs">{b.name}</span>
            <span className="ml-auto text-xs text-zinc-500">{formatTime(b.modified)}</span>
            <button type="button" onClick={() => restore(b.name)} className="rounded-md border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800">
              Restore
            </button>
          </li>
        ))}
      </ul>
      {message && <p className="text-sm text-zinc-500">{message}</p>}
    </div>
  );
}
