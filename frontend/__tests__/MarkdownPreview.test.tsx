import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MarkdownPreview } from "@/components/MarkdownPreview";

const SAMPLE_MD = `# Jane Doe

jane@example.com | +1 555-0100 | https://linkedin.com/in/janedoe

## Professional Experience

### Mobile Fullstack Engineer II, OakNorth
Jul 2025 - Present | Gurugram, India

- Built **high-scale** mobile apps with React Native.
- Automated CI/CD pipelines.
`;

describe("MarkdownPreview", () => {
  it("renders structured markdown headings, links, and bold elements", () => {
    render(<MarkdownPreview markdown={SAMPLE_MD} />);

    expect(screen.getByRole("heading", { level: 1, name: "Jane Doe" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Professional Experience" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: /Mobile Fullstack Engineer II/i })).toBeInTheDocument();
    expect(screen.getByText("high-scale")).toHaveClass("font-semibold");
    expect(screen.getByRole("link", { name: "https://linkedin.com/in/janedoe" })).toHaveAttribute(
      "href",
      "https://linkedin.com/in/janedoe",
    );
    expect(screen.getByText("Automated CI/CD pipelines.")).toBeInTheDocument();
  });

  it("toggles between rendered and raw markdown views", async () => {
    render(<MarkdownPreview markdown={SAMPLE_MD} />);

    // Initially in rendered mode
    expect(screen.queryByText(/Jul 2025 - Present \| Gurugram, India/)).toBeInTheDocument();

    // Click Raw
    await userEvent.click(screen.getByRole("button", { name: /raw/i }));
    const pre = screen.getByText((_, el) => el?.tagName === "PRE");
    expect(pre.textContent).toBe(SAMPLE_MD);

    // Click Rendered
    await userEvent.click(screen.getByRole("button", { name: /rendered/i }));
    expect(screen.queryByText((_, el) => el?.tagName === "PRE")).not.toBeInTheDocument();
  });

  it("handles copy to clipboard", async () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: writeTextSpy },
    });

    render(<MarkdownPreview markdown={SAMPLE_MD} />);
    const copyButton = screen.getByRole("button", { name: /copy/i });
    await userEvent.click(copyButton);

    expect(writeTextSpy).toHaveBeenCalledWith(SAMPLE_MD);
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });
});
