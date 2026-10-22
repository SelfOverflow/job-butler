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

export const api = {
  jobs: () => request<Job[]>("/api/jobs"),
};
