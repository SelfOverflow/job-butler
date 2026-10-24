import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { JobCard } from "@/components/JobCard";
import { api } from "@/lib/api";
import { resetTailorStore, useTailorStore } from "@/lib/tailorStore";
import { makeJob, makeRun } from "./fixtures";

describe("JobCard Actions", () => {
  afterEach(() => {
    resetTailorStore();
    vi.restoreAllMocks();
  });

  it("shows Tailor and Re-verify buttons and launches tailor_one", async () => {
    let resolveLaunch!: (val: { run_id: string; status: string; single_flight: boolean }) => void;
    const launchPromise = new Promise<{ run_id: string; status: string; single_flight: boolean }>((res) => {
      resolveLaunch = res;
    });
    const launchSpy = vi.spyOn(api, "launchCommand").mockReturnValue(launchPromise);
    vi.spyOn(api, "runs").mockResolvedValue([]);
    const progress = { done: 1, total: 4, detail: "Drafting & ranking bullets with LLM..." };
    vi.spyOn(api, "getRun").mockResolvedValue(makeRun({ id: "run_test_123", progress }));

    const job = makeJob({ resume_url: null, cover_letter_url: null });
    render(<JobCard job={job} />);

    const tailorBtn = screen.getByRole("button", { name: /tailor/i });
    expect(tailorBtn).toBeInTheDocument();

    await userEvent.click(tailorBtn);
    expect(launchSpy).toHaveBeenCalledWith("tailor_one", { job_id: job.id });
    expect(screen.getByRole("button", { name: /tailoring/i })).toBeInTheDocument();

    // Launch returns; the card shows live progress, not a resume, until the run succeeds.
    resolveLaunch({ run_id: "run_test_123", status: "queued", single_flight: false });
    expect(await screen.findByRole("button", { name: "Tailoring… 1/4" })).toBeDisabled();
    expect(screen.queryByRole("link", { name: /resume/i })).not.toBeInTheDocument();

    act(() => useTailorStore.getState().upsert(makeRun({ id: "run_test_123", status: "succeeded" })));
    expect(await screen.findByRole("link", { name: /resume/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Status Tailored")).toBeInTheDocument();
  });

  it("offers Re-tailor once a resume exists and shows its progress", async () => {
    vi.spyOn(api, "runs").mockResolvedValue([]);
    const launchSpy = vi.spyOn(api, "launchCommand").mockResolvedValue({ run_id: "run_2", status: "queued", single_flight: false });
    vi.spyOn(api, "getRun").mockResolvedValue(makeRun({ id: "run_2", progress: { done: 2, total: 4 } }));
    render(<JobCard job={makeJob()} />);  // Fixture job already has a resume.

    expect(screen.queryByRole("button", { name: /^tailor$/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Re-tailor" }));

    expect(launchSpy).toHaveBeenCalledWith("tailor_one", { job_id: "job_1234abcd" });
    expect(await screen.findByRole("button", { name: "Re-tailoring… 2/4" })).toBeDisabled();
    expect(screen.getByRole("link", { name: /resume/i })).toBeInTheDocument();  // Old resume stays available.
  });

  it("launches scout_verify when Re-verify is clicked", async () => {
    let resolveLaunch!: (val: { run_id: string; status: string; single_flight: boolean }) => void;
    const launchPromise = new Promise<{ run_id: string; status: string; single_flight: boolean }>((res) => {
      resolveLaunch = res;
    });
    const launchSpy = vi.spyOn(api, "launchCommand").mockReturnValue(launchPromise);
    vi.spyOn(api, "getRun").mockResolvedValue(
      makeRun({ id: "run_verify_456", status: "succeeded", result: { status: "live" } }),
    );

    const job = makeJob({ last_verified_at: null, is_active: true });
    render(<JobCard job={job} />);

    const verifyBtn = screen.getByRole("button", { name: /re-verify/i });
    expect(verifyBtn).toBeInTheDocument();

    await userEvent.click(verifyBtn);
    expect(launchSpy).toHaveBeenCalledWith("scout_verify", { job_id: job.id });
    expect(screen.getByText(/verifying/i)).toBeInTheDocument();

    resolveLaunch({ run_id: "run_verify_456", status: "queued", single_flight: false });
    expect(await screen.findByText("Live")).toBeInTheDocument();
  });

  it("marks job as Closed when Re-verify discovers link is dead", async () => {
    vi.spyOn(api, "launchCommand").mockResolvedValue({
      run_id: "run_verify_closed",
      status: "queued",
      single_flight: false,
    });
    vi.spyOn(api, "getRun").mockResolvedValue(
      makeRun({
        id: "run_verify_closed",
        status: "succeeded",
        result: { status: "closed", reason: "http 404" },
      }),
    );

    const job = makeJob({ is_active: true });
    render(<JobCard job={job} />);

    const verifyBtn = screen.getByRole("button", { name: /re-verify/i });
    await userEvent.click(verifyBtn);

    expect(await screen.findByText("Closed")).toBeInTheDocument();
  });

  it("prunes the job after confirmation and notifies the list", async () => {
    const pruneSpy = vi.spyOn(api, "pruneJob").mockResolvedValue({ job_id: "job_1234abcd", status: "pruned" });
    const onPruned = vi.fn();
    render(<JobCard job={makeJob()} onPruned={onPruned} />);

    await userEvent.click(screen.getByRole("button", { name: /^prune$/i }));
    expect(screen.getByRole("dialog")).toHaveTextContent(/won't bring it back/i);
    expect(pruneSpy).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Prune job" }));
    expect(pruneSpy).toHaveBeenCalledWith("job_1234abcd");
    expect(onPruned).toHaveBeenCalledWith("job_1234abcd");
  });
});
