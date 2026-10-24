"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import React, { Suspense, useEffect, useState } from "react";
import { AlertCircle, ArrowLeft, ExternalLink, Filter, Loader2, RotateCcw, Sparkles, Square } from "lucide-react";

import { ApplicationDetailView } from "@/components/ApplicationDetailView";
import { ApplicationProcessStepper } from "@/components/ApplicationProcessStepper";
import { LiveExecutionFeed } from "@/components/LiveExecutionFeed";
import type { Application } from "@/lib/api";
import { useApplicationWorkflowStore } from "@/lib/applicationWorkflowStore";
import { useApplicationQuery, useApplicationsQuery, useJobQuery } from "@/lib/queries";

const STATUS_BADGE: Record<string, string> = {
  in_progress: "bg-sky-100 text-sky-800 dark:bg-sky-950/60 dark:text-sky-300 animate-pulse",
  awaiting_review: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
  needs_input: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  blocked: "bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300",
  submitted: "bg-sky-100 text-sky-800 dark:bg-sky-950/60 dark:text-sky-300",
  applied_manually: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300",
  skipped: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
  failed: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300",
};

const STATUS_LABEL: Record<string, string> = {
  in_progress: "In Progress",
  awaiting_review: "Ready for Review",
  needs_input: "Needs Input",
  blocked: "Blocked",
  submitted: "Submitted",
  applied_manually: "Applied Manually",
  skipped: "Skipped",
  failed: "Failed",
};

function ApplicationProcessContent() {
  const searchParams = useSearchParams();
  const jobId = searchParams.get("jobId");
  const auto = searchParams.get("auto") === "true";

  const workflow = useApplicationWorkflowStore();

  const { data: job, isLoading: jobLoading } = useJobQuery(jobId ?? "");
  const { data: app, refetch: refetchApp } = useApplicationQuery(jobId ?? "");
  const { data: allApps = [], isLoading: appsLoading } = useApplicationsQuery();

  const ongoingJobId =
    workflow.step === "tailoring" || workflow.step === "filling_form"
      ? workflow.jobId
      : null;
  const { data: ongoingJob } = useJobQuery(ongoingJobId ?? "");

  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    workflow.hydrate().catch(() => {});
  }, [workflow]);

  useEffect(() => {
    if (job && auto && workflow.jobId !== job.id && workflow.step === "idle") {
      workflow.startWorkflow(job);
    }
  }, [job, auto, workflow]);

  const isOngoingForThisJob =
    Boolean(jobId) &&
    (workflow.step === "tailoring" || workflow.step === "filling_form") &&
    workflow.jobId === jobId;

  if (jobId) {
    if (jobLoading && !job) {
      return (
        <div className="flex h-64 items-center justify-center text-sm text-zinc-500 gap-2">
          <Loader2 className="animate-spin" size={18} /> Loading application context…
        </div>
      );
    }

    return (
      <div className="flex flex-col gap-5">
        <header className="flex items-center justify-between border-b border-zinc-200 pb-4 dark:border-zinc-800">
          <Link
            href="/applications/"
            className="inline-flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition"
          >
            <ArrowLeft size={14} /> All Applications
          </Link>
          {job && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-zinc-500">{job.company}</span>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                <ExternalLink size={12} /> View Posting
              </a>
            </div>
          )}
        </header>

        {isOngoingForThisJob ? (
          <div className="flex flex-col gap-5">
            {job && (
              <div className="flex flex-col gap-2 rounded-xl border border-sky-200 bg-sky-50/50 p-5 shadow-sm dark:border-sky-900/60 dark:bg-sky-950/30">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-bold tracking-tight">{job.title}</h2>
                    <p className="text-sm text-zinc-600 dark:text-zinc-400">
                      <span className="font-medium text-zinc-900 dark:text-zinc-100">{job.company}</span> · {job.location}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-800 dark:bg-sky-900/60 dark:text-sky-300 animate-pulse">
                      <span className="h-2 w-2 rounded-full bg-sky-500"></span>
                      {workflow.step === "tailoring" ? "Tailoring Resume" : "Autofilling Form"}
                    </span>
                    <button
                      type="button"
                      onClick={() => workflow.stopWorkflow()}
                      className="inline-flex items-center gap-1.5 rounded-md border border-red-300 bg-white px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:border-red-900/60 dark:bg-zinc-900 dark:text-red-400 dark:hover:bg-red-950/50 transition"
                    >
                      <Square size={12} className="fill-current" />
                      {workflow.step === "tailoring" ? "Stop Tailoring" : "Stop Process"}
                    </button>
                  </div>
                </div>
              </div>
            )}
            <ApplicationProcessStepper step={workflow.step} failedStep={workflow.failedStep} progressDetail={workflow.progressDetail} />
            <LiveExecutionFeed />
          </div>
        ) : workflow.step === "failed" ? (
          <div className="flex flex-col gap-5">
            {job && (
              <div className="flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-bold tracking-tight">{job.title}</h2>
                    <p className="text-sm text-zinc-600 dark:text-zinc-400">
                      <span className="font-medium text-zinc-900 dark:text-zinc-100">{job.company}</span> · {job.location}
                    </p>
                  </div>
                  <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-800 dark:bg-red-950 dark:text-red-300">
                    Failed
                  </span>
                </div>
              </div>
            )}
            <ApplicationProcessStepper step={workflow.step} failedStep={workflow.failedStep} progressDetail={workflow.progressDetail} />

            {workflow.error && (
              <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
                <AlertCircle className="mt-0.5 shrink-0 text-red-600 dark:text-red-400" size={18} />
                <div className="flex flex-col gap-1.5 flex-1">
                  <p className="font-semibold">Process Failed During {workflow.failedStep === "tailoring" ? "Resume Tailoring" : "Form Autofill"}</p>
                  <p className="text-xs leading-relaxed">{workflow.error}</p>
                  {job && (
                    <div className="pt-2">
                      <button
                        type="button"
                        onClick={() => workflow.startWorkflow(job)}
                        className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 transition"
                      >
                        <RotateCcw size={12} /> Retry Application Process
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
            <LiveExecutionFeed />
          </div>
        ) : app ? (
          <ApplicationDetailView app={app} onRefresh={refetchApp} />
        ) : (
          <div className="flex flex-col gap-4">
            <ApplicationProcessStepper step={workflow.step} failedStep={workflow.failedStep} progressDetail={workflow.progressDetail} />
            <LiveExecutionFeed />
          </div>
        )}
      </div>
    );
  }

  // Synthesize ongoing application into listing if active
  const ongoingApp: Application | null = ongoingJob
    ? {
        job_id: ongoingJob.id,
        title: ongoingJob.title,
        company: ongoingJob.company,
        url: ongoingJob.url,
        status: "in_progress" as unknown as Application["status"],
        barrier: null,
        plan: [],
        questions: [],
        answers: {},
        error: workflow.error,
        screenshot_url: null,
        updated_at: new Date().toISOString(),
        submitted_at: null,
      }
    : null;

  const combinedApps = ongoingApp
    ? [ongoingApp, ...allApps.filter((a) => a.job_id !== ongoingApp.job_id)]
    : allApps;

  const filteredApps = combinedApps.filter((a) => {
    if (filter === "all") return true;
    if (filter === "in_progress") return a.status === ("in_progress" as unknown);
    return a.status === filter;
  });

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">Application Process</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Autonomous direct application pipeline with Playwright form autofill and verification mode.
        </p>
      </header>

      {/* Prominent Ongoing Application Card */}
      {ongoingJob && (
        <section aria-label="Ongoing application" className="flex flex-col gap-3 rounded-xl border border-sky-300 bg-sky-50/70 p-4 shadow-sm dark:border-sky-800 dark:bg-sky-950/40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75"></span>
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500"></span>
              </span>
              <h2 className="text-sm font-semibold text-sky-950 dark:text-sky-200">
                Ongoing Application Process
              </h2>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => workflow.stopWorkflow()}
                className="inline-flex items-center gap-1 text-xs font-medium text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 hover:underline"
              >
                <Square size={11} className="fill-current" />
                {workflow.step === "tailoring" ? "Stop Tailoring" : "Stop Process"}
              </button>
              <Link
                href={`/applications/?jobId=${ongoingJob.id}`}
                className="inline-flex items-center gap-1 text-xs font-semibold text-sky-700 hover:text-sky-900 dark:text-sky-300 dark:hover:text-sky-100 hover:underline"
              >
                View Live Execution &rarr;
              </Link>
            </div>
          </div>

          <Link
            href={`/applications/?jobId=${ongoingJob.id}`}
            className="group flex flex-col gap-2 rounded-lg border border-sky-200 bg-white p-3.5 transition hover:border-sky-400 dark:border-sky-900/60 dark:bg-zinc-900"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold text-sm group-hover:text-sky-600 dark:group-hover:text-sky-400 transition">
                  {ongoingJob.title}
                </h3>
                <p className="text-xs text-zinc-500">{ongoingJob.company} · {ongoingJob.location}</p>
              </div>
              <span className="rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-medium text-sky-800 dark:bg-sky-900/60 dark:text-sky-300">
                {workflow.step === "tailoring" ? "Tailoring Resume" : "Autofilling Form"}
              </span>
            </div>

            {workflow.progressDetail && (
              <p className="text-xs text-zinc-600 dark:text-zinc-400 font-mono truncate">
                › {workflow.progressDetail}
              </p>
            )}

            {workflow.progressTotal > 0 && (
              <div className="w-full bg-zinc-100 rounded-full h-1.5 dark:bg-zinc-800 overflow-hidden">
                <div
                  className="bg-sky-500 h-1.5 rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.min(100, Math.round((workflow.progressDone / workflow.progressTotal) * 100))}%`,
                  }}
                />
              </div>
            )}
          </Link>
        </section>
      )}

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 pb-3 dark:border-zinc-800">
        <span className="inline-flex items-center gap-1 text-xs text-zinc-400 mr-2">
          <Filter size={12} /> Status:
        </span>
        {["all", "in_progress", "awaiting_review", "needs_input", "blocked", "submitted"].map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setFilter(tab)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
              filter === tab
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
            }`}
          >
            {tab === "all" ? "All Applications" : (STATUS_LABEL[tab] ?? tab)}
          </button>
        ))}
      </div>

      {appsLoading ? (
        <div className="flex h-48 items-center justify-center text-sm text-zinc-500 gap-2">
          <Loader2 className="animate-spin" size={16} /> Loading applications…
        </div>
      ) : filteredApps.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-200 p-12 text-center dark:border-zinc-800">
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">No applications found</p>
          <p className="mt-1 text-xs text-zinc-500">
            Click &ldquo;Apply&rdquo; on any job card or detail page to start the automated process.
          </p>
          <Link
            href="/jobs/"
            className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          >
            <Sparkles size={13} /> Browse Jobs
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {filteredApps.map((a) => {
            const isItemOngoing = a.status === ("in_progress" as unknown);
            return (
              <article
                key={a.job_id}
                className={`flex flex-col justify-between gap-3 rounded-xl border p-4 shadow-sm transition ${
                  isItemOngoing
                    ? "border-sky-300 bg-sky-50/30 dark:border-sky-800 dark:bg-sky-950/20"
                    : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-semibold text-sm">
                      <Link href={`/applications/?jobId=${a.job_id}`} className="hover:underline">
                        {a.title}
                      </Link>
                    </h3>
                    <p className="text-xs text-zinc-500">{a.company}</p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                      STATUS_BADGE[a.status] ?? "bg-zinc-100"
                    }`}
                  >
                    {STATUS_LABEL[a.status] ?? a.status}
                  </span>
                </div>

                {isItemOngoing && workflow.progressDetail ? (
                  <p className="text-xs text-zinc-600 dark:text-zinc-400 font-mono truncate">
                    › {workflow.progressDetail}
                  </p>
                ) : null}

                <div className="flex items-center justify-between border-t border-zinc-100 pt-2 text-xs text-zinc-500 dark:border-zinc-800">
                  <span>{isItemOngoing ? "Autofilling form…" : `${a.plan.length} fields planned`}</span>
                  <Link
                    href={`/applications/?jobId=${a.job_id}`}
                    className="font-medium text-zinc-700 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-zinc-100 hover:underline"
                  >
                    {isItemOngoing ? "View Live Execution \u2192" : "Inspect \u2192"}
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ApplicationsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-64 items-center justify-center text-sm text-zinc-500 gap-2">
          <Loader2 className="animate-spin" size={18} /> Loading…
        </div>
      }
    >
      <ApplicationProcessContent />
    </Suspense>
  );
}
