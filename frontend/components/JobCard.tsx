"use client";

import { useState } from "react";
import Link from "next/link";
import { ExternalLink, FileText, Mail, RefreshCw, Sparkles, Trash2 } from "lucide-react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { PrepareButton } from "@/components/PrepareButton";
import { type Job } from "@/lib/api";
import { useLaunchCommandMutation, usePruneJobMutation } from "@/lib/queries";
import { isActive, useTailorRun, useTailorStore } from "@/lib/tailorStore";
import { ageLabel } from "@/lib/recency";

function scoreColour(score: number): string {
  if (score >= 80) return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300";
  if (score >= 60) return "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
  return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
}

const pill = "rounded-full px-2 py-0.5 text-xs font-medium";
const action =
  "inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2.5 py-1 text-sm hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800";

export function JobCard({ job, onPruned }: { job: Job; onPruned?: (id: string) => void }) {
  const [launching, setLaunching] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const run = useTailorRun(job.id);
  const startTailoring = useTailorStore((state) => state.start);
  const tailoring = launching || isActive(run);
  const tailored = Boolean(job.resume_url) || run?.status === "succeeded";
  const status = tailoring
    ? "tailoring"
    : run?.status === "succeeded"
      ? "tailored"
      : run?.status === "failed"
        ? "tailor_failed"
        : job.status;
  const step = isActive(run) && run?.progress.total ? ` ${run.progress.done ?? 0}/${run.progress.total}` : "";
  const [verifiedLive, setVerifiedLive] = useState(Boolean(job.last_verified_at));
  const [error, setError] = useState<string | null>(null);
  const [confirmPrune, setConfirmPrune] = useState(false);
  const [pruning, setPruning] = useState(false);

  const pruneJobMutation = usePruneJobMutation();
  const launchCommandMutation = useLaunchCommandMutation();

  const handlePrune = async () => {
    setPruning(true);
    setError(null);
    try {
      await pruneJobMutation.mutateAsync(job.id);
      setConfirmPrune(false);
      onPruned?.(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setConfirmPrune(false);
    } finally {
      setPruning(false);
    }
  };

  const handleTailor = async () => {
    setLaunching(true);
    setError(null);
    try {
      await startTailoring(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLaunching(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    setError(null);
    try {
      await launchCommandMutation.mutateAsync({ name: "scout_verify", params: { job_id: job.id } });
      setVerifiedLive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setVerifying(false);
    }
  };

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold">
            <Link href={`/jobs/detail/?id=${job.id}`} className="hover:underline">
              {job.title}
            </Link>
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            <span>{job.company}</span> · <span>{job.location}</span>
          </p>
        </div>
        <span aria-label={`Fit score ${job.score}`} className={`${pill} ${scoreColour(job.score)} text-sm`}>
          {job.score}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <JobStatusBadge status={status} />
        {job.tier_label && <span className={`${pill} bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300`}>{job.tier_label}</span>}
        <span className={`${pill} ${verifiedLive ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"}`}>
          {verifiedLive ? "Live" : "Unverified"}
        </span>
        <span className="text-zinc-500">{ageLabel(job)}</span>
        <span className="text-zinc-500">{job.source}</span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Link href={`/jobs/detail/?id=${job.id}`} className={action}>
          View Details
        </Link>

        <a href={job.url} target="_blank" rel="noopener noreferrer" className={action}>
          <ExternalLink size={14} aria-hidden /> Posting
        </a>

        {tailored || job.resume_url ? (
          <>
            <a href={job.resume_url ?? `/api/artifacts/${job.id}/resume`} className={action}>
              <FileText size={14} aria-hidden /> Resume
            </a>
            <button type="button" disabled={tailoring} onClick={handleTailor} className={action}>
              <Sparkles size={14} className={tailoring ? "animate-pulse" : ""} aria-hidden />
              {tailoring ? `Re-tailoring…${step}` : "Re-tailor"}
            </button>
          </>
        ) : (
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={tailoring}
              onClick={handleTailor}
              className={action}
            >
              <Sparkles size={14} aria-hidden />
              {tailoring ? `Tailoring…${step}` : "Tailor"}
            </button>
            <code className="rounded bg-zinc-100 px-2 py-1 text-xs dark:bg-zinc-800">
              job-butler tailor --job-id {job.id}
            </code>
          </div>
        )}

        {job.cover_letter_url && (
          <a href={job.cover_letter_url} className={action}>
            <Mail size={14} aria-hidden /> Cover letter
          </a>
        )}

        <button
          type="button"
          disabled={verifying}
          onClick={handleVerify}
          className={action}
        >
          <RefreshCw size={14} className={verifying ? "animate-spin" : ""} aria-hidden />
          {verifying ? "Verifying…" : "Re-verify"}
        </button>

        {(tailored || job.resume_url) && <PrepareButton jobId={job.id} />}

        <button type="button" onClick={() => setConfirmPrune(true)} className={action}>
          <Trash2 size={14} aria-hidden /> Prune
        </button>
      </div>

      <ConfirmDialog
        open={confirmPrune}
        title="Prune this job?"
        description={`${job.title} at ${job.company} will be removed from your jobs. Later sweeps won't bring it back.`}
        confirmLabel="Prune job"
        destructive
        busy={pruning}
        onConfirm={handlePrune}
        onCancel={() => setConfirmPrune(false)}
      />

      {error && (
        <span role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </span>
      )}
    </article>
  );
}
