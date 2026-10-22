import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CommandCard } from "@/components/CommandCard";
import { CommandDef, CommandRun } from "@/lib/commands";

const mockDef: CommandDef = {
  name: "scout_sweep",
  label: "Scout Sweep",
  description: "Discover fresh job postings and verify links.",
  defaultParams: { limit: 20 },
};

describe("CommandCard", () => {
  it("renders command details and form", () => {
    render(
      <CommandCard
        command={mockDef}
        onLaunch={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText("Scout Sweep")).toBeInTheDocument();
    expect(screen.getByText("Discover fresh job postings and verify links.")).toBeInTheDocument();
    expect(screen.getByLabelText("limit:")).toHaveValue(20);
    expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
  });

  it("submits parameters on run click", async () => {
    const onLaunch = vi.fn().mockResolvedValue(undefined);
    render(
      <CommandCard
        command={mockDef}
        onLaunch={onLaunch}
        onCancel={vi.fn()}
      />
    );

    const input = screen.getByLabelText("limit:");
    fireEvent.change(input, { target: { value: "35" } });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(onLaunch).toHaveBeenCalledWith("scout_sweep", { limit: 35 });
  });

  it("renders stage bars and cancel button when running", () => {
    const onCancel = vi.fn().mockResolvedValue(undefined);
    const activeRun: CommandRun = {
      id: "run-123",
      command: "scout_sweep",
      params: { limit: 20 },
      status: "running",
      progress: { stage: "search", done: 4, total: 10, detail: "querying Firecrawl" },
      result: null,
      error: null,
      requested_by: "human:user",
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      finished_at: null,
    };

    render(
      <CommandCard
        command={mockDef}
        activeRun={activeRun}
        onLaunch={vi.fn()}
        onCancel={onCancel}
      />
    );

    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("search")).toBeInTheDocument();
    expect(screen.getByText("4 / 10 (40%)")).toBeInTheDocument();
    expect(screen.getByText("querying Firecrawl")).toBeInTheDocument();

    const cancelBtn = screen.getByRole("button", { name: "Cancel" });
    fireEvent.click(cancelBtn);
    expect(onCancel).toHaveBeenCalledWith("run-123");
  });
});
