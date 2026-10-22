import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/Sidebar";

let currentPathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => currentPathname,
}));

describe("Sidebar", () => {
  it("highlights only Run history when pathname is /runs/", () => {
    currentPathname = "/runs/";
    render(<Sidebar />);

    const runHistoryLink = screen.getByRole("link", { name: /run history/i });
    const commandsLink = screen.getByRole("link", { name: /commands/i });

    expect(runHistoryLink).toHaveAttribute("aria-current", "page");
    expect(commandsLink).not.toHaveAttribute("aria-current");
  });

  it("highlights only Commands when pathname is /run/", () => {
    currentPathname = "/run/";
    render(<Sidebar />);

    const runHistoryLink = screen.getByRole("link", { name: /run history/i });
    const commandsLink = screen.getByRole("link", { name: /commands/i });

    expect(commandsLink).toHaveAttribute("aria-current", "page");
    expect(runHistoryLink).not.toHaveAttribute("aria-current");
  });

  it("highlights only Dashboard when pathname is /", () => {
    currentPathname = "/";
    render(<Sidebar />);

    const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
    const commandsLink = screen.getByRole("link", { name: /commands/i });

    expect(dashboardLink).toHaveAttribute("aria-current", "page");
    expect(commandsLink).not.toHaveAttribute("aria-current");
  });
});
