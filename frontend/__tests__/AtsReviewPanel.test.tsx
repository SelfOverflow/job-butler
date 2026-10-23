import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AtsReviewPanel } from "@/components/AtsReviewPanel";
import type { AtsReview } from "@/lib/api";

const REVIEW: AtsReview = {
  score: 74,
  verdict: "borderline",
  requirements: [
    { requirement: "React Native", priority: "required", status: "covered", note: "Experience" },
    { requirement: "GraphQL", priority: "required", status: "missing_have_it", note: "in skills" },
    { requirement: "Kotlin", priority: "preferred", status: "gap", note: "" },
  ],
  issues: ["Exact job title missing from the summary"],
  ungrounded_claims: [],
};

describe("AtsReviewPanel", () => {
  it("shows the score, verdict, requirement coverage and recruiter issues", () => {
    render(<AtsReviewPanel review={REVIEW} />);

    expect(screen.getByRole("heading", { name: /recruiter ats review/i })).toBeInTheDocument();
    expect(screen.getByLabelText("ATS score 74 of 100")).toHaveTextContent("74");
    expect(screen.getByText("Borderline")).toBeInTheDocument();
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows.map((r) => r.textContent)).toEqual([
      "RequirementStatus",
      expect.stringContaining("React NativeCovered"),
      expect.stringContaining("GraphQLMissing (you have it)"),
      "Kotlin(preferred)Gap",
    ]);
    expect(screen.getByText("Exact job title missing from the summary")).toBeInTheDocument();
  });

  it("flags claims the reviewer could not trace to the profile", () => {
    render(<AtsReviewPanel review={{ ...REVIEW, ungrounded_claims: ["Led a team of 20"] }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Led a team of 20");
  });
});
