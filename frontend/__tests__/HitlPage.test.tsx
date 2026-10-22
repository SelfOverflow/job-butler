import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HitlPage from "@/app/hitl/page";

describe("HITL page", () => {
  it("explains that interventions arrive with auto-apply", () => {
    render(<HitlPage />);
    expect(screen.getByRole("heading", { name: /interventions/i })).toBeInTheDocument();
    expect(screen.getByText(/no interventions pending/i)).toBeInTheDocument();
  });
});
