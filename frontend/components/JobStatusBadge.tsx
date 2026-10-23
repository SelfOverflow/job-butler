import { Check, Loader2 } from "lucide-react";

import type { JobStatus } from "@/lib/api";

const STYLES: Record<JobStatus, { label: string; className: string }> = {
  discovered: { label: "Discovered", className: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300" },
  tailoring: { label: "Tailoring…", className: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300" },
  tailored: { label: "Tailored", className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300" },
  tailor_failed: { label: "Tailor Failed", className: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300" },
  applied: { label: "Applied", className: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300" },
  pruned: { label: "Pruned", className: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400" },
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const { label, className } = STYLES[status] ?? STYLES.discovered;
  return (
    <span
      aria-label={`Status ${label}`}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${className}`}
    >
      {status === "tailoring" && <Loader2 size={11} className="animate-spin" aria-hidden />}
      {status === "tailored" && <Check size={11} aria-hidden />}
      {label}
    </span>
  );
}
