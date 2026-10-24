"use client";

import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";

import { AuditLogViewer } from "@/components/AuditLogViewer";
import { api, type AuditFilters } from "@/lib/api";

const ACTORS = ["agent:scout", "agent:tailor", "agent:navigator", "agent:autopilot", "human:user"];
const ACTIONS = ["SCOUT_SWEEP", "JOB_DISCOVERED", "LINK_VERIFIED", "RESUME_TAILORED", "PROFILE_UPDATED", "FORM_SUBMITTED", "HITL_ESCALATED"];
const STATUSES = ["SUCCESS", "WARNING", "FAILURE"];
const select = "rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";

function Filter(props: { label: string; options: string[]; value?: string; onChange: (v: string) => void }) {
  return (
    <select aria-label={props.label} value={props.value ?? ""} onChange={(e) => props.onChange(e.target.value)} className={select}>
      <option value="">{`Any ${props.label.toLowerCase()}`}</option>
      {props.options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

export default function AuditPage() {
  const [filters, setFilters] = useState<AuditFilters>({});

  const {
    data,
    error: queryError,
    fetchNextPage,
    hasNextPage,
  } = useInfiniteQuery({
    queryKey: ["audit-infinite", filters],
    queryFn: ({ pageParam = 0 }) => api.audit(filters, pageParam),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => lastPage.next_offset ?? undefined,
  });

  const events = data ? data.pages.flatMap((p) => p.items) : null;
  const error = queryError ? queryError.message : null;

  const set = (key: keyof AuditFilters) => (value: string) => setFilters((f) => ({ ...f, [key]: value || undefined }));
  return (
    <section className="flex flex-col gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <div className="flex flex-wrap gap-2">
          <Filter label="Actor" options={ACTORS} value={filters.actor} onChange={set("actor")} />
          <Filter label="Action" options={ACTIONS} value={filters.action} onChange={set("action")} />
          <Filter label="Status" options={STATUSES} value={filters.status} onChange={set("status")} />
        </div>
      </header>
      {error && <p role="alert" className="text-sm text-red-600">Could not load the audit log: {error}</p>}
      {events === null && !error ? <p className="text-sm text-zinc-500">Loading…</p> : <AuditLogViewer events={events ?? []} />}
      {hasNextPage && (
        <button type="button" onClick={() => fetchNextPage()} className="self-center rounded-md border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800">
          Load more
        </button>
      )}
    </section>
  );
}
