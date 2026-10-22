"use client";

import { useEffect, useMemo, useState } from "react";

import { JobCard } from "@/components/JobCard";
import { api, type Job, type Recency } from "@/lib/api";
import { RECENCY_OPTIONS, withinRecency } from "@/lib/recency";

const SCORE_FLOORS = [0, 60, 70, 80, 90];

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [recency, setRecency] = useState<Recency>("any");

  useEffect(() => {
    api.jobs().then(setJobs, (e: Error) => setError(e.message));
  }, []);

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
        </div>
        <div className="flex gap-2">
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

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          Could not load jobs: {error}
        </p>
      )}
      {jobs === null && !error && <p className="text-sm text-zinc-500">Loading…</p>}
      {jobs?.length === 0 && (
        <p className="text-sm text-zinc-500">
          No jobs yet. Run <code>job-butler scout run</code> to discover some.
        </p>
      )}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visible.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
      </div>
    </section>
  );
}
