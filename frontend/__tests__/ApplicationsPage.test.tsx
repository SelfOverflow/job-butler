import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ApplicationsPage from "@/app/applications/page";
import { api, type Application, type JobDetail } from "@/lib/api";
import { useApplicationWorkflowStore } from "@/lib/applicationWorkflowStore";

const SAMPLE_APPS: Application[] = [
  {
    job_id: "job_00000001",
    title: "Senior Lead Engineer",
    company: "Google",
    url: "https://example.com/apply",
    status: "awaiting_review",
    barrier: null,
    plan: [{ label: "Full Name", kind: "text", value: "Mohit", source: "profile" }],
    questions: [],
    answers: {},
    error: null,
    screenshot_url: "/api/hitl/job_00000001/screenshot",
    updated_at: new Date().toISOString(),
    submitted_at: null,
  },
];

const ONGOING_JOB: JobDetail = {
  id: "job_ongoing_1",
  title: "Staff Distributed Systems Engineer",
  company: "Cloudflare",
  location: "Remote",
  url: "https://cloudflare.com/apply",
  source: "greenhouse",
  score: 95,
  tier: "tier1",
  tier_label: "Tier 1",
  is_active: true,
  status: "tailored",
  posted_at: null,
  discovered_at: new Date().toISOString(),
  last_verified_at: null,
  resume_url: "/artifacts/resumes/job_ongoing_1_resume.pdf",
  cover_letter_url: null,
  cover_letter_txt_url: null,
  description: "Distributed systems job description",
  ats_review: null,
};

let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
}));

describe("ApplicationsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockSearchParams = new URLSearchParams();
    useApplicationWorkflowStore.getState().reset();
  });

  it("renders header and lists applications", async () => {
    vi.spyOn(api, "applications").mockResolvedValue(SAMPLE_APPS);

    render(<ApplicationsPage />);

    expect(screen.getByText("Application Process")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Senior Lead Engineer")).toBeInTheDocument();
      expect(screen.getByText("Google")).toBeInTheDocument();
      expect(screen.getAllByText("Ready for Review").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows empty state when no applications exist", async () => {
    vi.spyOn(api, "applications").mockResolvedValue([]);

    render(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("No applications found")).toBeInTheDocument();
      expect(screen.getByText(/Browse Jobs/i)).toBeInTheDocument();
    });
  });

  it("displays prominent ongoing application card and in-progress list item when an application is running", async () => {
    vi.spyOn(api, "applications").mockResolvedValue(SAMPLE_APPS);
    vi.spyOn(api, "job").mockResolvedValue(ONGOING_JOB);

    useApplicationWorkflowStore.setState({
      jobId: "job_ongoing_1",
      step: "filling_form",
      progressStage: "filling_form",
      progressDetail: "Filling field 3/8: Email (text)",
      progressDone: 3,
      progressTotal: 8,
    });

    render(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Ongoing Application Process")).toBeInTheDocument();
      expect(screen.getAllByText("Staff Distributed Systems Engineer").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Filling field 3\/8: Email/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/View Live Execution/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows live stepper and live execution feed when viewing ongoing application details", async () => {
    mockSearchParams = new URLSearchParams("jobId=job_ongoing_1");
    vi.spyOn(api, "job").mockResolvedValue(ONGOING_JOB);
    vi.spyOn(api, "application").mockRejectedValue(new Error("Not found"));

    useApplicationWorkflowStore.setState({
      jobId: "job_ongoing_1",
      step: "filling_form",
      progressStage: "filling_form",
      progressDetail: "Filling field 3/8: Email",
      progressDone: 3,
      progressTotal: 8,
    });

    render(<ApplicationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Staff Distributed Systems Engineer")).toBeInTheDocument();
      expect(screen.getByText("Autofilling Form")).toBeInTheDocument();
      expect(screen.getByText("Form Autofill (Playwright)")).toBeInTheDocument();
      expect(screen.getByText("Playwright Navigator Live Stream")).toBeInTheDocument();
    });
  });
});
