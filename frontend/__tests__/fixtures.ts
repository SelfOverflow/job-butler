import { vi } from "vitest";

import type { Job } from "@/lib/api";

export function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "job_1234abcd",
    title: "Senior Software Engineer",
    company: "Hooli",
    location: "Bengaluru, India",
    url: "https://boards.greenhouse.io/hooli/jobs/1",
    source: "greenhouse",
    score: 94,
    tier: "tier1_india_domestic",
    tier_label: "Tier 1",
    is_active: true,
    discovered_at: "2026-10-22T07:00:00",
    last_verified_at: "2026-10-22T07:05:00",
    resume_url: "/api/artifacts/job_1234abcd/resume",
    cover_letter_url: "/api/artifacts/job_1234abcd/cover_pdf",
    cover_letter_txt_url: "/api/artifacts/job_1234abcd/cover_txt",
    ...overrides,
  };
}

export function mockFetch(handler: (url: string, init?: RequestInit) => unknown, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const body = handler(String(input), init);
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
}
