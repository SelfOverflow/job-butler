import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AuditLogViewer } from "@/components/AuditLogViewer";
import { makeEvent } from "./fixtures";

const EVENTS = [
  makeEvent(),
  makeEvent({ id: "e2", actor: "human:user", action: "PROFILE_UPDATED", status: "WARNING", duration_ms: null }),
  makeEvent({
    id: "e3",
    actor: "agent:tailor",
    action: "RESUME_TAILORED",
    status: "FAILURE",
    target_id: "job_1234abcd",
    details: { error: "bullet ids not in the profile: b_x" },
  }),
];

describe("AuditLogViewer", () => {
  it("renders actor tags, action badges, status, target and duration", () => {
    render(<AuditLogViewer events={EVENTS} />);
    const rows = screen.getAllByRole("row").slice(1); // skip header
    expect(rows).toHaveLength(3);

    expect(within(rows[0]).getByText("agent:scout")).toBeInTheDocument();
    expect(within(rows[0]).getByText("SCOUT_SWEEP")).toBeInTheDocument();
    expect(within(rows[0]).getByText("1.5 s")).toBeInTheDocument();
    expect(within(rows[1]).getByText("human:user").className).toContain("violet");
    expect(within(rows[2]).getByText("FAILURE").className).toContain("red");
    expect(within(rows[2]).getByText("job_1234abcd")).toBeInTheDocument();
  });

  it("opens a drawer with the event's JSON details and closes it", async () => {
    render(<AuditLogViewer events={EVENTS} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(screen.getByText("RESUME_TAILORED"));
    const drawer = screen.getByRole("dialog", { name: /RESUME_TAILORED/ });
    expect(within(drawer).getByText(/"error": "bullet ids not in the profile: b_x"/)).toBeInTheDocument();

    await userEvent.click(within(drawer).getByRole("button", { name: /close/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<AuditLogViewer events={[]} />);
    expect(screen.getByText(/no events/i)).toBeInTheDocument();
  });
});
