import type { Job, Recency } from "@/lib/api";

export const RECENCY_OPTIONS: { value: Recency; label: string; hours: number | null }[] = [
  { value: "24h", label: "24 hours", hours: 24 },
  { value: "48h", label: "48 hours", hours: 48 },
  { value: "72h", label: "72 hours", hours: 72 },
  { value: "1w", label: "1 week", hours: 168 },
  { value: "2w", label: "2 weeks", hours: 336 },
  { value: "4w", label: "4 weeks", hours: 672 },
  { value: "1m", label: "1 month", hours: 720 },
  { value: "any", label: "Any time", hours: null },
];

/** Hours since a naive-UTC API timestamp. */
export function ageHours(timestamp: string, now = Date.now()): number {
  return (now - Date.parse(`${timestamp}Z`)) / 3_600_000;
}

/** When the job was published, or (if the source gave no date) when we found it. */
function reference(job: Pick<Job, "posted_at" | "discovered_at">): string {
  return job.posted_at ?? job.discovered_at;
}

export function ageLabel(job: Pick<Job, "posted_at" | "discovered_at">): string {
  const hours = Math.max(0, ageHours(reference(job)));
  const amount = hours < 24 ? `${Math.floor(hours)}h` : `${Math.floor(hours / 24)}d`;
  return `${job.posted_at ? "Posted" : "Found"} ${amount} ago`;
}

export function withinRecency(job: Pick<Job, "posted_at" | "discovered_at">, recency: Recency): boolean {
  const hours = RECENCY_OPTIONS.find((o) => o.value === recency)?.hours ?? null;
  return hours === null || ageHours(reference(job)) <= hours;
}
