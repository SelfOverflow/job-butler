import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ApplicationsPage from "@/app/applications/page";
import { api, type Application } from "@/lib/api";

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

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

describe("ApplicationsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
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
});
