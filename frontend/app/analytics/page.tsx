"use client";

import { formatTime } from "@/components/AuditLogViewer";
import { BarChart } from "@/components/BarChart";
import { useTrendsQuery, useUpskillQuery } from "@/lib/queries";

const TOP = 12;

function Tile({ label, value }: { label: string; value: string | number }) {
  return (
    <li className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </li>
  );
}

export default function AnalyticsPage() {
  const { data: trends = null, error: trendsError } = useTrendsQuery();
  const { data: roi = null, error: upskillError } = useUpskillQuery();
  const error = trendsError?.message ?? upskillError?.message ?? null;

  const demand = (trends?.demand ?? []).slice(0, TOP);
  const upskill = (roi?.upskill ?? []).slice(0, TOP);
  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Analytics</h1>
      {error && <p role="alert" className="text-sm text-red-600">Could not load analytics: {error}</p>}
      {trends && !trends.created_at && (
        <p className="text-sm text-zinc-500">No market snapshot yet: run <code>job-butler scout run</code> to analyse the market.</p>
      )}
      {trends?.created_at && roi && (
        <>
          <ul aria-label="Market summary" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Tile label="Eligible postings" value={trends.total} />
            <Tile label={`Matched (fit score ≥ ${trends.threshold})`} value={trends.matched} />
            <Tile label="Snapshot" value={formatTime(trends.created_at)} />
          </ul>
          <div className="grid gap-6 xl:grid-cols-2">
            <BarChart
              title="Most demanded technologies"
              description={`Share of the ${trends.total} eligible postings that mention each technology.`}
              legend={[{ label: "You have it", series: 1 }, { label: "Missing", series: 2 }]}
              bars={demand.map((d) => ({
                key: d.skill,
                label: d.skill,
                value: d.share,
                valueLabel: `${d.share.toFixed(0)}%`,
                series: d.have ? 1 : 2,
                mark: d.have ? "✓" : "✗",
                details: [`${d.postings} postings`, d.have ? "You have it" : "Missing from your profile"],
              }))}
              table={{
                headers: ["Technology", "Postings", "Share", "You have it"],
                rows: demand.map((d) => [d.skill, d.postings, `${d.share}%`, d.have ? "Yes" : "No"]),
              }}
            />
            <BarChart
              title="Upskilling: roles each skill would unlock"
              description={`Postings that would reach a fit score of ${roi.threshold} if you added the skill (currently ${roi.matched} matched).`}
              bars={upskill.map((u) => ({
                key: u.skill,
                label: u.skill,
                value: u.unlocks,
                valueLabel: `+${u.unlocks} roles`,
                details: [`+${u.uplift_pct}% vs ${roi.matched} matched`, `in ${u.demand} postings`],
              }))}
              table={{
                headers: ["Skill", "Roles unlocked", "Uplift", "Postings mentioning"],
                rows: upskill.map((u) => [u.skill, u.unlocks, `+${u.uplift_pct}%`, u.demand]),
              }}
            />
          </div>
        </>
      )}
    </section>
  );
}
