"use client";

import { Monitor, Terminal } from "lucide-react";
import React, { useEffect } from "react";

import { useApplicationWorkflowStore } from "@/lib/applicationWorkflowStore";
import { connectEvents } from "@/lib/websocket";

export function LiveExecutionFeed() {
  const {
    progressDone,
    progressTotal,
    logs,
    updateFromRun,
    isHeaded,
    setHeaded,
  } = useApplicationWorkflowStore();

  useEffect(() => {
    return connectEvents((msg) => {
      if (msg.type === "command") {
        updateFromRun(msg.run);
      }
    });
  }, [updateFromRun]);

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-zinc-200 bg-zinc-950 p-4 font-mono text-xs text-zinc-300 dark:border-zinc-800 shadow-sm">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-2.5">
        <div className="flex items-center gap-2 text-zinc-400">
          <Terminal size={14} />
          <span className="font-semibold text-zinc-200">Playwright Navigator Live Stream</span>
          {progressTotal > 0 && (
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300">
              {progressDone}/{progressTotal}
            </span>
          )}
        </div>

        <label className="flex items-center gap-1.5 cursor-pointer text-zinc-400 hover:text-zinc-200">
          <Monitor size={12} />
          <input
            type="checkbox"
            checked={isHeaded}
            onChange={(e) => setHeaded(e.target.checked)}
            className="rounded border-zinc-700 bg-zinc-900 text-sky-600 focus:ring-0"
          />
          <span className="text-[11px]">Visible window (headed)</span>
        </label>
      </div>

      <div className="flex flex-col gap-1.5 py-1 min-h-[90px] max-h-[160px] overflow-y-auto">
        {logs.length === 0 ? (
          <p className="text-zinc-500 italic">Awaiting navigation and DOM actions…</p>
        ) : (
          logs.map((log, index) => (
            <p key={index} className="leading-relaxed">
              <span className="text-emerald-400">› </span>
              {log}
            </p>
          ))
        )}
      </div>
    </div>
  );
}
