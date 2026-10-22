// Typed client for the FastAPI backend. Paths are same-origin: FastAPI serves the
// static export in production, and `next dev` proxies /api in development.

export type Job = {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  score: number;
  tier: string | null;
  tier_label: string | null;
  is_active: boolean;
  discovered_at: string;
  last_verified_at: string | null;
  resume_url: string | null;
  cover_letter_url: string | null;
  cover_letter_txt_url: string | null;
};

export type AuditEvent = {
  id: string;
  timestamp: string; // naive UTC
  actor: string;
  action: string;
  target_id: string | null;
  status: "SUCCESS" | "WARNING" | "FAILURE" | string;
  duration_ms: number | null;
  details: Record<string, unknown>;
};

export type AuditPage = { items: AuditEvent[]; next_offset: number | null };
export type AuditFilters = { actor?: string; action?: string; status?: string };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API request failed with ${status}`);
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, body);
  return body as T;
}

export const AUDIT_PAGE_SIZE = 50;

export const api = {
  jobs: () => request<Job[]>("/api/jobs"),
  audit: (filters: AuditFilters, offset = 0) => {
    const params = new URLSearchParams(
      Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1])),
    );
    params.set("limit", String(AUDIT_PAGE_SIZE));
    params.set("offset", String(offset));
    return request<AuditPage>(`/api/audit?${params}`);
  },
};
