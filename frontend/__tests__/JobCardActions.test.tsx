import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { JobCard } from "@/components/JobCard";
import { api } from "@/lib/api";
import { makeJob } from "./fixtures";

describe("JobCard Actions", () => {
  it("shows Tailor and Re-verify buttons and launches tailor_one", async () => {
    let resolveLaunch!: (val: { run_id: string; status: string; single_flight: boolean }) => void;
    const launchPromise = new Promise<{ run_id: string; status: string; single_flight: boolean }>((res) => {
      resolveLaunch = res;
    });
    const launchSpy = vi.spyOn(api, "launchCommand").mockReturnValue(launchPromise);

    const job = makeJob({ resume_url: null, cover_letter_url: null });
    render(<JobCard job={job} />);

    const tailorBtn = screen.getByRole("button", { name: /tailor/i });
    expect(tailorBtn).toBeInTheDocument();

    await userEvent.click(tailorBtn);
    expect(launchSpy).toHaveBeenCalledWith("tailor_one", { job_id: job.id });
    expect(screen.getByText(/tailoring/i)).toBeInTheDocument();

    // Finish launch
    resolveLaunch({ run_id: "run_test_123", status: "queued", single_flight: false });
    expect(await screen.findByRole("link", { name: /resume/i })).toBeInTheDocument();
  });

  it("launches scout_verify when Re-verify is clicked", async () => {
    let resolveLaunch!: (val: { run_id: string; status: string; single_flight: boolean }) => void;
    const launchPromise = new Promise<{ run_id: string; status: string; single_flight: boolean }>((res) => {
      resolveLaunch = res;
    });
    const launchSpy = vi.spyOn(api, "launchCommand").mockReturnValue(launchPromise);

    const job = makeJob({ last_verified_at: null });
    render(<JobCard job={job} />);

    const verifyBtn = screen.getByRole("button", { name: /re-verify/i });
    expect(verifyBtn).toBeInTheDocument();

    await userEvent.click(verifyBtn);
    expect(launchSpy).toHaveBeenCalledWith("scout_verify", { job_id: job.id });
    expect(screen.getByText(/verifying/i)).toBeInTheDocument();

    resolveLaunch({ run_id: "run_verify_456", status: "queued", single_flight: false });
    expect(await screen.findByText("Live")).toBeInTheDocument();
  });
});
