"use client";

import { useState } from "react";

export type Bar = {
  key: string;
  label: string;
  value: number;
  valueLabel: string; // Shown at the bar tip and first in the tooltip.
  series?: 1 | 2;
  mark?: string; // Secondary, non-color identity cue (e.g. ✓ / ✗).
  details: string[]; // Tooltip lines after the value.
};

type Props = {
  title: string;
  description?: string;
  bars: Bar[];
  legend?: { label: string; series: 1 | 2 }[]; // Only for >= 2 identities.
  table: { headers: string[]; rows: (string | number)[][] };
};

/** Horizontal bars: <=24px thick, 4px rounded data end, square at the baseline. */
export function BarChart({ title, description, bars, legend, table }: Props) {
  const [active, setActive] = useState<string | null>(null);
  const [asTable, setAsTable] = useState(false);
  const max = Math.max(1, ...bars.map((b) => b.value));

  return (
    <figure aria-label={title} className="viz-root flex flex-col gap-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" style={{ background: "var(--viz-surface)", color: "var(--viz-ink)" }}>
      <figcaption className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">{title}</h2>
          {description && <p className="text-sm" style={{ color: "var(--viz-ink-2)" }}>{description}</p>}
        </div>
        <button type="button" onClick={() => setAsTable((v) => !v)} className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700">
          {asTable ? "Show chart" : "Show table"}
        </button>
      </figcaption>

      {legend && !asTable && (
        <ul aria-label="Legend" className="flex gap-4 text-xs" style={{ color: "var(--viz-ink-2)" }}>
          {legend.map((l) => (
            <li key={l.label} className="flex items-center gap-1.5">
              <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: `var(--series-${l.series})` }} />
              {l.label}
            </li>
          ))}
        </ul>
      )}

      {asTable ? (
        <table className="text-sm">
          <thead style={{ color: "var(--viz-muted)" }}>
            <tr>{table.headers.map((h) => <th key={h} className="py-1 pr-4 text-left font-medium">{h}</th>)}</tr>
          </thead>
          <tbody className="tabular-nums">
            {table.rows.map((row) => (
              <tr key={String(row[0])} className="border-t border-zinc-100 dark:border-zinc-800">
                {row.map((cell, i) => <td key={i} className="py-1 pr-4">{cell}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {bars.map((bar) => (
            <li
              key={bar.key}
              tabIndex={0}
              aria-label={`${bar.label}: ${bar.valueLabel}`}
              onMouseEnter={() => setActive(bar.key)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(bar.key)}
              onBlur={() => setActive(null)}
              className="relative grid grid-cols-[9rem_1fr] items-center gap-3 rounded py-0.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              <span className="truncate" style={{ color: "var(--viz-ink-2)" }}>{bar.label}</span>
              <span className="flex items-center gap-2 border-l" style={{ borderColor: "var(--viz-axis)" }}>
                <span
                  aria-hidden
                  className="h-5 rounded-r"
                  style={{ width: `${(bar.value / max) * 85}%`, minWidth: 2, background: `var(--series-${bar.series ?? 1})` }}
                />
                <span className="text-xs whitespace-nowrap tabular-nums">{bar.valueLabel}</span>
                {bar.mark && <span className="text-xs" style={{ color: "var(--viz-ink-2)" }}>{bar.mark}</span>}
              </span>
              {active === bar.key && (
                <span role="tooltip" className="absolute top-full left-36 z-10 mt-1 flex flex-col rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs shadow-md dark:border-zinc-700 dark:bg-zinc-900">
                  <strong className="text-sm">{bar.valueLabel}</strong>
                  <span style={{ color: "var(--viz-ink-2)" }}>{bar.label}</span>
                  {bar.details.map((d) => <span key={d} style={{ color: "var(--viz-ink-2)" }}>{d}</span>)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
