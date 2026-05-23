"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useNotifications } from "@/hooks/useNotifications";

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { notifications, unreadCount, read, readAll, dismiss } = useNotifications();

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        className={cn(
          "relative flex items-center justify-center w-8 h-8 rounded-md transition-colors",
          open ? "bg-border text-white" : "text-muted hover:text-white hover:bg-border/50"
        )}
        aria-label="Notifications"
      >
        <BellIcon />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-0.5 flex items-center justify-center rounded-full bg-accent text-white text-[10px] font-bold leading-none">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-96 rounded-lg border border-border bg-[#0f0f0f] shadow-2xl z-50 flex flex-col max-h-[480px]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
            <span className="text-sm font-medium text-white">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={readAll}
                className="text-xs text-accent hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="overflow-y-auto flex-1">
            {notifications.length === 0 ? (
              <p className="text-muted text-sm text-center py-10">No notifications yet.</p>
            ) : (
              notifications.map((n) => {
                const unread = !n.read_at;
                const inner = (
                  <div
                    className={cn(
                      "flex gap-3 px-4 py-3 border-b border-border/50 last:border-0 transition-colors",
                      unread ? "bg-accent/5 hover:bg-accent/10" : "hover:bg-white/[0.03]"
                    )}
                  >
                    {unread && (
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                    )}
                    <div className={cn("flex-1 min-w-0", !unread && "pl-[18px]")}>
                      <p className={cn("text-sm truncate", unread ? "text-white font-medium" : "text-white/80")}>
                        {n.title}
                      </p>
                      <p className="text-xs text-muted mt-0.5 line-clamp-2">{n.body}</p>
                      <p className="text-[10px] text-muted/60 mt-1">{formatRelative(n.created_at)}</p>
                    </div>
                    <button
                      onClick={(e) => { e.preventDefault(); e.stopPropagation(); dismiss(n.id); }}
                      className="shrink-0 self-start mt-1 p-1 rounded text-muted hover:text-white hover:bg-white/10 transition-colors"
                      aria-label="Dismiss"
                    >
                      <XIcon />
                    </button>
                  </div>
                );

                if (n.link) {
                  return (
                    <Link
                      key={n.id}
                      href={n.link}
                      onClick={() => { if (unread) read(n.id); setOpen(false); }}
                      className="block"
                    >
                      {inner}
                    </Link>
                  );
                }

                return (
                  <div
                    key={n.id}
                    onClick={() => { if (unread) read(n.id); }}
                    className={cn("cursor-default", n.link ? "" : "")}
                  >
                    {inner}
                  </div>
                );
              })
            )}
          </div>

          <div className="shrink-0 px-4 py-2 border-t border-border/50">
            <Link
              href="/alerts"
              onClick={() => setOpen(false)}
              className="text-xs text-muted hover:text-white transition-colors"
            >
              Manage alerts →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
