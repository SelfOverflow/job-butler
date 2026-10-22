import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProfileForm, type ProfileFields } from "@/components/ProfileForm";
import { ApiError } from "@/lib/api";

const INITIAL: ProfileFields = {
  target_roles: ["Technical Lead", "Senior Full-Stack Engineer"],
  min_base_salary: 3500000,
  currency: "INR",
  years_of_experience: null,
  excluded_employers: ["OakNorth", "Tejas Networks"],
};

describe("ProfileForm", () => {
  it("saves only the changed minimum salary via PUT /api/profile set", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ProfileForm initial={INITIAL} onSave={onSave} />);

    const salary = screen.getByLabelText(/minimum base salary/i);
    await userEvent.clear(salary);
    await userEvent.type(salary, "4200000");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(onSave).toHaveBeenCalledWith({ "preferences.min_base_salary": "4200000" });
    expect(await screen.findByText(/saved/i)).toBeInTheDocument();
  });

  it("encodes lists, strings, and cleared numbers as YAML values", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ProfileForm initial={INITIAL} onSave={onSave} />);

    await userEvent.type(screen.getByLabelText(/target roles/i), "\nStaff Engineer");
    await userEvent.clear(screen.getByLabelText(/currency/i));
    await userEvent.type(screen.getByLabelText(/currency/i), "EUR");
    await userEvent.type(screen.getByLabelText(/years of experience/i), "5");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(onSave).toHaveBeenCalledWith({
      "preferences.target_roles": '["Technical Lead","Senior Full-Stack Engineer","Staff Engineer"]',
      "preferences.currency": '"EUR"',
      "preferences.years_of_experience": "5",
    });
  });

  it("does not call the API when nothing changed", async () => {
    const onSave = vi.fn();
    render(<ProfileForm initial={INITIAL} onSave={onSave} />);
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText(/no changes/i)).toBeInTheDocument();
  });

  it("shows validation errors next to the field and keeps the edit", async () => {
    const onSave = vi.fn().mockRejectedValue(
      new ApiError(422, { detail: [{ loc: "preferences.currency", msg: "String should match pattern" }] }),
    );
    render(<ProfileForm initial={INITIAL} onSave={onSave} />);
    const currency = screen.getByLabelText(/currency/i);
    await userEvent.clear(currency);
    await userEvent.type(currency, "rupees");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText("String should match pattern")).toBeInTheDocument();
    expect(currency).toHaveValue("rupees");
    expect(currency).toHaveAttribute("aria-invalid", "true");
  });
});
