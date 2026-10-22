import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import AnalyticsPage from "@/app/analytics/page";
import { mockFetch } from "./fixtures";

const TRENDS = {
  created_at: "2026-10-22T07:50:00",
  total: 412,
  matched: 34,
  threshold: 60,
  demand: [
    { skill: "Python", postings: 346, share: 84.0, have: true },
    { skill: "Kubernetes", postings: 210, share: 51.0, have: false },
  ],
};
const UPSKILL = {
  created_at: "2026-10-22T07:50:00",
  matched: 34,
  threshold: 60,
  upskill: [
    { skill: "Kubernetes", unlocks: 14, demand: 210, uplift_pct: 41.2 },
    { skill: "Terraform", unlocks: 8, demand: 120, uplift_pct: 23.5 },
  ],
};

function mockAnalytics(trends: unknown = TRENDS, upskill: unknown = UPSKILL) {
  return mockFetch((url) => (url.endsWith("/trends") ? trends : upskill));
}

describe("Analytics page", () => {
  it("shows headline tiles, demand with have/missing identity, and upskilling ROI", async () => {
    mockAnalytics();
    render(<AnalyticsPage />);

    const tiles = await screen.findByRole("list", { name: /market summary/i });
    expect(within(tiles).getByText("412")).toBeInTheDocument();
    expect(within(tiles).getByText("34")).toBeInTheDocument();

    const demand = within(screen.getByRole("figure", { name: /most demanded/i }));
    expect(demand.getByText("Python")).toBeInTheDocument();
    expect(demand.getByText("84%")).toBeInTheDocument();
    expect(demand.getByText("✓")).toBeInTheDocument();
    expect(demand.getByText("✗")).toBeInTheDocument();
    expect(demand.getByText("You have it")).toBeInTheDocument(); // legend for 2 identities
    expect(demand.getByText("Missing")).toBeInTheDocument();

    const roi = within(screen.getByRole("figure", { name: /upskilling/i }));
    expect(roi.getByText("+14 roles")).toBeInTheDocument();
    expect(roi.queryByText("You have it")).not.toBeInTheDocument(); // single series: no legend
  });

  it("shows a tooltip on keyboard focus with the value first", async () => {
    mockAnalytics();
    render(<AnalyticsPage />);
    const roi = within(await screen.findByRole("figure", { name: /upskilling/i }));
    fireEvent.focus(roi.getByRole("listitem", { name: /Kubernetes/ }));
    const tip = roi.getByRole("tooltip");
    expect(tip).toHaveTextContent("+14 roles");
    expect(tip).toHaveTextContent("+41.2% vs 34 matched");
    expect(tip).toHaveTextContent("in 210 postings");
  });

  it("offers a table view of each chart", async () => {
    mockAnalytics();
    render(<AnalyticsPage />);
    const demand = within(await screen.findByRole("figure", { name: /most demanded/i }));
    await userEvent.click(demand.getByRole("button", { name: /show table/i }));
    const rows = demand.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Python");
    expect(rows[1]).toHaveTextContent("346");
    expect(rows[1]).toHaveTextContent("Yes");
  });

  it("explains what to do before the first sweep", async () => {
    mockAnalytics({ ...TRENDS, created_at: null, demand: [] }, { ...UPSKILL, created_at: null, upskill: [] });
    render(<AnalyticsPage />);
    expect(await screen.findByText(/no market snapshot yet/i)).toBeInTheDocument();
  });
});
