"use client";

import { ExternalLink, Lock, ShieldAlert } from "lucide-react";
import React, { useState } from "react";

import { ApplicationProcessStepper } from "@/components/ApplicationProcessStepper";
import { LiveExecutionFeed } from "@/components/LiveExecutionFeed";
import type { Application, Question } from "@/lib/api";
import { useApplicationWorkflowStore } from "@/lib/applicationWorkflowStore";
import { useHitlActionMutation, useSubmitAnswersMutation } from "@/lib/queries";

const box =
  "rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const actionBtn =
  "rounded-md border border-zinc-200 px-3 py-1.5 text-sm hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800 transition";

function QuestionInput(props: { q: Question; value: string; onChange: (v: string) => void }) {
  const { q, value, onChange } = props;
  if (q.kind === "checkbox") {
    return (
      <input
        id={q.label}
        type="checkbox"
        checked={value === "yes"}
        onChange={(e) => onChange(e.target.checked ? "yes" : "no")}
      />
    );
  }
  if (q.options.length > 0) {
    return (
      <select id={q.label} value={value} onChange={(e) => onChange(e.target.value)} className={box}>
        <option value="">Choose…</option>
        {q.options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  }
  if (q.kind === "textarea") {
    return (
      <textarea
        id={q.label}
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={box}
      />
    );
  }
  return (
    <input
      id={q.label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={box}
    />
  );
}

export function ApplicationDetailView({
  app,
  onRefresh,
}: {
  app: Application;
  onRefresh?: () => void;
}) {
  const { step, progressDetail } = useApplicationWorkflowStore();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hitlMutation = useHitlActionMutation();
  const answerMutation = useSubmitAnswersMutation();

  const isExecuting = step === "tailoring" || step === "filling_form";

  async function handleAction(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onRefresh?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-5">
      <ApplicationProcessStepper step={step} progressDetail={progressDetail} />

      {isExecuting && <LiveExecutionFeed />}

      {/* Safety Verification Guard Alert */}
      <div className="flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50/80 p-4 text-sky-900 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-300">
        <ShieldAlert className="mt-0.5 shrink-0 text-sky-600 dark:text-sky-400" size={18} />
        <div className="text-sm">
          <p className="font-semibold">Verification Mode Active (Submission Locked)</p>
          <p className="mt-0.5 text-xs text-sky-800 dark:text-sky-300">
            Playwright automatically fills the form, uploads your tailored resume, and captures a verification screenshot. Actual submission is never performed until you verify the filled data.
          </p>
        </div>
      </div>

      {(app.error || error) && (
        <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/60 dark:text-red-300">
          {error ?? app.error}
        </div>
      )}

      {/* Split view: Fields/Questions on Left, Screenshot on Right */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 items-start">
        {/* Left Column: Form Plan / Screening Questions */}
        <div className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-3 dark:border-zinc-800">
            <div>
              <h3 className="font-semibold">{app.title}</h3>
              <p className="text-xs text-zinc-500">{app.company} · {app.job_id}</p>
            </div>
            <a
              href={app.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
            >
              <ExternalLink size={12} /> ATS Posting
            </a>
          </div>

          {app.status === "needs_input" && (
            <div className="flex flex-col gap-3">
              <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
                The ATS form requires answers to the following screening questions:
              </p>
              {app.questions.map((q) => (
                <label key={q.label} htmlFor={q.label} className="flex flex-col gap-1 text-xs">
                  <span className="font-medium text-zinc-700 dark:text-zinc-300">{q.label}</span>
                  <QuestionInput
                    q={q}
                    value={answers[q.label] ?? ""}
                    onChange={(v) => setAnswers((a) => ({ ...a, [q.label]: v }))}
                  />
                </label>
              ))}
              <button
                type="button"
                disabled={busy}
                onClick={() => handleAction(() => answerMutation.mutateAsync({ jobId: app.job_id, answers }))}
                className="mt-2 rounded-md bg-zinc-900 py-2 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
              >
                {busy ? "Saving & Re-filling…" : "Save Answers & Re-fill Form"}
              </button>
            </div>
          )}

          {app.status === "blocked" && (
            <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
              <p className="font-semibold">Barrier Detected: {app.barrier}</p>
              <p className="mt-1">
                Please complete the account creation or CAPTCHA directly on the posting, then mark it as applied.
              </p>
            </div>
          )}

          {app.plan.length > 0 && (
            <div className="flex flex-col gap-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Planned Form Fields ({app.plan.length})
              </h4>
              <div className="max-h-[360px] overflow-y-auto divide-y divide-zinc-100 dark:divide-zinc-800">
                {app.plan.map((field) => (
                  <div key={field.label} className="flex items-start justify-between py-2 text-xs">
                    <span className="font-medium text-zinc-600 dark:text-zinc-400">{field.label}</span>
                    <span className="truncate max-w-[200px] text-right text-zinc-900 dark:text-zinc-100">
                      {field.kind === "file" ? field.value.split("/").pop() : field.value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-zinc-100 dark:border-zinc-800">
            {app.status === "awaiting_review" && (
              <button
                type="button"
                disabled
                className="inline-flex items-center gap-1.5 rounded-md bg-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-500 cursor-not-allowed dark:bg-zinc-800 dark:text-zinc-400"
                title="Locked in verification mode"
              >
                <Lock size={12} /> Submit Application (Locked)
              </button>
            )}

            {app.status === "blocked" && (
              <button
                type="button"
                disabled={busy}
                onClick={() => handleAction(() => hitlMutation.mutateAsync({ jobId: app.job_id, action: "resolve" }))}
                className={actionBtn}
              >
                I applied myself
              </button>
            )}

            <button
              type="button"
              disabled={busy}
              onClick={() => handleAction(() => hitlMutation.mutateAsync({ jobId: app.job_id, action: "skip" }))}
              className={actionBtn}
            >
              Skip
            </button>
          </div>
        </div>

        {/* Right Column: Full-Page Playwright Verification Screenshot */}
        <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Verification Screenshot</h3>
            {app.screenshot_url && (
              <a
                href={app.screenshot_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              >
                <ExternalLink size={12} /> Open Full Size
              </a>
            )}
          </div>

          {app.screenshot_url ? (
            <div className="overflow-hidden rounded-lg border border-zinc-200 bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-950 max-h-[560px] overflow-y-auto">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={app.screenshot_url}
                alt={`Screenshot of application for ${app.company}`}
                className="w-full object-top"
              />
            </div>
          ) : (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed border-zinc-200 text-xs text-zinc-400 dark:border-zinc-800">
              Screenshot will appear once Playwright completes form autofill.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
