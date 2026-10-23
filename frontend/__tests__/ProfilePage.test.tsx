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
      job_max_age: "any",
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

  it("validates profile on button click and renders summary", async () => {
    mockFetch((url) => {
      if (url.endsWith("/validate")) {
        return {
          valid: true,
          full_name: "Jane Doe",
          bullet_count: 5,
          role_count: 2,
          star_story_count: 1,
          screening_count: 6,
        };
      }
      return url.endsWith("/backups") ? [] : PROFILE;
    });

    render(<ProfilePage />);
    const validateBtn = await screen.findByRole("button", { name: /validate profile/i });
    await userEvent.click(validateBtn);

    expect(await screen.findByText(/Valid: 2 roles, 5 bullets, 6 screening answers/i)).toBeInTheDocument();
  });

  it("tests screening question queries", async () => {
    const fetchSpy = mockFetch((url) => {
      if (url.endsWith("/query")) {
        return { question: "Legally authorized?", answer: true };
      }
      return url.endsWith("/backups") ? [] : PROFILE;
    });

    render(<ProfilePage />);
    const queryInput = await screen.findByPlaceholderText(/ask a screening question/i);
    await userEvent.type(queryInput, "Legally authorized?");
    await userEvent.click(screen.getByRole("button", { name: /test answer/i }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith("/api/profile/query", expect.objectContaining({ method: "POST" })),
    );
    expect(await screen.findByText(/Answer: true/i)).toBeInTheDocument();
  });

  it("adds a bullet point to a role", async () => {
    const fetchSpy = mockFetch((url) => {
      if (url.endsWith("/bullets")) {
        return { bullet_id: "b_test_123" };
      }
      return url.endsWith("/backups") ? [] : PROFILE;
    });

    render(<ProfilePage />);
    await userEvent.type(await screen.findByPlaceholderText(/role id/i), "exp_company_alpha");
    await userEvent.type(screen.getByPlaceholderText(/bullet text/i), "Scaled WebSocket layer");
    await userEvent.type(screen.getByPlaceholderText(/skills/i), "WebSockets, Python");
    await userEvent.click(screen.getByRole("button", { name: /add bullet/i }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith("/api/profile/bullets", expect.objectContaining({ method: "POST" })),
    );
    expect(await screen.findByText(/added bullet b_test_123/i)).toBeInTheDocument();
  });
});

