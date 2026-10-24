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

  it("formats single-paragraph descriptions into sections and bullet lists", () => {
    const singlePara =
      "Accountabilities Full Stack Development: Design, develop, and maintain web apps. API Integration: Build RESTful APIs. Requirements 5+ years of software engineering experience. Strong proficiency in Python.";
    render(<JobDescription text={singlePara} />);

    expect(screen.getByRole("heading", { name: /accountabilities/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /requirements/i })).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items.length).toBeGreaterThanOrEqual(2);
    expect(items[0]).toHaveTextContent("Full Stack Development: Design, develop, and maintain web apps.");
  });

  it("renders mixed intro text and bullet lists within the same block", () => {
    const mixed = "Here is what we need:\n- React proficiency\n- Python experience";
    render(<JobDescription text={mixed} />);

    expect(screen.getByText("Here is what we need:")).toBeInTheDocument();
    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual(["React proficiency", "Python experience"]);
  });

  it("renders inline bold and clickable links", () => {
    const markdown = "Visit https://jobbutler.dev for **awesome** documentation.";
    const { container } = render(<JobDescription text={markdown} />);

    const link = screen.getByRole("link", { name: "https://jobbutler.dev" });
    expect(link).toHaveAttribute("href", "https://jobbutler.dev");
    expect(container.querySelector("strong")?.textContent).toBe("awesome");
  });
});
