import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import HitlPage from "@/app/hitl/page";
import { makeApplication, mockFetch } from "./fixtures";

const NEEDS_INPUT = makeApplication({
  job_id: "job_00000001",
  company: "Initech",
  status: "needs_input",
  questions: [
    { label: "Why do you want to work here?", kind: "textarea", options: [] },
    { label: "I agree to the privacy policy", kind: "checkbox", options: [] },
    { label: "Gender", kind: "select", options: ["Male", "Female", "Decline to self-identify"] },
  ],
});
const REVIEW = makeApplication({ job_id: "job_00000002", company: "Hooli" });
const BLOCKED = makeApplication({ job_id: "job_00000003", company: "Globex", status: "blocked", barrier: "ACCOUNT_CREATION_REQUIRED", plan: [] });

function card(company: string) {
  return within(screen.getByRole("article", { name: new RegExp(company) }));
}

describe("HITL page", () => {
  it("shows an empty state", async () => {
    mockFetch(() => []);
    render(<HitlPage />);
    expect(await screen.findByText(/no interventions pending/i)).toBeInTheDocument();
  });

  it("collects answers for unanswerable questions and re-checks without submitting", async () => {
    const fetchSpy = mockFetch((url) => (url.endsWith("/answers") ? { ...NEEDS_INPUT, status: "awaiting_review", questions: [] } : [NEEDS_INPUT]));
    render(<HitlPage />);
    const c = await screen.findByRole("article", { name: /Initech/ }).then(() => card("Initech"));

    await userEvent.type(c.getByLabelText("Why do you want to work here?"), "Your mission.");
    await userEvent.click(c.getByLabelText("I agree to the privacy policy"));
    await userEvent.selectOptions(c.getByLabelText("Gender"), "Decline to self-identify");
    await userEvent.click(c.getByRole("button", { name: /save answers/i }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith("/api/hitl/job_00000001/answers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          answers: {
            "Why do you want to work here?": "Your mission.",
            "I agree to the privacy policy": "yes",
            Gender: "Decline to self-identify",
          },
        }),
      }),
    );
    expect(fetchSpy.mock.calls.some(([u]) => String(u).endsWith("/approve"))).toBe(false);
  });

  it("requires an explicit confirmation before approving", async () => {
    const fetchSpy = mockFetch((url) => (url.endsWith("/approve") ? { ...REVIEW, status: "submitted" } : [REVIEW]));
    render(<HitlPage />);
    await screen.findByRole("article", { name: /Hooli/ });
    const c = card("Hooli");
    expect(c.getByText("First Name")).toBeInTheDocument();
    expect(c.getByText("Jane")).toBeInTheDocument();

    await userEvent.click(c.getByRole("button", { name: /approve & submit/i }));
    expect(fetchSpy.mock.calls.some(([u]) => String(u).endsWith("/approve"))).toBe(false);
    expect(c.getByText(/submit to hooli\?/i)).toBeInTheDocument();

    await userEvent.click(c.getByRole("button", { name: /cancel/i }));
    expect(c.queryByText(/submit to hooli\?/i)).not.toBeInTheDocument();

    await userEvent.click(c.getByRole("button", { name: /approve & submit/i }));
    await userEvent.click(c.getByRole("button", { name: /confirm/i }));
    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith("/api/hitl/job_00000002/approve", expect.objectContaining({ method: "POST" })),
    );
    expect(await c.findByText("Submitted")).toBeInTheDocument();
  });

  it("lets the candidate resolve or skip a blocked application", async () => {
    const fetchSpy = mockFetch((url) => (url.endsWith("/resolve") ? { ...BLOCKED, status: "applied_manually" } : [BLOCKED]));
    render(<HitlPage />);
    await screen.findByRole("article", { name: /Globex/ });
    const c = card("Globex");
    expect(c.getByText(/account creation required/i)).toBeInTheDocument();
    expect(c.getByRole("link", { name: /open posting/i })).toHaveAttribute("href", BLOCKED.url);
    expect(c.getByRole("img", { name: /screenshot/i })).toHaveAttribute("src", BLOCKED.screenshot_url);

    await userEvent.click(c.getByRole("button", { name: /i applied myself/i }));
    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith("/api/hitl/job_00000003/resolve", expect.objectContaining({ method: "POST" })),
    );
  });
});
