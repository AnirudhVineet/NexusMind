"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";

import { cn } from "@/lib/utils";
import { NotificationBell } from "@/components/notifications/NotificationBell";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/qa", label: "Q&A" },
  { href: "/library", label: "Library" },
  { href: "/graph", label: "Graph" },
  { href: "/notes", label: "Notes" },
  { href: "/flashcards", label: "Flashcards" },
];

const NAV_PHASE4 = [
  { href: "/research", label: "Research" },
  { href: "/studio", label: "Studio" },
  { href: "/workflows", label: "Workflows" },
  { href: "/alerts", label: "Alerts" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: session } = useSession();

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-border bg-surface px-4 py-5 flex flex-col overflow-y-auto">
        <Link href="/" className="font-semibold text-base">
          NexusMind
        </Link>
        <nav className="mt-6 flex flex-col gap-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "px-3 py-2 rounded-md text-sm",
                pathname === item.href
                  ? "bg-border text-white"
                  : "text-muted hover:text-white hover:bg-border/50"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <p className="mt-5 px-3 text-[10px] uppercase tracking-widest text-muted/50">Phase 4</p>
        <nav className="mt-1 flex flex-col gap-1">
          {NAV_PHASE4.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "px-3 py-2 rounded-md text-sm",
                pathname === item.href
                  ? "bg-border text-white"
                  : "text-muted hover:text-white hover:bg-border/50"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto pt-4 text-xs text-muted">
          <p className="truncate">{session?.user?.email}</p>
          <button
            onClick={() => signOut({ callbackUrl: "/sign-in" })}
            className="mt-2 text-accent hover:underline"
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center justify-end px-8 py-3 border-b border-border/50">
          <NotificationBell />
        </header>
        <main className="flex-1 px-8 py-8 max-w-5xl">{children}</main>
      </div>
    </div>
  );
}
