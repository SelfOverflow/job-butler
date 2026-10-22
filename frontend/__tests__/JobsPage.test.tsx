import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import JobsPage from "@/app/jobs/page";
import { hoursAgo, makeJob, mockFetch } from "./fixtures";

const JOBS = [
  makeJob({ id: "job_00000001", title: "Lead Mobile Engineer", company: "Klarna", location: "Stockholm", score: 92 }),
  makeJob({ id: "job_00000002", title: "Tech Lead", company: "Razorpay", location: "Bengaluru", score: 61 }),
];

describe("Jobs page", () => {
  it("lists jobs from the API and filters by search text", async () => {
    const fetchSpy = mockFetch(() => JOBS);
    render(<JobsPage />);

    expect(await screen.findByText("Lead Mobile Engineer")).toBeInTheDocument();
    expect(screen.getByText("Tech Lead")).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith("/api/jobs", undefined);

    await userEvent.type(screen.getByRole("searchbox", { name: /search/i }), "razor");
    expect(screen.queryByText("Lead Mobile Engineer")).not.toBeInTheDocument();
    expect(screen.getByText("Tech Lead")).toBeInTheDocument();
    expect(screen.getByText("1 of 2 jobs")).toBeInTheDocument();
  });

  it("filters by minimum score", async () => {
    mockFetch(() => JOBS);
    render(<JobsPage />);
    await screen.findByText("Tech Lead");

    await userEvent.selectOptions(screen.getByRole("combobox", { name: /minimum score/i }), "80");
    expect(screen.queryByText("Tech Lead")).not.toBeInTheDocument();
    expect(screen.getByText("Lead Mobile Engineer")).toBeInTheDocument();
  });

  it("shows an empty state and an error state", async () => {
    mockFetch(() => []);
    const { unmount } = render(<JobsPage />);
    expect(await screen.findByText(/no jobs yet/i)).toBeInTheDocument();
    unmount();

    mockFetch(() => ({ detail: "boom" }), 500);
    render(<JobsPage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/500/));
  });

  it("filters by how recently jobs were posted", async () => {
    mockFetch(() => [
      makeJob({ id: "job_00000011", title: "Fresh Role", posted_at: hoursAgo(3) }),
      makeJob({ id: "job_00000012", title: "Two Day Role", posted_at: hoursAgo(40) }),
      makeJob({ id: "job_00000013", title: "Old Role", posted_at: hoursAgo(24 * 20) }),
      makeJob({ id: "job_00000014", title: "Undated Role", posted_at: null, discovered_at: hoursAgo(2) }),
    ]);
    render(<JobsPage />);
    await screen.findByText("Old Role");

    const recency = screen.getByRole("combobox", { name: /posted within/i });
    await userEvent.selectOptions(recency, "24h");
    expect(screen.getByText("Fresh Role")).toBeInTheDocument();
    expect(screen.getByText("Undated Role")).toBeInTheDocument(); // falls back to when it was found
    expect(screen.queryByText("Two Day Role")).not.toBeInTheDocument();
    expect(screen.queryByText("Old Role")).not.toBeInTheDocument();

    await userEvent.selectOptions(recency, "48h");
    expect(screen.getByText("Two Day Role")).toBeInTheDocument();
    await userEvent.selectOptions(recency, "any");
    expect(screen.getByText("Old Role")).toBeInTheDocument();
  });
});
