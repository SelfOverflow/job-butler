import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import AuditPage from "@/app/audit/page";
import { makeEvent, mockFetch } from "./fixtures";

describe("Audit page", () => {
  it("passes filters to the API and pages with Load more", async () => {
    const fetchSpy = mockFetch((url) =>
      url.includes("offset=50")
        ? { items: [makeEvent({ id: "late", action: "LINK_VERIFIED" })], next_offset: null }
        : { items: [makeEvent()], next_offset: 50 },
    );
    render(<AuditPage />);

    const table = () => within(screen.getByRole("table"));
    await screen.findByRole("table");
    expect(table().getByText("SCOUT_SWEEP")).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenLastCalledWith("/api/audit?limit=50&offset=0", undefined);

    await userEvent.click(screen.getByRole("button", { name: /load more/i }));
    await waitFor(() => expect(table().getByText("LINK_VERIFIED")).toBeInTheDocument());
    expect(table().getByText("SCOUT_SWEEP")).toBeInTheDocument(); // appended, not replaced
    expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByRole("combobox", { name: /status/i }), "FAILURE");
    await waitFor(() =>
      expect(fetchSpy).toHaveBeenLastCalledWith("/api/audit?status=FAILURE&limit=50&offset=0", undefined),
    );
  });
});
