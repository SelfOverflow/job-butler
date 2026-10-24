// Typed client for the FastAPI backend. Paths are same-origin: FastAPI serves the
// static export in production, and `next dev` proxies /api in development.

export type JobStatus = "discovered" | "tailoring" | "tailored" | "tailor_failed" | "applied" | "pruned";

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
  status: JobStatus;
  posted_at: string | null;
  discovered_at: string;
  last_verified_at: string | null;
  resume_url: string | null;
  cover_letter_url: string | null;
  cover_letter_txt_url: string | null;
};

export type RequirementCheck = {
  requirement: string;
  priority: "required" | "preferred";
  status: "covered" | "synonym_only" | "missing_have_it" | "gap";
  note: string;
};

/** Recruiter/ATS review of the tailored resume (src/agents/tailor/ats_review.py). */
export type AtsReview = {
  score: number;
  verdict: "shortlist" | "borderline" | "reject";
  requirements: RequirementCheck[];
  issues: string[];
  ungrounded_claims: string[];
};

export type JobDetail = Job & {
  description: string;
  ats_review: AtsReview | null;
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

export type Recency = "24h" | "48h" | "72h" | "1w" | "2w" | "4w" | "1m" | "any";
export type FieldError = { loc: string; msg: string };
export type Preferences = {
  target_roles: string[];
  min_base_salary: number | null;
  currency: string | null;
  years_of_experience: number | null;
  excluded_employers: string[];
  job_recency: Recency;
  job_max_age: Recency;
};
export type ProfileResponse = {
  yaml: string;
  profile: { personal_info: { full_name: string }; preferences: Preferences } | null;
  errors: FieldError[];
};
export type Backup = { name: string; modified: string };
export type PlannedField = { label: string; kind: string; value: string; source: string };
export type Question = { label: string; kind: string; options: string[] };
export type Application = {
  job_id: string;
  title: string;
  company: string;
  url: string;
  status: "needs_input" | "blocked" | "awaiting_review" | "submitted" | "applied_manually" | "skipped" | "failed";
  barrier: string | null;
  plan: PlannedField[];
  questions: Question[];
  answers: Record<string, string>;
  error: string | null;
  screenshot_url: string | null;
  updated_at: string;
  submitted_at: string | null;
};
export type SkillDemand = { skill: string; postings: number; share: number; have: boolean };
export type SkillRoi = { skill: string; unlocks: number; demand: number; uplift_pct: number };
export type Trends = { created_at: string | null; total: number; matched: number; threshold: number; demand: SkillDemand[] };
export type UpskillReport = { created_at: string | null; matched: number; threshold: number; upskill: SkillRoi[] };
export type HitlAction = "prepare" | "approve" | "skip" | "resolve";
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

export async function requestText(path: string, init?: RequestInit): Promise<string> {
  const response = await fetch(path, init);
  const text = await response.text();
  if (!response.ok) throw new ApiError(response.status, text);
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed === "string") return parsed;
    if (typeof parsed === "object" && parsed !== null && "yaml" in parsed) {
      return "# Master Resume\n\nPreview unavailable in mock";
    }
  } catch {
    // Raw text content
  }
  return text;
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
  job: (id: string) => request<JobDetail>(`/api/jobs/${id}`),
  /** Deactivate jobs failing a profile gate or older than `job_max_age`. */
  pruneJobs: () => request<{ pruned: number }>("/api/jobs/prune", { method: "POST" }),
  /** Remove one job for good; later sweeps never bring it back. */
  pruneJob: (id: string) =>
    request<{ job_id: string; status: string }>(`/api/jobs/${id}/prune`, { method: "POST" }),
  audit: (filters: AuditFilters, offset = 0) => {
    const params = new URLSearchParams(
      Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1])),
    );
    params.set("limit", String(AUDIT_PAGE_SIZE));
    params.set("offset", String(offset));
    return request<AuditPage>(`/api/audit?${params}`);
  },
  profile: () => request<ProfileResponse>("/api/profile"),
  validateProfile: () =>
    request<{
      valid: boolean;
      full_name: string;
      bullet_count: number;
      role_count: number;
      star_story_count: number;
      screening_count: number;
    }>("/api/profile/validate"),
  exportMaster: () => requestText("/api/profile/export-master"),
  queryScreening: (question: string) =>
    request<{ question: string; answer: unknown }>("/api/profile/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  addBullet: (role_id: string, text: string, skills: string[] = []) =>
    request<{ bullet_id: string }>("/api/profile/bullets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role_id, text, skills }),
    }),
  updateProfile: (update: ProfileUpdate) => request<unknown>("/api/profile", json(update)),
  backups: () => request<Backup[]>("/api/profile/backups"),
  restoreBackup: (name: string) =>
    request<unknown>("/api/profile/restore", { ...json({ name }), method: "POST" }),
  trends: () => request<Trends>("/api/analytics/trends"),
  upskill: () => request<UpskillReport>("/api/analytics/upskill"),
  pending: () => request<Application[]>("/api/hitl/pending"),
  /** prepare/answers never submit; only "approve" submits an application. */
  hitl: (jobId: string, action: HitlAction) =>
    request<Application>(`/api/hitl/${jobId}/${action}`, { method: "POST" }),
  answer: (jobId: string, answers: Record<string, string>) =>
    request<Application>(`/api/hitl/${jobId}/answers`, { ...json({ answers }), method: "POST" }),
  launchCommand: (name: string, params: Record<string, unknown> = {}) =>
    request<{ run_id: string; status: string; single_flight: boolean }>(`/api/commands/${name}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    }),
  runs: () => request<import("./commands").CommandRun[]>("/api/commands/runs"),
  getRun: (id: string) => request<import("./commands").CommandRun>(`/api/commands/runs/${id}`),
  cancelRun: (id: string) => request<{ status: string }>(`/api/commands/runs/${id}/cancel`, { method: "POST" }),
  settings: () =>
    request<{
      auth_enabled: boolean;
      gemini_model: string;
      gemini_configured: boolean;
      firecrawl_configured: boolean;
      openai_configured: boolean;
      anthropic_configured: boolean;
      max_daily_scrape_credits: number;
    }>("/api/settings"),
};
