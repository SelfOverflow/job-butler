import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import ProfilePage from "@/app/profile/page";
import { mockFetch } from "./fixtures";

const PROFILE = {
  yaml: "personal_info:\n  full_name: Jane\n",
  profile: {
    personal_info: { full_name: "Jane Doe" },
    preferences: {
      target_roles: ["Tech Lead"],
      min_base_salary: null,
      currency: null,
      years_of_experience: null,
      excluded_employers: [],
      job_recency: "1w",
    },
  },
  errors: [],
};

describe("Profile page", () => {
  it("loads the profile and PUTs form changes", async () => {
    const fetchSpy = mockFetch((url) => (url.endsWith("/backups") ? [] : PROFILE));
    render(<ProfilePage />);

    const salary = await screen.findByLabelText(/minimum base salary/i);
    await userEvent.type(salary, "180000");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ set: { "preferences.min_base_salary": "180000" } }),
      }),
    );
  });

  it("shows file-level errors when the profile is invalid", async () => {
    const invalid = { ...PROFILE, profile: null, errors: [{ loc: "personal_info.email", msg: "bad email" }] };
    mockFetch((url) => (url.endsWith("/backups") ? [] : invalid));
    render(<ProfilePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("personal_info.email: bad email");
    expect(screen.queryByLabelText(/minimum base salary/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/profile yaml/i)).toHaveValue(PROFILE.yaml); // still fixable here
  });
});
