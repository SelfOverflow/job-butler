import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { JobDescription } from "@/components/JobDescription";

describe("JobDescription", () => {
  it("renders headings, paragraphs with line breaks, and bullet lists", () => {
    const text = "## About us\n\nWe ship fast.\nEvery day.\n\n## What you'll do\n\n- Build APIs\n- Lead";
    const { container } = render(<JobDescription text={text} />);

    expect(screen.getByRole("heading", { name: "About us" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What you'll do" })).toBeInTheDocument();
    expect(container.querySelector("p")?.innerHTML).toBe("We ship fast.<br>Every day.");
    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual(["Build APIs", "Lead"]);
  });

  it("falls back to a placeholder for empty descriptions", () => {
    render(<JobDescription text="" />);
    expect(screen.getByText(/no description provided/i)).toBeInTheDocument();
  });
});
