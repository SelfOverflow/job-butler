import { ExternalLink, FileText, Mail } from "lucide-react";

import type { Job } from "@/lib/api";

function scoreColour(score: number): string {
  if (score >= 80) return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300";
  if (score >= 60) return "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
  return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
}

const pill = "rounded-full px-2 py-0.5 text-xs font-medium";
const action =
  "inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2.5 py-1 text-sm hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800";

export function JobCard({ job }: { job: Job }) {
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold">{job.title}</h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            <span>{job.company}</span> · <span>{job.location}</span>
          </p>
        </div>
        <span aria-label={`Fit score ${job.score}`} className={`${pill} ${scoreColour(job.score)} text-sm`}>
          {job.score}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        {job.tier_label && <span className={`${pill} bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300`}>{job.tier_label}</span>}
        <span className={`${pill} ${job.last_verified_at ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"}`}>
          {job.last_verified_at ? "Live" : "Unverified"}
        </span>
        <span className="text-zinc-500">{job.source}</span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <a href={job.url} target="_blank" rel="noopener noreferrer" className={action}>
          <ExternalLink size={14} aria-hidden /> Posting
        </a>
        {job.resume_url ? (
          <a href={job.resume_url} className={action}>
            <FileText size={14} aria-hidden /> Resume
          </a>
        ) : (
          <code className="rounded bg-zinc-100 px-2 py-1 text-xs dark:bg-zinc-800">
            job-butler tailor --job-id {job.id}
          </code>
        )}
        {job.cover_letter_url && (
          <a href={job.cover_letter_url} className={action}>
            <Mail size={14} aria-hidden /> Cover letter
          </a>
        )}
      </div>
    </article>
  );
}
