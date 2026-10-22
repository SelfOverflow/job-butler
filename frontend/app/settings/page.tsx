"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CheckCircle2, XCircle } from "lucide-react";

type SettingsData = {
  auth_enabled: boolean;
  gemini_model: string;
  gemini_configured: boolean;
  firecrawl_configured: boolean;
  openai_configured: boolean;
  anthropic_configured: boolean;
  max_daily_scrape_credits: number;
};

export default function SettingsPage() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .settings()
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-xs text-zinc-500">Loading settings...</p>;
  if (!data) return <p className="text-xs text-rose-500">Failed to load settings.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">Settings & Integrations</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Inspection of system configurations. Secret API keys and private tokens are never returned by any endpoint.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">LLM Provider Configuration</h2>
          <div className="mt-4 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Gemini API ({data.gemini_model}):</span>
              <StatusIcon configured={data.gemini_configured} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">OpenAI API:</span>
              <StatusIcon configured={data.openai_configured} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Anthropic API:</span>
              <StatusIcon configured={data.anthropic_configured} />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="font-semibold text-zinc-900 dark:text-zinc-100">Scraping & Security</h2>
          <div className="mt-4 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Firecrawl Scraper:</span>
              <StatusIcon configured={data.firecrawl_configured} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Daily Scrape Credits Limit:</span>
              <span className="font-mono font-medium">{data.max_daily_scrape_credits}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Dashboard Authentication:</span>
              <span
                className={`rounded px-1.5 py-0.5 font-medium ${
                  data.auth_enabled
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400"
                    : "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400"
                }`}
              >
                {data.auth_enabled ? "Enabled" : "Disabled (Loopback Only)"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusIcon({ configured }: { configured: boolean }) {
  return configured ? (
    <span className="flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
      <CheckCircle2 size={16} /> Configured
    </span>
  ) : (
    <span className="flex items-center gap-1 text-zinc-400">
      <XCircle size={16} /> Not configured
    </span>
  );
}
