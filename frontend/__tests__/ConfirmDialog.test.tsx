import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "@/components/ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders nothing when open is false", () => {
    render(
      <ConfirmDialog
        open={false}
        title="Submit application?"
        description="This will send your details to Acme Corp."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders title, description and actions when open", () => {
    render(
      <ConfirmDialog
        open={true}
        title="Submit application?"
        description="This will send your details to Acme Corp."
        confirmLabel="Yes, submit"
        cancelLabel="Never mind"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Submit application?" })).toBeInTheDocument();
    expect(screen.getByText("This will send your details to Acme Corp.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yes, submit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Never mind" })).toBeInTheDocument();
  });

  it("calls onConfirm when confirm button is clicked", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open={true}
        title="Restore backup?"
        description="Current profile will be backed up."
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onCancel when cancel button is clicked or Escape key pressed", () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open={true}
        title="Restore backup?"
        description="Current profile will be backed up."
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it("disables buttons and shows busy state when busy", () => {
    render(
      <ConfirmDialog
        open={true}
        busy={true}
        title="Submitting..."
        description="Submitting application."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /confirm/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
  });
});
