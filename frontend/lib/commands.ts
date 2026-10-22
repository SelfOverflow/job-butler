// Typed command catalogue, run types, and client methods for the Command Center.

export type CommandStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type CommandProgress = {
  stage?: string;
  done?: number;
  total?: number;
  detail?: string;
};

export type CommandRun = {
  id: string;
  command: string;
  params: Record<string, unknown>;
  status: CommandStatus;
  progress: CommandProgress;
  result: Record<string, unknown> | null;
  error: string | null;
  requested_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type CommandDef = {
  name: string;
  label: string;
  description: string;
  defaultParams: Record<string, unknown>;
};

export const COMMAND_CATALOGUE: CommandDef[] = [
  {
    name: "scout_sweep",
    label: "Scout Sweep",
    description: "Discover fresh jobs via Firecrawl & watched companies, verify links, and save matching roles.",
    defaultParams: { limit: 20 },
  },
  {
    name: "scout_verify",
    label: "Re-verify Stored Jobs",
    description: "Re-check deep SPA liveness for all active postings; prune expired or closed jobs.",
    defaultParams: {},
  },
  {
    name: "tailor_matches",
    label: "Tailor All Matches",
    description: "Generate verified ATS resumes and cover letters for all active jobs meeting fit threshold.",
    defaultParams: { min_score: 75 },
  },
];
