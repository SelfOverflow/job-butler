"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  Mail,
  RefreshCw,
  Sparkles,
} from "lucide-react";

import { AtsReviewPanel } from "@/components/AtsReviewPanel";
import { JobDescription } from "@/components/JobDescription";
import { JobStatusBadge } from "@/components/JobStatusBadge";
import { PrepareButton } from "@/components/PrepareButton";
import { api, type JobDetail } from "@/lib/api";
import type { CommandProgress } from "@/lib/commands";
import { ageLabel } from "@/lib/recency";
import { isActive, useTailorRun, useTailorStore } from "@/lib/tailorStore";

function scoreColour(score: number): string {
  if (score >= 80) return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300";
  if (score >= 60) return "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
  return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
}

const pill = "rounded-full px-2.5 py-0.5 text-xs font-medium";
const actionBtn =
  "inline-flex items-center gap-1.5 rounded-md border border-zinc-200 px-3 py-1.5 text-sm hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800 transition";

function JobDetailContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(() => Boolean(id));
  const [error, setError] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [cacheBuster, setCacheBuster] = useState(() => Date.now());

  // Shared store: survives navigation and is re-synced from the server on mount.
  const run = useTailorRun(id);
  const startTailoring = useTailorStore((state) => state.start);
  const running = isActive(run);
  const tailoring = launching || running;
  const progress: CommandProgress | null = running && run
    ? run.progress
    : launching
      ? { detail: "Initiating tailor command…" }
      : null;
  const tailored = Boolean(job?.resume_url) || run?.status === "succeeded";

  const loadJob = useCallback((jobId: string) => {
    return api.job(jobId).then(
      (data) => {
        setJob(data);
        setError(null);
        setLoading(false);
      },
      (err: Error) => {
        setError(err.message);
        setLoading(false);
      },
    );
  }, []);

  useEffect(() => {
    if (id) loadJob(id);
  }, [id, loadJob]);

  // When a run seen in flight finishes, refresh the job and the PDF preview.
  useEffect(() => {
    if (!id) return;
    return useTailorStore.subscribe((state, previous) => {
      const now = state.runs[id];
      if (!now || isActive(now) || !isActive(previous.runs[id])) return;
      if (now.status === "succeeded") {
        setCacheBuster(Date.now());
        loadJob(id);
      } else {
        setJob((j) => j && { ...j, status: now.status === "failed" ? "tailor_failed" : j.status });
        setError(now.error ?? "Resume tailoring failed");
      }
    });
  }, [id, loadJob]);

  const handleTailor = async () => {
    if (!id) return;
    setLaunching(true);
    setError(null);
    try {
      await startTailoring(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLaunching(false);
    }
  };

  const handleVerify = async () => {
    if (!id) return;
    setVerifying(true);
    try {
      await api.launchCommand("scout_verify", { job_id: id });
      await loadJob(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setVerifying(false);
    }
  };

  if (!id) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <p className="text-zinc-600 dark:text-zinc-400">No job specified. Please select a job from the jobs board.</p>
        <Link href="/jobs/" className={actionBtn}>
          <ArrowLeft size={16} /> Back to Jobs
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-12 text-zinc-500">
        <Loader2 size={18} className="animate-spin" />
        <p>Loading job details…</p>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="flex flex-col gap-4 py-8">
        <div role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950/60 dark:text-red-300">
          Could not load job: {error}
        </div>
        <Link href="/jobs/" className={`self-start ${actionBtn}`}>
          <ArrowLeft size={16} /> Back to Jobs
        </Link>
      </div>
    );
  }

  if (!job) return null;

  const resumeUrl = job.resume_url ?? `/api/artifacts/${job.id}/resume`;
  const percent = progress?.total ? Math.round(((progress.done ?? 0) / progress.total) * 100) : 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Top Header & Breadcrumbs */}
      <header className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <Link
            href="/jobs/"
            className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition"
          >
            <ArrowLeft size={16} /> Back to Jobs
          </Link>
          <div className="flex items-center gap-2">
            <a href={job.url} target="_blank" rel="noopener noreferrer" className={actionBtn}>
              <ExternalLink size={14} /> View Posting
            </a>
            <button type="button" disabled={verifying} onClick={handleVerify} className={actionBtn}>
              <RefreshCw size={14} className={verifying ? "animate-spin" : ""} />
              {verifying ? "Verifying…" : "Re-verify"}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-200 pb-4 dark:border-zinc-800">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold tracking-tight">{job.title}</h1>
            <p className="mt-1 text-base text-zinc-600 dark:text-zinc-400">
              <span className="font-medium text-zinc-900 dark:text-zinc-100">{job.company}</span> · {job.location}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span aria-label={`Fit score ${job.score}`} className={`${pill} ${scoreColour(job.score)}`}>
                Score: {job.score}
              </span>
              <JobStatusBadge status={tailoring ? "tailoring" : job.status} />
              {job.tier_label && (
                <span className={`${pill} bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300`}>
                  {job.tier_label}
                </span>
              )}
              <span
                className={`${pill} ${job.last_verified_at ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"}`}
              >
                {job.last_verified_at ? "Live Link" : "Unverified"}
              </span>
              <span className="text-xs text-zinc-500">{ageLabel(job)}</span>
              <span className="text-xs text-zinc-500">Source: {job.source}</span>
            </div>
          </div>

          {tailored && <PrepareButton jobId={job.id} />}
        </div>
      </header>

      {error && (
        <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/60 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Split-screen: Job Description on Left, PDF Renderer on Right */}
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        {/* Left Column: Job Description */}
        <section className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
            Job Description
          </h2>
          <div className="max-h-[750px] overflow-y-auto text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            <JobDescription text={job.description} />
          </div>
        </section>

        {/* Right Column: Tailored Resume PDF Viewer */}
        <section className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold tracking-tight text-zinc-900 dark:text-zinc-100">
              Tailored Resume
            </h2>
            {tailored && (
              <div className="flex items-center gap-2">
                <a
                  href={resumeUrl}
                  download
                  className="inline-flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                >
                  <Download size={13} /> Download
                </a>
                <a
                  href={resumeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                >
                  <ExternalLink size={13} /> Open
                </a>
                <button
                  type="button"
                  disabled={tailoring}
                  onClick={handleTailor}
                  className="inline-flex items-center gap-1 rounded bg-zinc-100 px-2 py-1 text-xs font-medium hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 disabled:opacity-50 transition"
                >
                  <RefreshCw size={12} className={tailoring ? "animate-spin" : ""} />
                  {tailoring ? "Re-tailoring…" : "Re-tailor"}
                </button>
              </div>
            )}
          </div>

          {tailoring ? (
            <div className="flex min-h-[550px] flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-zinc-200 bg-zinc-50/50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-950/50">
              <Loader2 size={36} className="animate-spin text-blue-600" />
              <div className="flex w-full max-w-sm flex-col gap-2">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Tailoring Resume…</h3>
                {progress?.total ? (
                  <>
                    <p className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      Step {progress.done ?? 0} of {progress.total} ({percent}%)
                    </p>
                    <div
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={percent}
                      className="h-2 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
                    >
                      <div className="h-full rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${percent}%` }} />
                    </div>
                  </>
                ) : null}
                <p className="text-xs text-zinc-500">{progress?.detail || "Running Drafter & Reviewer loop..."}</p>
              </div>
            </div>
          ) : tailored ? (
            <div className="flex flex-col gap-3">
              <iframe
                src={`${resumeUrl}?t=${cacheBuster}#toolbar=1&navpanes=0`}
                title={`Tailored Resume for ${job.title} at ${job.company}`}
                className="h-[720px] w-full rounded-lg border border-zinc-200 bg-zinc-50 shadow-inner dark:border-zinc-800 dark:bg-zinc-950"
              />
              {job.ats_review && <AtsReviewPanel review={job.ats_review} />}
              {job.cover_letter_url && (
                <div className="flex items-center justify-between rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-800/60">
                  <span className="flex items-center gap-1.5 font-medium text-zinc-700 dark:text-zinc-300">
                    <Mail size={14} /> Tailored Cover Letter is also ready
                  </span>
                  <a
                    href={job.cover_letter_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline text-blue-600 dark:text-blue-400"
                  >
                    View Cover Letter
                  </a>
                </div>
              )}
            </div>
          ) : (
            <div className="flex min-h-[550px] flex-col items-center justify-center gap-5 rounded-lg border border-dashed border-zinc-300 bg-zinc-50/50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-950/50">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-400">
                <FileText size={28} />
              </div>
              <div className="flex max-w-sm flex-col gap-1.5">
                <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                  No Tailored Resume Yet
                </h3>
                <p className="text-xs text-zinc-500">
                  Tailor verified career facts, skills, and atomic bullets specifically for this role’s requirements.
                </p>
              </div>
              <div className="flex flex-col items-center gap-2">
                <button
                  type="button"
                  onClick={handleTailor}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition"
                >
                  <Sparkles size={16} />
                  Tailor Resume
                </button>
                <code className="text-[11px] text-zinc-500 bg-zinc-100 dark:bg-zinc-800 px-2 py-1 rounded">
                  job-butler tailor --job-id {id}
                </code>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default function JobDetailPage() {
  return (
    <Suspense fallback={<p className="text-sm text-zinc-500">Loading…</p>}>
      <JobDetailContent />
    </Suspense>
  );
}
