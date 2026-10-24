import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, type Application } from "@/lib/api";
import { useApplicationQuery, useApplicationsQuery } from "@/lib/queries";
import { createTestQueryClient } from "../vitest.setup";

const SAMPLE_APP: Application = {
  job_id: "job_01234567",
  title: "Senior Engineer",
  company: "Acme",
  url: "https://example.com/apply",
  status: "awaiting_review",
  barrier: null,
  plan: [{ label: "Name", kind: "text", value: "Mohit", source: "profile" }],
  questions: [],
  answers: {},
  error: null,
  screenshot_url: "/api/hitl/job_01234567/screenshot",
  updated_at: new Date().toISOString(),
  submitted_at: null,
};

function createWrapper() {
  const client = createTestQueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("Application queries", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches list of applications", async () => {
    vi.spyOn(api, "applications").mockResolvedValue([SAMPLE_APP]);

    const { result } = renderHook(() => useApplicationsQuery(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([SAMPLE_APP]);
    expect(api.applications).toHaveBeenCalledWith(undefined);
  });

  it("fetches single application by job id", async () => {
    vi.spyOn(api, "application").mockResolvedValue(SAMPLE_APP);

    const { result } = renderHook(() => useApplicationQuery("job_01234567"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(SAMPLE_APP);
    expect(api.application).toHaveBeenCalledWith("job_01234567");
  });
});
