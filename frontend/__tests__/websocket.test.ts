import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { connectEvents, eventsUrl } from "@/lib/websocket";
import { FakeWebSocket } from "./fixtures";

describe("connectEvents", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("parses messages and reports connection state", () => {
    const messages: unknown[] = [];
    const states: boolean[] = [];
    connectEvents((m) => messages.push(m), (s) => states.push(s));

    FakeWebSocket.latest().open();
    FakeWebSocket.latest().emit({ type: "snapshot", events: [] });
    expect(messages).toEqual([{ type: "snapshot", events: [] }]);
    expect(states).toEqual([true]);
  });

  it("reconnects automatically with exponential backoff, reset after a successful open", () => {
    connectEvents(() => {});
    FakeWebSocket.latest().drop();
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);

    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(1999);
    expect(FakeWebSocket.instances).toHaveLength(2); // second retry waits 2 s
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);

    FakeWebSocket.latest().open(); // success resets the backoff
    FakeWebSocket.latest().drop();
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(4);
  });

  it("stops reconnecting once closed by the caller", () => {
    const close = connectEvents(() => {});
    close();
    expect(FakeWebSocket.latest().closed).toBe(true);
    vi.advanceTimersByTime(60_000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("ignores malformed messages", () => {
    const messages: unknown[] = [];
    connectEvents((m) => messages.push(m));
    FakeWebSocket.latest().onmessage?.({ data: "not json" });
    expect(messages).toEqual([]);
  });
});

describe("eventsUrl", () => {
  it.each([
    ["http:", "localhost:3000", "ws://localhost:8000/ws/events"], // next dev -> FastAPI
    ["http:", "localhost:8000", "ws://localhost:8000/ws/events"],
    ["https:", "butler.example.com", "wss://butler.example.com/ws/events"],
  ])("%s//%s -> %s", (protocol, host, expected) => {
    expect(eventsUrl({ protocol, host } as Location)).toBe(expected);
  });
});
