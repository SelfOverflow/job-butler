import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import JobDetailPage from "@/app/jobs/detail/page";
import { api } from "@/lib/api";
import type { FeedMessage } from "@/lib/websocket";
import { makeJobDetail, mockFetch } from "./fixtures";

let emit: (msg: FeedMessage) => void = () => {};

vi.mock("@/lib/websocket", () => ({
  connectEvents: (onMessage: (msg: FeedMessage) => void) => {
    emit = onMessage;
    return () => {};
  },
}));

let mockSearchParams = new URLSearchParams({ id: "job_1234abcd" });

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
}));

describe("JobDetailPage", () => {
  beforeEach(() => {
    mockSearchParams = new URLSearchParams({ id: "job_1234abcd" });
    vi.restoreAllMocks();
  });

  it("renders job information and description on the left column", async () => {
    const job = makeJobDetail({
      title: "Senior Full-Stack Engineer",
      company: "Stripe",
      location: "Bengaluru, India",
      description: "Build financial infrastructure using React and Python.",
      resume_url: null,
    });
    mockFetch((url) => {
      if (url === "/api/jobs/job_1234abcd") return job;
      return {};
    });

    render(<JobDetailPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Senior Full-Stack Engineer" })).toBeInTheDocument();
    expect(screen.getByText("Stripe")).toBeInTheDocument();
    expect(screen.getByText(/Bengaluru, India/)).toBeInTheDocument();
    expect(screen.getByText("Build financial infrastructure using React and Python.")).toBeInTheDocument();
  });

  it("shows tailor button when no resume is tailored yet, and clicking triggers tailor_one", async () => {
    const job = makeJobDetail({ resume_url: null });
    mockFetch((url) => {
      if (url === "/api/jobs/job_1234abcd") return job;
      return {};
    });

    let resolveLaunch!: (val: { run_id: string; status: string; single_flight: boolean }) => void;
    const launchPromise = new Promise<{ run_id: string; status: string; single_flight: boolean }>((res) => {
      resolveLaunch = res;
    });
    const launchSpy = vi.spyOn(api, "launchCommand").mockReturnValue(launchPromise);

    render(<JobDetailPage />);

    const tailorBtn = await screen.findByRole("button", { name: /tailor resume/i });
    expect(tailorBtn).toBeInTheDocument();
    expect(screen.queryByTitle(/tailored resume/i)).not.toBeInTheDocument();

    await userEvent.click(tailorBtn);
    expect(launchSpy).toHaveBeenCalledWith("tailor_one", { job_id: "job_1234abcd" });
    expect(screen.getByText(/tailoring resume/i)).toBeInTheDocument();

    resolveLaunch({ run_id: "run_test_1", status: "queued", single_flight: false });
  });

  it("renders the PDF iframe when resume_url is present", async () => {
    const job = makeJobDetail({
      resume_url: "/api/artifacts/job_1234abcd/resume",
    });
    mockFetch((url) => {
      if (url === "/api/jobs/job_1234abcd") return job;
      return {};
    });

    render(<JobDetailPage />);

    await screen.findByRole("heading", { name: /Senior Software Engineer/i });
    const iframe = screen.getByTitle(/tailored resume/i);
    expect(iframe).toBeInTheDocument();
    expect(iframe).toHaveAttribute("src", expect.stringContaining("/api/artifacts/job_1234abcd/resume"));
    expect(screen.getByRole("link", { name: /download/i })).toHaveAttribute(
      "href",
      "/api/artifacts/job_1234abcd/resume",
    );
  });

  it("shows the persisted status and live tailoring progress from WebSocket events", async () => {
    mockFetch((url) => {
      if (url === "/api/jobs/job_1234abcd") return makeJobDetail({ status: "discovered", resume_url: null });
      return {};
    });

    render(<JobDetailPage />);

    expect(await screen.findByLabelText("Status Discovered")).toBeInTheDocument();

    act(() =>
      emit({
        type: "command",
        run: {
          id: "run_1",
          command: "tailor_one",
          params: { job_id: "job_1234abcd" },
          status: "running",
          progress: { stage: "tailor", done: 2, total: 4, detail: "Fitting Typst page budget..." },
          result: null,
          error: null,
          requested_by: "human:user",
          created_at: "2026-10-23T00:00:00",
          started_at: "2026-10-23T00:00:00",
          finished_at: null,
        },
      }),
    );

    expect(screen.getByLabelText("Status Tailoring…")).toBeInTheDocument();
    expect(screen.getByText("Step 2 of 4 (50%)")).toBeInTheDocument();
    expect(screen.getByText("Fitting Typst page budget...")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
  });

  it("shows an error alert when job is not found", async () => {
    mockFetch(() => ({ detail: "Not found" }), 404);

    render(<JobDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/could not load job/i)).toBeInTheDocument();
  });

  it("handles missing job id in search params", async () => {
    mockSearchParams = new URLSearchParams({});

    render(<JobDetailPage />);

    expect(await screen.findByText(/no job specified/i)).toBeInTheDocument();
  });
});
