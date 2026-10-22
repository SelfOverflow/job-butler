import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import RunsPage from "@/app/runs/page";
import { api } from "@/lib/api";
import { CommandRun } from "@/lib/commands";

vi.mock("@/lib/api", () => ({
  api: {
    runs: vi.fn(),
  },
}));

const mockRuns: CommandRun[] = [
  {
    id: "run-abc",
    command: "scout_sweep",
    params: { limit: 10 },
    status: "succeeded",
    progress: {},
    result: { saved: 3 },
    error: null,
    requested_by: "human:user",
    created_at: "2026-10-22T10:00:00Z",
    started_at: "2026-10-22T10:00:01Z",
    finished_at: "2026-10-22T10:00:05Z",
  },
];

describe("RunsPage", () => {
  beforeEach(() => {
    vi.mocked(api.runs).mockResolvedValue(mockRuns);
  });

  it("lists runs and opens drawer on inspect click", async () => {
    render(<RunsPage />);

    expect(await screen.findByText("scout_sweep")).toBeInTheDocument();
    expect(screen.getByText("succeeded")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));

    // Drawer opens
    expect(screen.getByText("run-abc")).toBeInTheDocument();
    expect(screen.getByText("Parameters")).toBeInTheDocument();
    expect(screen.getByText("Result")).toBeInTheDocument();

    // Close drawer
    fireEvent.click(screen.getByRole("button", { name: "Close drawer" }));
    await waitFor(() => {
      expect(screen.queryByText("run-abc")).not.toBeInTheDocument();
    });
  });
});
