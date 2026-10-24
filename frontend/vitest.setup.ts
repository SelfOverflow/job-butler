import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup } from "@testing-library/react";
import React from "react";
import { afterEach, vi } from "vitest";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

vi.mock("@testing-library/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@testing-library/react")>();
  return {
    ...actual,
    render: (ui: React.ReactElement, options?: Parameters<typeof actual.render>[1]) => {
      const client = createTestQueryClient();
      const Wrapper = ({ children }: { children: React.ReactNode }) => {
        const inner = options?.wrapper ? React.createElement(options.wrapper, null, children) : children;
        return React.createElement(QueryClientProvider, { client }, inner);
      };
      return actual.render(ui, { ...options, wrapper: Wrapper });
    },
  };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
