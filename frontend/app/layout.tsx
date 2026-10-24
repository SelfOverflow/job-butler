import type { Metadata } from "next";
import "./globals.css";

import { Providers } from "@/components/Providers";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Job Butler",
  description: "Autonomous job discovery, tailoring, and applications",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-zinc-50 text-zinc-900 md:flex-row dark:bg-zinc-950 dark:text-zinc-100">
        <Providers>
          <Sidebar />
          <main className="flex-1 p-4 md:p-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
