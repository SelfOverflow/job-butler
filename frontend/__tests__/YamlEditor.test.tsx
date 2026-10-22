import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BackupList } from "@/components/BackupList";
import { YamlEditor } from "@/components/YamlEditor";
import { ApiError } from "@/lib/api";

const YAML = "personal_info:\n  full_name: Jane\n";

describe("YamlEditor", () => {
  it("saves the edited text verbatim", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<YamlEditor initial={YAML} onSave={onSave} />);
    const save = screen.getByRole("button", { name: /save yaml/i });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/profile yaml/i), { target: { value: `${YAML}# note\n` } });
    expect(save).toBeEnabled();
    await userEvent.click(save);

    expect(onSave).toHaveBeenCalledWith(`${YAML}# note\n`);
    expect(await screen.findByText(/saved/i)).toBeInTheDocument();
  });

  it("lists validation errors by field and keeps the text", async () => {
    const error = new ApiError(422, {
      detail: [
        { loc: "personal_info.email", msg: "value is not a valid email address" },
        { loc: "", msg: "Invalid YAML: mapping values are not allowed" },
      ],
    });
    render(<YamlEditor initial={YAML} onSave={vi.fn().mockRejectedValue(error)} />);
    fireEvent.change(screen.getByLabelText(/profile yaml/i), { target: { value: "bad: [" } });
    await userEvent.click(screen.getByRole("button", { name: /save yaml/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("personal_info.email: value is not a valid email address");
    expect(alert).toHaveTextContent("Invalid YAML: mapping values are not allowed");
    expect(screen.getByLabelText(/profile yaml/i)).toHaveValue("bad: [");
  });
});

describe("BackupList", () => {
  it("lists backups newest first and restores on click", async () => {
    const onRestore = vi.fn().mockResolvedValue(undefined);
    const backups = [
      { name: "candidate_profile_20261022_093015.yaml", modified: "2026-10-22T09:30:15" },
      { name: "candidate_profile_20261023_101500.yaml", modified: "2026-10-23T10:15:00" },
    ];
    render(<BackupList backups={backups} onRestore={onRestore} />);

    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("candidate_profile_20261023_101500.yaml");
    await userEvent.click(screen.getAllByRole("button", { name: /^restore$/i })[1]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /confirm restore/i }));
    expect(onRestore).toHaveBeenCalledWith("candidate_profile_20261022_093015.yaml");
    expect(await screen.findByText(/restored candidate_profile_20261022_093015/i)).toBeInTheDocument();
  });

  it("explains when there are no backups", () => {
    render(<BackupList backups={[]} onRestore={vi.fn()} />);
    expect(screen.getByText(/no backups yet/i)).toBeInTheDocument();
  });
});
