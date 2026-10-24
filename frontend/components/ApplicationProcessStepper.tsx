"use client";

import { CheckCircle2, Circle, Clock, FastForward, Loader2 } from "lucide-react";
import React from "react";

import type { WorkflowStep } from "@/lib/applicationWorkflowStore";

export function ApplicationProcessStepper({
  step,
  progressDetail,
}: {
  step: WorkflowStep;
  progressDetail?: string | null;
}) {
  const isTailoring = step === "tailoring";
  const isTailorSkipped = step === "tailoring_skipped";
  const isTailorDone = isTailorSkipped || ["filling_form", "awaiting_review", "needs_input", "blocked"].includes(step);

  const isFilling = step === "filling_form";
  const isFillDone = ["awaiting_review", "needs_input", "blocked"].includes(step);

  const isReview = ["awaiting_review", "needs_input", "blocked"].includes(step);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Step 1: Tailoring */}
        <div className="flex items-center gap-2.5">
          {isTailoring ? (
            <Loader2 className="animate-spin text-sky-600 dark:text-sky-400" size={20} />
          ) : isTailorSkipped ? (
            <FastForward className="text-zinc-500" size={20} />
          ) : isTailorDone ? (
            <CheckCircle2 className="text-emerald-600 dark:text-emerald-400" size={20} />
          ) : (
            <Circle className="text-zinc-400" size={20} />
          )}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Step 1</p>
            <p className="text-sm font-medium">
              {isTailorSkipped ? "Tailoring (Skipped)" : "Resume Tailoring"}
            </p>
          </div>
        </div>

        <div className="hidden h-px w-8 bg-zinc-200 sm:block dark:bg-zinc-700" />

        {/* Step 2: Form Autofill */}
        <div className="flex items-center gap-2.5">
          {isFilling ? (
            <Loader2 className="animate-spin text-sky-600 dark:text-sky-400" size={20} />
          ) : isFillDone ? (
            <CheckCircle2 className="text-emerald-600 dark:text-emerald-400" size={20} />
          ) : (
            <Clock className="text-zinc-400" size={20} />
          )}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Step 2</p>
            <p className="text-sm font-medium">Form Autofill (Playwright)</p>
          </div>
        </div>

        <div className="hidden h-px w-8 bg-zinc-200 sm:block dark:bg-zinc-700" />

        {/* Step 3: Human Verification */}
        <div className="flex items-center gap-2.5">
          {isReview ? (
            <CheckCircle2 className="text-emerald-600 dark:text-emerald-400" size={20} />
          ) : (
            <Clock className="text-zinc-400" size={20} />
          )}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Step 3</p>
            <p className="text-sm font-medium">Human Verification</p>
          </div>
        </div>
      </div>

      {progressDetail && (
        <div className="flex items-center gap-2 rounded-md bg-zinc-50 px-3 py-1.5 text-xs text-zinc-600 dark:bg-zinc-800/60 dark:text-zinc-300">
          <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-pulse" />
          <span>{progressDetail}</span>
        </div>
      )}
    </div>
  );
}
