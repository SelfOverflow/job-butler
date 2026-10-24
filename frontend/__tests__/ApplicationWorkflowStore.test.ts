import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { useApplicationWorkflowStore } from "@/lib/applicationWorkflowStore";
import type { CommandRun } from "@/lib/commands";

describe("ApplicationWorkflowStore", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useApplicationWorkflowStore.getState().reset();
  });

  it("skips tailoring if resume already exists and proceeds to fill form", async () => {
    const store = useApplicationWorkflowStore.getState();

    const mockPrepareRun: CommandRun = {
      id: "run_prep_1",
      command: "prepare_application",
      params: { job_id: "job_01234567" },
      status: "succeeded",
      progress: { stage: "screenshot", done: 5, total: 5, detail: "Captured screenshot" },
      result: { job_id: "job_01234567", status: "awaiting_review" },
      error: null,
      requested_by: "human:user",
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };

    vi.spyOn(api, "launchCommand").mockResolvedValue({
      run_id: "run_prep_1",
      status: "queued",
      single_flight: false,
    });
    vi.spyOn(api, "getRun").mockResolvedValue(mockPrepareRun);
    vi.spyOn(api, "application").mockResolvedValue({
      job_id: "job_01234567",
      title: "Senior Engineer",
      company: "Acme",
      url: "https://example.com/apply",
      status: "awaiting_review",
      barrier: null,
      plan: [],
      questions: [],
      answers: {},
      error: null,
      screenshot_url: "/api/hitl/job_01234567/screenshot",
      updated_at: new Date().toISOString(),
      submitted_at: null,
    });

    await store.startWorkflow({
      id: "job_01234567",
      resume_url: "/artifacts/resumes/job_01234567_resume.pdf",
      status: "tailored",
    });

    const state = useApplicationWorkflowStore.getState();
    expect(state.step).toBe("awaiting_review");
    expect(api.launchCommand).not.toHaveBeenCalledWith("tailor_one", expect.anything());
    expect(api.launchCommand).toHaveBeenCalledWith("prepare_application", expect.anything());
  });

  it("runs tailoring first if resume does not exist", async () => {
    const store = useApplicationWorkflowStore.getState();

    const mockTailorRun: CommandRun = {
      id: "run_tailor_1",
      command: "tailor_one",
      params: { job_id: "job_need_tailor" },
      status: "succeeded",
      progress: { stage: "done", done: 4, total: 4, detail: "Tailored" },
      result: { job_id: "job_need_tailor" },
      error: null,
      requested_by: "human:user",
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };

    const mockPrepareRun: CommandRun = {
      id: "run_prep_2",
      command: "prepare_application",
      params: { job_id: "job_need_tailor" },
      status: "succeeded",
      progress: { stage: "screenshot", done: 5, total: 5, detail: "Captured screenshot" },
      result: { job_id: "job_need_tailor", status: "needs_input" },
      error: null,
      requested_by: "human:user",
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };

    vi.spyOn(api, "launchCommand")
      .mockResolvedValueOnce({ run_id: "run_tailor_1", status: "queued", single_flight: false })
      .mockResolvedValueOnce({ run_id: "run_prep_2", status: "queued", single_flight: false });

    vi.spyOn(api, "getRun")
      .mockResolvedValueOnce(mockTailorRun)
      .mockResolvedValueOnce(mockPrepareRun);

    vi.spyOn(api, "application").mockResolvedValue({
      job_id: "job_need_tailor",
      title: "Dev",
      company: "Acme",
      url: "https://example.com/apply",
      status: "needs_input",
      barrier: null,
      plan: [],
      questions: [{ label: "Expected salary?", kind: "text", options: [] }],
      answers: {},
      error: null,
      screenshot_url: "/api/hitl/job_need_tailor/screenshot",
      updated_at: new Date().toISOString(),
      submitted_at: null,
    });

    await store.startWorkflow({
      id: "job_need_tailor",
      resume_url: null,
      status: "discovered",
    });

    const state = useApplicationWorkflowStore.getState();
    expect(state.step).toBe("needs_input");
    expect(api.launchCommand).toHaveBeenCalledWith("tailor_one", { job_id: "job_need_tailor" });
    expect(api.launchCommand).toHaveBeenCalledWith("prepare_application", expect.anything());
  });

  it("captures failure when tailoring step fails", async () => {
    const store = useApplicationWorkflowStore.getState();

    const mockFailedTailorRun: CommandRun = {
      id: "run_tailor_fail",
      command: "tailor_one",
      params: { job_id: "job_tailor_fail" },
      status: "failed",
      progress: { stage: "error", done: 1, total: 4, detail: "Gemini API rate limit" },
      result: null,
      error: "Gemini API rate limit exceeded",
      requested_by: "human:user",
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };

    vi.spyOn(api, "launchCommand").mockResolvedValueOnce({
      run_id: "run_tailor_fail",
      status: "queued",
      single_flight: false,
    });
    vi.spyOn(api, "getRun").mockResolvedValueOnce(mockFailedTailorRun);

    await store.startWorkflow({
      id: "job_tailor_fail",
      resume_url: null,
      status: "discovered",
    });

    const state = useApplicationWorkflowStore.getState();
    expect(state.step).toBe("failed");
    expect(state.failedStep).toBe("tailoring");
    expect(state.error).toBe("Gemini API rate limit exceeded");
  });

  it("captures failure when form filling step fails", async () => {
    const store = useApplicationWorkflowStore.getState();

    const mockFailedPrepRun: CommandRun = {
      id: "run_prep_fail",
      command: "prepare_application",
      params: { job_id: "job_prep_fail" },
      status: "failed",
      progress: { stage: "error", done: 2, total: 5, detail: "HTTP 404 at posting" },
      result: null,
      error: "HTTP 404: Job posting no longer exists",
      requested_by: "human:user",
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };

    vi.spyOn(api, "launchCommand").mockResolvedValueOnce({
      run_id: "run_prep_fail",
      status: "queued",
      single_flight: false,
    });
    vi.spyOn(api, "getRun").mockResolvedValueOnce(mockFailedPrepRun);

    await store.startWorkflow({
      id: "job_prep_fail",
      resume_url: "/artifacts/resumes/job_prep_fail_resume.pdf",
      status: "tailored",
    });

    const state = useApplicationWorkflowStore.getState();
    expect(state.step).toBe("failed");
    expect(state.failedStep).toBe("filling_form");
    expect(state.error).toBe("HTTP 404: Job posting no longer exists");
  });
});
