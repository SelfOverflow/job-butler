// Auto-reconnecting client for the FastAPI `/ws/events` live feed.

import type { AuditEvent } from "@/lib/api";
import type { CommandRun } from "@/lib/commands";

export type FeedMessage =
  | { type: "snapshot"; events: AuditEvent[] }
  | { type: "audit"; event: AuditEvent }
  | { type: "command"; run: CommandRun };

const MIN_DELAY_MS = 1_000;
const MAX_DELAY_MS = 30_000;
const DEV_PORT = "3000";
const API_HOST = "localhost:8000";

/** Same host in production; `next dev` (port 3000) talks to FastAPI directly. */
export function eventsUrl(location: Pick<Location, "protocol" | "host">): string {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const host = location.host.endsWith(`:${DEV_PORT}`) ? API_HOST : location.host;
  return `${scheme}://${host}/ws/events`;
}

/** Connects and reconnects with exponential backoff; returns a function that stops it. */
export function connectEvents(
  onMessage: (message: FeedMessage) => void,
  onConnectionChange: (connected: boolean) => void = () => {},
): () => void {
  let socket: WebSocket | null = null;
  let delay = MIN_DELAY_MS;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;

  const open = () => {
    socket = new WebSocket(eventsUrl(window.location));
    socket.onopen = () => {
      delay = MIN_DELAY_MS;
      onConnectionChange(true);
    };
    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        onMessage(JSON.parse(event.data) as FeedMessage);
      } catch {
        // Ignore malformed frames rather than breaking the feed.
      }
    };
    socket.onclose = () => {
      onConnectionChange(false);
      if (stopped) return;
      timer = setTimeout(open, delay);
      delay = Math.min(delay * 2, MAX_DELAY_MS);
    };
  };

  open();
  return () => {
    stopped = true;
    clearTimeout(timer);
    socket?.close();
  };
}
