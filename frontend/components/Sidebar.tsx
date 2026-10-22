"use client";

import { Activity, BarChart3, Briefcase, Hand, History, LayoutDashboard, Settings as SettingsIcon, Terminal, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs/", label: "Jobs", icon: Briefcase },
  { href: "/run/", label: "Commands", icon: Terminal },
  { href: "/runs/", label: "Run history", icon: History },
  { href: "/analytics/", label: "Analytics", icon: BarChart3 },
  { href: "/profile/", label: "Profile", icon: UserRound },
  { href: "/audit/", label: "Audit log", icon: Activity },
  { href: "/hitl/", label: "Interventions", icon: Hand },
  { href: "/settings/", label: "Settings", icon: SettingsIcon },
];

export function isRouteActive(pathname: string, href: string): boolean {
  const normPath = pathname.replace(/\/+$/, "") || "/";
  const normHref = href.replace(/\/+$/, "") || "/";
  if (normHref === "/") {
    return normPath === "/";
  }
  return normPath === normHref || normPath.startsWith(`${normHref}/`);
}

export function Sidebar() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex gap-1 overflow-x-auto border-b border-zinc-200 p-2 md:w-56 md:flex-col md:border-r md:border-b-0 md:p-4 dark:border-zinc-800">
      <p className="hidden px-2 pb-4 text-lg font-semibold md:block">Job Butler</p>
      {LINKS.map(({ href, label, icon: Icon }) => {
        const active = isRouteActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm whitespace-nowrap ${active ? "bg-zinc-100 font-medium dark:bg-zinc-800" : "text-zinc-600 hover:bg-zinc-50 dark:text-zinc-400 dark:hover:bg-zinc-900"}`}
          >
            <Icon size={16} aria-hidden /> {label}
          </Link>
        );
      })}
    </nav>
  );
}
