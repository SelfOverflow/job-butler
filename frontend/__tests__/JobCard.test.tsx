import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { JobCard } from "@/components/JobCard";
import { hoursAgo, makeJob } from "./fixtures";

describe("JobCard", () => {
  it("renders title, company, ATS score badge, tier and download links", () => {
    render(<JobCard job={makeJob()} />);

    expect(screen.getByRole("heading", { name: "Senior Software Engineer" })).toBeInTheDocument();
    expect(screen.getByText("Hooli")).toBeInTheDocument();
    expect(screen.getByText("Bengaluru, India")).toBeInTheDocument();
    expect(screen.getByLabelText("Fit score 94")).toHaveTextContent("94");
    expect(screen.getByText("Tier 1")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /posting/i })).toHaveAttribute(
      "href",
      "https://boards.greenhouse.io/hooli/jobs/1",
    );
    expect(screen.getByRole("link", { name: /resume/i })).toHaveAttribute(
      "href",
      "/api/artifacts/job_1234abcd/resume",
    );
    expect(screen.getByRole("link", { name: /cover letter/i })).toHaveAttribute(
      "href",
      "/api/artifacts/job_1234abcd/cover_pdf",
    );
    expect(screen.getByRole("link", { name: /view details/i })).toHaveAttribute(
      "href",
      "/jobs/detail?id=job_1234abcd",
    );
  });

  it.each([
    ["discovered", "Discovered"],
    ["tailoring", "Tailoring…"],
    ["tailored", "Tailored"],
    ["tailor_failed", "Tailor Failed"],
    ["applied", "Applied"],
  ] as const)("renders the %s status badge", (status, label) => {
    render(<JobCard job={makeJob({ status })} />);
    expect(screen.getByLabelText(`Status ${label}`)).toHaveTextContent(label);
  });

  it("opens external postings in a new tab safely", () => {
    render(<JobCard job={makeJob()} />);
    const link = screen.getByRole("link", { name: /posting/i });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows the tailor command when no resume exists yet", () => {
    render(
      <JobCard job={makeJob({ resume_url: null, cover_letter_url: null, last_verified_at: null, tier_label: null })} />,
    );
    expect(screen.queryByRole("link", { name: /resume/i })).not.toBeInTheDocument();
    expect(screen.getByText("job-butler tailor --job-id job_1234abcd")).toBeInTheDocument();
    expect(screen.getByText("Unverified")).toBeInTheDocument();
  });

  it.each([
    [92, "bg-emerald"],
    [65, "bg-amber"],
    [30, "bg-zinc"],
  ])("colours score %i with %s", (score, colour) => {
    render(<JobCard job={makeJob({ score })} />);
    expect(screen.getByLabelText(`Fit score ${score}`).className).toContain(colour);
  });

  it.each([
    [{ posted_at: hoursAgo(5) }, "Posted 5h ago"],
    [{ posted_at: hoursAgo(50) }, "Posted 2d ago"],
    [{ posted_at: null, discovered_at: hoursAgo(30) }, "Found 1d ago"],
  ])("shows posting age %#", (overrides, label) => {
    render(<JobCard job={makeJob(overrides)} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
