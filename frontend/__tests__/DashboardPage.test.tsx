import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Dashboard from "@/app/page";
import { FakeWebSocket, makeEvent, makeJob, mockFetch } from "./fixtures";

describe("Dashboard", () => {
  beforeEach(() => vi.stubGlobal("WebSocket", FakeWebSocket));
  afterEach(() => vi.unstubAllGlobals());

  it("shows job metrics, the last sweep, top matches, and the live feed", async () => {
    mockFetch((url) =>
      url.startsWith("/api/jobs")
        ? [
            makeJob({ id: "job_00000001", title: "Lead Mobile Engineer", score: 90 }),
            makeJob({ id: "job_00000002", title: "Tech Lead", score: 70, resume_url: null }),
          ]
        : { items: [makeEvent({ details: { discovered: 412, saved: 19, new: 7, errors: [] } })], next_offset: null },
    );
    render(<Dashboard />);

    const metric = async (label: string) => within((await screen.findByText(label)).closest("div")!);
    expect((await metric("Active jobs")).getByText("2")).toBeInTheDocument();
    expect((await metric("Tailored")).getByText("1")).toBeInTheDocument();
    expect((await metric("Average fit")).getByText("80")).toBeInTheDocument();
    expect(await screen.findByText(/412 discovered → 19 saved \(7 new\)/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Lead Mobile Engineer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Live feed" })).toBeInTheDocument();
  });

  it("explains how to get started when nothing has run yet", async () => {
    mockFetch((url) => (url.startsWith("/api/jobs") ? [] : { items: [], next_offset: null }));
    render(<Dashboard />);
    expect(await screen.findByText(/no sweep yet/i)).toBeInTheDocument();
  });
});
