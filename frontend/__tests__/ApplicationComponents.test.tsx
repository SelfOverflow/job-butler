import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { ApplicationDetailView } from "@/components/ApplicationDetailView";
import { ApplicationProcessStepper } from "@/components/ApplicationProcessStepper";
import type { Application } from "@/lib/api";

const SAMPLE_APP: Application = {
  job_id: "job_01234567",
  title: "Senior Lead Engineer",
  company: "Stripe",
  url: "https://example.com/apply",
  status: "awaiting_review",
  barrier: null,
  plan: [
    { label: "Full Name", kind: "text", value: "Mohit Ranjan", source: "profile" },
    { label: "Email", kind: "text", value: "mohit@example.com", source: "profile" },
  ],
  questions: [],
  answers: {},
  error: null,
  screenshot_url: "/api/hitl/job_01234567/screenshot",
  updated_at: new Date().toISOString(),
  submitted_at: null,
};

describe("ApplicationProcessStepper", () => {
  it("renders all 3 steps with labels", () => {
    render(<ApplicationProcessStepper step="filling_form" progressDetail="Typing email..." />);

    expect(screen.getByText("Step 1")).toBeInTheDocument();
    expect(screen.getByText("Step 2")).toBeInTheDocument();
    expect(screen.getByText("Step 3")).toBeInTheDocument();
    expect(screen.getByText("Typing email...")).toBeInTheDocument();
  });

  it("shows skipped state when tailoring is already done", () => {
    render(<ApplicationProcessStepper step="tailoring_skipped" />);
    expect(screen.getByText("Tailoring (Skipped)")).toBeInTheDocument();
  });

  it("shows failed states for tailoring and form filling", () => {
    const { rerender } = render(
      <ApplicationProcessStepper step="failed" failedStep="tailoring" />,
    );
    expect(screen.getByText("Tailoring (Failed)")).toBeInTheDocument();

    rerender(<ApplicationProcessStepper step="failed" failedStep="filling_form" />);
    expect(screen.getByText("Autofill (Failed)")).toBeInTheDocument();
  });
});

describe("ApplicationDetailView", () => {
  it("renders locked submit button and planned fields in review mode", () => {
    render(<ApplicationDetailView app={SAMPLE_APP} />);

    expect(screen.getByText("Senior Lead Engineer")).toBeInTheDocument();
    expect(screen.getByText("Verification Mode Active (Submission Locked)")).toBeInTheDocument();
    expect(screen.getByText("Submit Application (Locked)")).toBeDisabled();
    expect(screen.getByText("Full Name")).toBeInTheDocument();
    expect(screen.getByText("Mohit Ranjan")).toBeInTheDocument();
  });

  it("displays error alert and retry button when application step failed", () => {
    render(
      <ApplicationDetailView
        app={{
          ...SAMPLE_APP,
          status: "failed",
          error: "HTTP 404 at application form URL",
        }}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("HTTP 404 at application form URL");
    expect(screen.getByRole("button", { name: /retry application/i })).toBeInTheDocument();
  });
});
