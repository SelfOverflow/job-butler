"use client";

import Link from "next/link";
import { useState } from "react";

import { ApiError } from "@/lib/api";
import { useHitlActionMutation } from "@/lib/queries";

const OUTCOME: Record<string, string> = {
  needs_input: "Needs your answers",
  awaiting_review: "Ready for review",
  blocked: "Blocked: needs you",
  failed: "Could not prepare",
};

/** Fills the application for review. Never submits: approval happens on /hitl. */
export function PrepareButton({ jobId }: { jobId: string }) {
  const hitlMutation = useHitlActionMutation();
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function prepare() {
    setBusy(true);
    setError(null);
    try {
      const app = await hitlMutation.mutateAsync({ jobId, action: "prepare" });
      setOutcome(OUTCOME[app.status] ?? app.status);
    } catch (e) {
      const detail = e instanceof ApiError ? (e.body as { detail?: string } | null)?.detail : undefined;
      setError(detail ?? (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <button type="button" disabled={busy} onClick={prepare} className="rounded-md border border-zinc-200 px-2.5 py-1 hover:bg-zinc-50 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800">
        {busy ? "Preparing…" : "Prepare application"}
      </button>
      {outcome && (
        <span>
          {outcome} ·{" "}
          <Link href="/hitl/" className="underline">Review</Link>
        </span>
      )}
      {error && <span role="alert" className="text-red-600">{error}</span>}
    </span>
  );
}
