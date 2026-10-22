import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import SettingsPage from "@/app/settings/page";
import LoginPage from "@/app/login/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    settings: vi.fn(),
  },
}));

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/",
}));

describe("SettingsPage", () => {
  it("renders configuration status without secrets", async () => {
    vi.mocked(api.settings).mockResolvedValue({
      auth_enabled: true,
      gemini_model: "gemini-3.8-flash",
      gemini_configured: true,
      firecrawl_configured: false,
      openai_configured: false,
      anthropic_configured: false,
      max_daily_scrape_credits: 100,
    });

    render(<SettingsPage />);

    expect(await screen.findByText(/Gemini API \(gemini-3.8-flash\)/)).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
  });
});

describe("LoginPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
  });

  it("submits password and redirects on success", async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "authenticated", csrf_token: "csrf-xyz" }),
    } as Response);

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret123" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/");
    });
  });

  it("shows rate limit error on 429", async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ detail: "Rate limited" }),
    } as Response);

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText(/Too many failed login attempts/)).toBeInTheDocument();
  });
});
