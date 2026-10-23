import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { isActive, resetTailorStore, useTailorStore } from "@/lib/tailorStore";
import { makeRun } from "./fixtures";


describe("tailor store", () => {
  afterEach(() => {
    resetTailorStore();
    vi.restoreAllMocks();
  });

  it("keeps the latest tailor_one run per job and ignores other commands", () => {
    const { upsert } = useTailorStore.getState();
    upsert(makeRun());
    upsert(makeRun({ id: "run_x", command: "scout_sweep", params: {} }));
    upsert(makeRun({ status: "succeeded", progress: { done: 4, total: 4 } }));

    const runs = useTailorStore.getState().runs;
    expect(Object.keys(runs)).toEqual(["job_1234abcd"]);
    expect(runs.job_1234abcd.status).toBe("succeeded");
    expect(isActive(runs.job_1234abcd)).toBe(false);
  });

  it("does not let an older run overwrite a newer one for the same job", () => {
    const { upsert } = useTailorStore.getState();
    upsert(makeRun({ id: "run_new", created_at: "2026-10-23T02:00:00" }));
    upsert(makeRun({ id: "run_old", status: "failed", created_at: "2026-10-23T01:00:00" }));
    expect(useTailorStore.getState().runs.job_1234abcd.id).toBe("run_new");
  });

  it("hydrates in-flight runs from the runs API", async () => {
    vi.spyOn(api, "runs").mockResolvedValue([makeRun(), makeRun({ id: "s", command: "scout_sweep" })]);
    await useTailorStore.getState().hydrate();
    expect(useTailorStore.getState().runs.job_1234abcd.progress.done).toBe(2);
  });

  it("starts tailoring and tracks the run returned by the server", async () => {
    vi.spyOn(api, "launchCommand").mockResolvedValue({ run_id: "run_1", status: "queued", single_flight: false });
    vi.spyOn(api, "getRun").mockResolvedValue(makeRun({ status: "queued", progress: {} }));

    await useTailorStore.getState().start("job_1234abcd");

    expect(api.launchCommand).toHaveBeenCalledWith("tailor_one", { job_id: "job_1234abcd" });
    expect(isActive(useTailorStore.getState().runs.job_1234abcd)).toBe(true);
  });
});
