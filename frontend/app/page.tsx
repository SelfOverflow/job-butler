"use client";

import { useEffect, useState } from "react";

import { formatTime } from "@/components/AuditLogViewer";
import { JobCard } from "@/components/JobCard";
import { LiveFeed } from "@/components/LiveFeed";
import { api, type AuditEvent, type Job } from "@/lib/api";

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs text-zinc-500 uppercase">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}

function sweepSummary(sweep: AuditEvent): string {
  const d = sweep.details as { discovered?: number; saved?: number; new?: number };
  return `${d.discovered ?? 0} discovered → ${d.saved ?? 0} saved (${d.new ?? 0} new)`;
}

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [sweep, setSweep] = useState<AuditEvent | null | undefined>(undefined);

  useEffect(() => {
    api.jobs().then(setJobs, () => setJobs([]));
    api.audit({ action: "SCOUT_SWEEP" }).then((page) => setSweep(page.items[0] ?? null), () => setSweep(null));
  }, []);

  const tailored = jobs.filter((j) => j.resume_url).length;
  const average = jobs.length ? Math.round(jobs.reduce((sum, j) => sum + j.score, 0) / jobs.length) : "—";
  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Active jobs" value={jobs.length} />
        <Metric label="Tailored" value={tailored} />
        <Metric label="Average fit" value={average} />
        <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-xs text-zinc-500 uppercase">Last sweep</p>
          {sweep ? (
            <>
              <p className="text-sm font-medium">{sweepSummary(sweep)}</p>
              <p className="text-xs text-zinc-500">{formatTime(sweep.timestamp)}</p>
            </>
          ) : (
            sweep === null && <p className="text-sm">No sweep yet: run <code>job-butler scout run</code></p>
          )}
        </div>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="flex flex-col gap-3">
          <h2 className="font-semibold">Top matches</h2>
          {jobs.slice(0, 3).map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
        <LiveFeed />
      </div>
    </section>
  );
}
