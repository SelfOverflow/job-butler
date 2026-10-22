"use client";

import { useEffect, useState } from "react";

import { ActorTag, StatusBadge, formatTime } from "@/components/AuditLogViewer";
import type { AuditEvent } from "@/lib/api";
import { connectEvents } from "@/lib/websocket";

const MAX_EVENTS = 50;

export function useLiveEvents(): { events: AuditEvent[]; connected: boolean } {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(
    () =>
      connectEvents((message) => {
        if (message.type === "snapshot") setEvents(message.events.slice(0, MAX_EVENTS));
        else setEvents((current) => [message.event, ...current].slice(0, MAX_EVENTS));
      }, setConnected),
    [],
  );
  return { events, connected };
}

export function LiveFeed() {
  const { events, connected } = useLiveEvents();
  return (
    <section aria-labelledby="live-feed-title" className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <header className="flex items-center justify-between">
        <h2 id="live-feed-title" className="font-semibold">Live feed</h2>
        <span className="flex items-center gap-1.5 text-xs text-zinc-500">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "animate-pulse bg-amber-500"}`} />
          {connected ? "Live" : "Reconnecting…"}
        </span>
      </header>
      {events.length === 0 && <p className="text-sm text-zinc-500">Waiting for activity…</p>}
      <ul className="flex flex-col divide-y divide-zinc-100 dark:divide-zinc-800">
        {events.map((event, i) => (
          <li
            key={event.id}
            className={`flex flex-wrap items-center gap-2 py-2 text-sm ${i === 0 ? "animate-[pulse_1s_ease-out_1]" : ""}`}
          >
            <span className="w-40 shrink-0 text-xs text-zinc-500">{formatTime(event.timestamp)}</span>
            <ActorTag actor={event.actor} />
            <span className="font-mono text-xs">{event.action}</span>
            {event.target_id && <span className="font-mono text-xs text-zinc-500">{event.target_id}</span>}
            <span className="ml-auto"><StatusBadge status={event.status} /></span>
          </li>
        ))}
      </ul>
    </section>
  );
}
