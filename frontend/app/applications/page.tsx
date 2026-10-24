"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import React, { Suspense, useEffect, useState } from "react";
import { ArrowLeft, ExternalLink, Filter, Loader2, Sparkles } from "lucide-react";

import { ApplicationDetailView } from "@/components/ApplicationDetailView";
import { ApplicationProcessStepper } from "@/components/ApplicationProcessStepper";
import { LiveExecutionFeed } from "@/components/LiveExecutionFeed";
import type { Application } from "@/lib/api";
import { useApplicationWorkflowStore } from "@/lib/applicationWorkflowStore";
import { useApplicationQuery, useApplicationsQuery, useJobQuery } from "@/lib/queries";

const STATUS_BADGE: Record<string, string> = {
  awaiting_review: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
  needs_input: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  blocked: "bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300",
  submitted: "bg-sky-100 text-sky-800 dark:bg-sky-950/60 dark:text-sky-300",
  applied_manually: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300",
  skipped: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
  failed: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300",
};

const STATUS_LABEL: Record<string, string> = {
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

  const { data: job, isLoading: jobLoading } = useJobQuery(jobId ?? "");
  const { data: app, refetch: refetchApp } = useApplicationQuery(jobId ?? "");
  const { data: allApps = [], isLoading: appsLoading } = useApplicationsQuery();

  const workflow = useApplicationWorkflowStore();
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    if (job && auto && workflow.jobId !== job.id && workflow.step === "idle") {
      workflow.startWorkflow(job);
    }
  }, [job, auto, workflow]);

  const activeApp: Application | null = app ?? (job ? {
    job_id: job.id,
    title: job.title,
    company: job.company,
    url: job.url,
    status: (workflow.step === "filling_form" || workflow.step === "tailoring" ? "awaiting_review" : (workflow.step as Application["status"])),
    barrier: null,
    plan: [],
    questions: [],
    answers: {},
    error: workflow.error,
    screenshot_url: null,
    updated_at: new Date().toISOString(),
    submitted_at: null,
  } : null);

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

        {activeApp ? (
          <ApplicationDetailView app={activeApp} onRefresh={refetchApp} />
        ) : (
          <div className="flex flex-col gap-4">
            <ApplicationProcessStepper step={workflow.step} progressDetail={workflow.progressDetail} />
            <LiveExecutionFeed />
          </div>
        )}
      </div>
    );
  }

  const filteredApps = allApps.filter((a) => (filter === "all" ? true : a.status === filter));

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">Application Process</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Autonomous direct application pipeline with Playwright form autofill and verification mode.
        </p>
      </header>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 pb-3 dark:border-zinc-800">
        <span className="inline-flex items-center gap-1 text-xs text-zinc-400 mr-2">
          <Filter size={12} /> Status:
        </span>
        {["all", "awaiting_review", "needs_input", "blocked", "submitted"].map((tab) => (
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
          {filteredApps.map((a) => (
            <article
              key={a.job_id}
              className="flex flex-col justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
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
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_BADGE[a.status] ?? "bg-zinc-100"}`}>
                  {STATUS_LABEL[a.status] ?? a.status}
                </span>
              </div>

              <div className="flex items-center justify-between border-t border-zinc-100 pt-2 text-xs text-zinc-500 dark:border-zinc-800">
                <span>{a.plan.length} fields planned</span>
                <Link
                  href={`/applications/?jobId=${a.job_id}`}
                  className="font-medium text-zinc-700 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-zinc-100 hover:underline"
                >
                  Inspect &rarr;
                </Link>
              </div>
            </article>
          ))}
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
