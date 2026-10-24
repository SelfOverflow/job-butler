"use client";

import { useMemo, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { JobCard } from "@/components/JobCard";
import { api, type Job, type Recency } from "@/lib/api";
import { queryKeys, useJobsQuery, useLaunchCommandMutation, usePruneJobsMutation } from "@/lib/queries";
import { RECENCY_OPTIONS, withinRecency } from "@/lib/recency";

const SCORE_FLOORS = [0, 60, 70, 80, 90];

export default function JobsPage() {
  const queryClient = useQueryClient();
  const { data: jobs = null, error: jobsError } = useJobsQuery();
  const pruneMutation = usePruneJobsMutation();
  const launchCommandMutation = useLaunchCommandMutation();
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [recency, setRecency] = useState<Recency>("any");
  const [pruning, setPruning] = useState(false);
  const [pruneNote, setPruneNote] = useState<string | null>(null);
  const [verifyingAll, setVerifyingAll] = useState(false);
  const [verifyNote, setVerifyNote] = useState<string | null>(null);

  const displayError = error ?? (jobsError ? jobsError.message : null);

  const handlePruneAll = async () => {
    setPruning(true);
    setPruneNote(null);
    try {
      const { pruned } = await pruneMutation.mutateAsync();
      setPruneNote(`Pruned ${pruned} job(s)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPruning(false);
    }
  };

  const handleVerifyAll = async () => {
    setVerifyingAll(true);
    setVerifyNote(null);
    setError(null);
    try {
      const res = await launchCommandMutation.mutateAsync({
        name: "scout_verify",
        params: { delete_closed: true },
      });
      let run = await api.getRun(res.run_id).catch(() => null);
      for (let i = 0; i < 30 && run && (run.status === "queued" || run.status === "running"); i++) {
        await new Promise((r) => setTimeout(r, 500));
        run = await api.getRun(res.run_id).catch(() => null);
      }
      if (run?.status === "failed") {
        setError(run.error || "Verification sweep failed");
      } else if (run?.status === "succeeded") {
        const result = run.result as {
          counts?: { live?: number; closed?: number; deleted?: number; unknown?: number };
        } | null;
        const counts = result?.counts;
        const live = counts?.live ?? 0;
        const closedDeleted = counts?.deleted ?? counts?.closed ?? 0;
        const unknown = counts?.unknown ?? 0;
        setVerifyNote(
          `Re-verified: ${live} live, ${closedDeleted} closed & deleted${unknown > 0 ? `, ${unknown} unknown` : ""}`,
        );
      } else {
        setVerifyNote("Verification sweep running in background");
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
      await queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setVerifyingAll(false);
    }
  };

  const removeJob = (id: string) => {
    queryClient.setQueryData<Job[]>(queryKeys.jobs, (current) => current?.filter((j) => j.id !== id) ?? []);
  };

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (jobs ?? []).filter(
      (job) =>
        job.score >= minScore &&
        withinRecency(job, recency) &&
        (!needle || `${job.title} ${job.company} ${job.location}`.toLowerCase().includes(needle)),
    );
  }, [jobs, query, minScore, recency]);

  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Jobs</h1>
          {jobs && <p className="text-sm text-zinc-500">{`${visible.length} of ${jobs.length} jobs`}</p>}
          {pruneNote && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">{pruneNote}</p>}
          {verifyNote && <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">{verifyNote}</p>}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={verifyingAll || pruning}
            onClick={handleVerifyAll}
            title="Re-verify active job links; delete any that cannot be verified"
            className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            <RefreshCw size={14} className={verifyingAll ? "animate-spin" : ""} aria-hidden />
            {verifyingAll ? "Verifying…" : "Re-verify all"}
          </button>
          <button
            type="button"
            disabled={pruning || verifyingAll}
            onClick={handlePruneAll}
            title="Deactivate jobs that fail a profile gate or are older than your maximum job age"
            className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            <Trash2 size={14} aria-hidden />
            {pruning ? "Pruning…" : "Prune jobs"}
          </button>
          <input
            type="search"
            aria-label="Search jobs"
            placeholder="Search title, company, location"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-64 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
          <select
            aria-label="Posted within"
            value={recency}
            onChange={(e) => setRecency(e.target.value as Recency)}
            className="rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            {RECENCY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.hours === null ? "Posted any time" : `Posted within ${o.label}`}
              </option>
            ))}
          </select>
          <select
            aria-label="Minimum score"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            {SCORE_FLOORS.map((floor) => (
              <option key={floor} value={floor}>
                {floor ? `Score ≥ ${floor}` : "Any score"}
              </option>
            ))}
          </select>
        </div>
      </header>

      {displayError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          Could not load jobs: {displayError}
        </p>
      )}
      {jobs === null && !displayError && <p className="text-sm text-zinc-500">Loading…</p>}
      {jobs?.length === 0 && (
        <p className="text-sm text-zinc-500">
          No jobs yet. Run <code>job-butler scout run</code> to discover some.
        </p>
      )}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visible.map((job) => (
          <JobCard key={job.id} job={job} onPruned={removeJob} />
        ))}
      </div>
    </section>
  );
}
