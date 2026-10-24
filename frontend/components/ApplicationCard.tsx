"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import type { Application, HitlAction, Question } from "@/lib/api";
import { useHitlActionMutation, useSubmitAnswersMutation } from "@/lib/queries";

const STATUS: Record<string, string> = {
  needs_input: "Needs your answers",
  blocked: "Blocked",
  awaiting_review: "Ready for review",
  submitted: "Submitted",
  applied_manually: "Applied manually",
  skipped: "Skipped",
  failed: "Failed",
};
const button = "rounded-md border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800";
const primary = "rounded-md bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900";
const box = "rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900";

function QuestionInput(props: { q: Question; value: string; onChange: (v: string) => void }) {
  const { q, value, onChange } = props;
  if (q.kind === "checkbox")
    return <input id={q.label} type="checkbox" checked={value === "yes"} onChange={(e) => onChange(e.target.checked ? "yes" : "no")} />;
  if (q.options.length > 0)
    return (
      <select id={q.label} value={value} onChange={(e) => onChange(e.target.value)} className={box}>
        <option value="">Choose…</option>
        {q.options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  if (q.kind === "textarea") return <textarea id={q.label} rows={3} value={value} onChange={(e) => onChange(e.target.value)} className={box} />;
  return <input id={q.label} value={value} onChange={(e) => onChange(e.target.value)} className={box} />;
}

export function ApplicationCard({ initial }: { initial: Application }) {
  const [app, setApp] = useState(initial);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hitlMutation = useHitlActionMutation();
  const answerMutation = useSubmitAnswersMutation();

  async function run(call: () => Promise<Application>) {
    setBusy(true);
    setError(null);
    try {
      setApp(await call());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }
  const act = (action: HitlAction) => run(() => hitlMutation.mutateAsync({ jobId: app.job_id, action }));

  return (
    <article aria-label={`${app.title} at ${app.company}`} className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">{app.title}</h2>
          <p className="text-sm text-zinc-500">{app.company} · {app.job_id}</p>
        </div>
        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium dark:bg-zinc-800">{STATUS[app.status] ?? app.status}</span>
      </header>
      {app.screenshot_url && (
        <a href={app.screenshot_url} target="_blank" rel="noopener noreferrer">
          {/* eslint-disable-next-line @next/next/no-img-element -- served by FastAPI, not next/image */}
          <img src={app.screenshot_url} alt={`Screenshot of the ${app.company} application`} className="max-h-48 rounded border border-zinc-200 object-cover object-top dark:border-zinc-800" />
        </a>
      )}
      {(app.error || error) && <p role="alert" className="text-sm text-red-600">{error ?? app.error}</p>}

      {app.status === "needs_input" && (
        <div className="flex flex-col gap-2">
          {app.questions.map((q) => (
            <label key={q.label} htmlFor={q.label} className="flex flex-col gap-1 text-sm">
              <span>{q.label}</span>
              <QuestionInput q={q} value={answers[q.label] ?? ""} onChange={(v) => setAnswers((a) => ({ ...a, [q.label]: v }))} />
            </label>
          ))}
          <button type="button" disabled={busy} className={primary} onClick={() => run(() => answerMutation.mutateAsync({ jobId: app.job_id, answers }))}>
            {busy ? "Working…" : "Save answers & re-check"}
          </button>
        </div>
      )}

      {app.status === "awaiting_review" && (
        <table className="text-sm">
          <tbody>
            {app.plan.map((f) => (
              <tr key={f.label} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                <td className="py-1 pr-3 text-zinc-500">{f.label}</td>
                <td className="py-1">{f.kind === "file" ? f.value.split("/").pop() : f.value}</td>
                <td className="py-1 pl-3 text-xs text-zinc-400">{f.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {app.status === "blocked" && (
        <p className="text-sm">
          {(app.barrier ?? "").replaceAll("_", " ").toLowerCase()}: finish it on the{" "}
          <a href={app.url} target="_blank" rel="noopener noreferrer" className="underline">open posting</a>, then mark it applied.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {app.status === "awaiting_review" && (
          <button type="button" disabled={busy} className={primary} onClick={() => setConfirming(true)}>Approve &amp; submit</button>
        )}
        <ConfirmDialog
          open={confirming}
          title={`Submit to ${app.company}?`}
          description={`This will submit your tailored application directly to ${app.company}. Please ensure you have reviewed all fields.`}
          confirmLabel={busy ? "Submitting…" : "Confirm"}
          cancelLabel="Cancel"
          busy={busy}
          onConfirm={() => act("approve")}
          onCancel={() => setConfirming(false)}
        />
        {app.status === "blocked" && <button type="button" disabled={busy} className={button} onClick={() => act("resolve")}>I applied myself</button>}
        {["needs_input", "blocked", "awaiting_review"].includes(app.status) && (
          <button type="button" disabled={busy} className={button} onClick={() => act("skip")}>Skip</button>
        )}
      </div>
    </article>
  );
}
