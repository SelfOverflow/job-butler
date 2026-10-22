"use client";

import { useEffect, useState } from "react";

import { ApplicationCard } from "@/components/ApplicationCard";
import { api, type Application } from "@/lib/api";

export default function HitlPage() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.pending().then(setApps, (e: Error) => setError(e.message));
  }, []);

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Interventions</h1>
        <p className="text-sm text-zinc-500">
          Applications are never submitted until you approve them here or with{" "}
          <code>job-butler apply approve</code>.
        </p>
      </div>
      {error && <p role="alert" className="text-sm text-red-600">Could not load interventions: {error}</p>}
      {apps?.length === 0 && (
        <p className="text-sm text-zinc-500">
          No interventions pending. Prepare an application from a job card or with <code>job-butler apply --job-id</code>.
        </p>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        {apps?.map((app) => <ApplicationCard key={app.job_id} initial={app} />)}
      </div>
    </section>
  );
}
