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

export type FieldError = { loc: string; msg: string };
export type Preferences = {
  target_roles: string[];
  min_base_salary: number | null;
  currency: string | null;
  years_of_experience: number | null;
  excluded_employers: string[];
};
export type ProfileResponse = {
  yaml: string;
  profile: { personal_info: { full_name: string }; preferences: Preferences } | null;
  errors: FieldError[];
};
export type Backup = { name: string; modified: string };
export type ProfileUpdate = { yaml: string } | { set: Record<string, string> };

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

/** Field errors from a 422 response (`detail: [{loc, msg}]`), else a single generic error. */
export function fieldErrors(error: unknown): FieldError[] {
  if (error instanceof ApiError && error.status === 422) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (Array.isArray(detail)) return detail as FieldError[];
  }
  return [{ loc: "", msg: error instanceof Error ? error.message : String(error) }];
}

const json = (body: unknown): RequestInit => ({
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

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
  profile: () => request<ProfileResponse>("/api/profile"),
  updateProfile: (update: ProfileUpdate) => request<unknown>("/api/profile", json(update)),
  backups: () => request<Backup[]>("/api/profile/backups"),
  restoreBackup: (name: string) =>
    request<unknown>("/api/profile/restore", { ...json({ name }), method: "POST" }),
};
