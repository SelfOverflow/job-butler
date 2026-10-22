"use client";

import { X } from "lucide-react";
import { useState } from "react";

import type { AuditEvent } from "@/lib/api";

const STATUS_STYLE: Record<string, string> = {
  SUCCESS: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  WARNING: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  FAILURE: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};
const pill = "rounded-full px-2 py-0.5 text-xs font-medium";

export function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function formatTime(timestamp: string): string {
  return new Date(`${timestamp}Z`).toLocaleString(); // Stored as naive UTC.
}

export function ActorTag({ actor }: { actor: string }) {
  const human = actor.startsWith("human:");
  const style = human
    ? "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300"
    : "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300";
  return <span className={`${pill} ${style}`}>{actor}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`${pill} ${STATUS_STYLE[status] ?? STATUS_STYLE.WARNING}`}>{status}</span>;
}

export function AuditLogViewer({ events }: { events: AuditEvent[] }) {
  const [open, setOpen] = useState<AuditEvent | null>(null);

  if (events.length === 0) return <p className="text-sm text-zinc-500">No events match these filters.</p>;
  return (
    <>
      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-zinc-200 text-xs text-zinc-500 uppercase dark:border-zinc-800">
            <tr>
              {["Time", "Actor", "Action", "Target", "Status", "Duration"].map((h) => (
                <th key={h} className="px-3 py-2 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr
                key={event.id}
                onClick={() => setOpen(event)}
                className="cursor-pointer border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/50"
              >
                <td className="px-3 py-2 whitespace-nowrap text-zinc-500">{formatTime(event.timestamp)}</td>
                <td className="px-3 py-2"><ActorTag actor={event.actor} /></td>
                <td className="px-3 py-2 font-mono text-xs">{event.action}</td>
                <td className="px-3 py-2 font-mono text-xs text-zinc-500">{event.target_id ?? "—"}</td>
                <td className="px-3 py-2"><StatusBadge status={event.status} /></td>
                <td className="px-3 py-2 text-zinc-500">{formatDuration(event.duration_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="audit-drawer-title"
          className="fixed inset-y-0 right-0 z-10 flex w-full max-w-lg flex-col gap-3 overflow-y-auto border-l border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="flex items-center justify-between">
            <h2 id="audit-drawer-title" className="font-mono font-semibold">{open.action}</h2>
            <button type="button" aria-label="Close" onClick={() => setOpen(null)} className="rounded p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800">
              <X size={18} aria-hidden />
            </button>
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            <ActorTag actor={open.actor} /> <StatusBadge status={open.status} />
            <span className="text-zinc-500">{formatTime(open.timestamp)} · {formatDuration(open.duration_ms)}</span>
          </div>
          <pre className="overflow-x-auto rounded-md bg-zinc-100 p-3 text-xs dark:bg-zinc-950">
            {JSON.stringify(open.details, null, 2)}
          </pre>
        </div>
      )}
    </>
  );
}
