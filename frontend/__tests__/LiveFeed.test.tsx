import { act, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveFeed } from "@/components/LiveFeed";
import { FakeWebSocket, makeEvent } from "./fixtures";

describe("LiveFeed", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows the snapshot, then prepends live events as they arrive", () => {
    render(<LiveFeed />);
    expect(screen.getByText(/reconnecting/i)).toBeInTheDocument();

    act(() => {
      FakeWebSocket.latest().open();
      FakeWebSocket.latest().emit({ type: "snapshot", events: [makeEvent({ id: "old", action: "SCOUT_SWEEP" })] });
    });
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("SCOUT_SWEEP")).toBeInTheDocument();

    act(() => {
      FakeWebSocket.latest().emit({
        type: "audit",
        event: makeEvent({ id: "new", actor: "agent:tailor", action: "RESUME_TAILORED", target_id: "job_1" }),
      });
    });
    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("RESUME_TAILORED");
    expect(items[0]).toHaveTextContent("job_1");
    expect(items[1]).toHaveTextContent("SCOUT_SWEEP");
  });

  it("keeps at most 50 events and closes the socket on unmount", () => {
    const { unmount } = render(<LiveFeed />);
    act(() => {
      for (let i = 0; i < 60; i++) FakeWebSocket.latest().emit({ type: "audit", event: makeEvent({ id: `e${i}` }) });
    });
    expect(within(screen.getByRole("list")).getAllByRole("listitem")).toHaveLength(50);
    unmount();
    expect(FakeWebSocket.latest().closed).toBe(true);
  });
});
