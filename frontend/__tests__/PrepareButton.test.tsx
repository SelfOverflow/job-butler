import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { JobCard } from "@/components/JobCard";
import { makeApplication, makeJob, mockFetch } from "./fixtures";

describe("Prepare application button", () => {
  it("prepares the application and links to the review queue", async () => {
    const fetchSpy = mockFetch(() => makeApplication({ status: "needs_input" }));
    render(<JobCard job={makeJob()} />);

    await userEvent.click(screen.getByRole("button", { name: /prepare application/i }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith("/api/hitl/job_1234abcd/prepare", { method: "POST" }),
    );
    expect(await screen.findByText(/needs your answers/i)).toBeInTheDocument();
    // next/link drops the trailing slash outside the static-export build (trailingSlash: true).
    expect(screen.getByRole("link", { name: /review/i }).getAttribute("href")).toMatch(/^\/hitl\/?$/);
  });

  it("is only offered once the job has a tailored resume", () => {
    render(<JobCard job={makeJob({ resume_url: null })} />);
    expect(screen.queryByRole("button", { name: /prepare application/i })).not.toBeInTheDocument();
  });

  it("shows refusals from the API", async () => {
    mockFetch(() => ({ detail: "Application already submitted" }), 409);
    render(<JobCard job={makeJob()} />);
    await userEvent.click(screen.getByRole("button", { name: /prepare application/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Application already submitted");
  });
});
