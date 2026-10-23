import { vi } from "vitest";

import type { Application, AuditEvent, Job, JobDetail } from "@/lib/api";

/** Naive-UTC timestamp `hours` before now, matching the API's format. */
export function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3_600_000).toISOString().replace("Z", "").split(".")[0];
}

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
    status: "discovered",
    posted_at: hoursAgo(5),
    discovered_at: hoursAgo(1),
    last_verified_at: "2026-10-22T07:05:00",
    resume_url: "/api/artifacts/job_1234abcd/resume",
    cover_letter_url: "/api/artifacts/job_1234abcd/cover_pdf",
    cover_letter_txt_url: "/api/artifacts/job_1234abcd/cover_txt",
    ...overrides,
  };
}

export function makeJobDetail(overrides: Partial<JobDetail> = {}): JobDetail {
  return {
    ...makeJob(),
    description: "We are looking for a Senior Software Engineer to build distributed systems.",
    ...overrides,
  };
}

export function mockFetch(handler: (url: string, init?: RequestInit) => unknown, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const body = handler(String(input), init);
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
}

export function makeEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: "e1",
    timestamp: "2026-10-22T07:50:28",
    actor: "agent:scout",
    action: "SCOUT_SWEEP",
    target_id: null,
    status: "SUCCESS",
    duration_ms: 1500,
    details: { saved: 20, errors: [] },
    ...overrides,
  };
}

/** Minimal controllable stand-in for the browser WebSocket. */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  open() {
    this.onopen?.();
  }

  emit(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  drop() {
    this.onclose?.();
  }

  close() {
    this.closed = true;
    this.onclose?.();
  }

  static latest(): FakeWebSocket {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  }
}

export function makeApplication(overrides: Partial<Application> = {}): Application {
  return {
    job_id: "job_1234abcd",
    title: "Senior Software Engineer",
    company: "Hooli",
    url: "https://boards.greenhouse.io/hooli/jobs/1",
    status: "awaiting_review",
    barrier: null,
    plan: [
      { label: "First Name", kind: "text", value: "Jane", source: "profile" },
      { label: "Resume/CV", kind: "file", value: "/artifacts/resumes/job_1234abcd_resume.pdf", source: "resume" },
    ],
    questions: [],
    answers: {},
    error: null,
    screenshot_url: "/api/hitl/job_1234abcd/screenshot",
    updated_at: "2026-10-22T10:00:00",
    submitted_at: null,
    ...overrides,
  };
}
