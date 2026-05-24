"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import {
  LayoutDashboard,
  Upload,
  MessageSquare,
  Library,
  StickyNote,
  Hash,
  Brain,
  Palette,
  LogOut,
  ChevronRight,
  User
} from "lucide-react";

import { cn } from "@/lib/utils";
import { DailyTip } from "@/components/daily-tip";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/qa", label: "Q&A", icon: MessageSquare },
  { href: "/library", label: "Library", icon: Library },
  { href: "/notes", label: "Notes", icon: StickyNote },
  { href: "/flashcards", label: "Flashcards", icon: Hash },
];

const NAV_PHASE4 = [
  { href: "/research", label: "Research", icon: Brain },
  { href: "/studio", label: "Studio", icon: Palette },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: session } = useSession();

  // Hide sidebar on library detail page (it has its own 3-pane layout)
  const isLibraryDetail = pathname?.startsWith("/library/") && pathname !== "/library";
  // Full-bleed main pages keep the app sidebar + header but skip the padded
  // max-width content wrapper so they can fill the main area edge-to-edge.
  const isFullBleedMain = pathname === "/qa";

  return (
    <div className="min-h-screen flex bg-background text-foreground selection:bg-primary/20">
      {!isLibraryDetail && (
        <aside className="w-64 shrink-0 border-r bg-card flex flex-col z-20 shadow-sm">
          <div className="h-14 flex items-center px-6 border-b">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="h-7 w-7 bg-primary rounded-lg flex items-center justify-center group-hover:rotate-12 transition-transform">
                <Brain className="h-4 w-4 text-primary-foreground" />
              </div>
              <span className="font-bold text-lg tracking-tight">NexusMind</span>
            </Link>
          </div>
          
          <ScrollArea className="flex-1">
            <nav className="p-4 space-y-6">
              <div className="space-y-1">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 px-2 mb-3">
                  Core Engine
                </h4>
                {NAV.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all group",
                        active
                          ? "bg-primary text-primary-foreground font-medium shadow-md shadow-primary/20"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className={cn("h-4 w-4", active ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground")} />
                        {item.label}
                      </div>
                      {active && <ChevronRight className="h-3 w-3" />}
                    </Link>
                  );
                })}
              </div>

              <Separator className="opacity-50" />

              <div className="space-y-1">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 px-2 mb-3">
                  Intelligence Tools
                </h4>
                {NAV_PHASE4.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all group",
                        active
                          ? "bg-primary text-primary-foreground font-medium shadow-md shadow-primary/20"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className={cn("h-4 w-4", active ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground")} />
                        {item.label}
                      </div>
                      {active && <ChevronRight className="h-3 w-3" />}
                    </Link>
                  );
                })}
              </div>
            </nav>
          </ScrollArea>

          <div className="p-4 border-t bg-muted/20">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="w-full justify-start gap-3 h-12 px-2 hover:bg-muted/50 transition-colors">
                  <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center border border-primary/20">
                    <User className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex-1 text-left min-w-0">
                    <p className="text-xs font-semibold truncate text-foreground">
                      {session?.user?.name || "User Account"}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {session?.user?.email}
                    </p>
                  </div>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end" side="right">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/settings">Settings</Link>
                </DropdownMenuItem>
                <DropdownMenuItem className="text-destructive" onClick={() => signOut({ callbackUrl: "/sign-in" })}>
                  <LogOut className="h-4 w-4 mr-2" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </aside>
      )}

      <div className="flex-1 flex flex-col min-w-0 relative">
        {!isLibraryDetail && (
          <header className="h-14 flex items-center justify-between px-8 border-b bg-card/30 backdrop-blur-md sticky top-0 z-10">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-widest">
              {pathname === "/" ? "Overview" : pathname?.split("/")[1] === "qa" ? "Q&A" : pathname?.split("/")[1]?.replace(/-/g, " ")}
            </div>
            <div className="flex items-center gap-4">
              <DailyTip />
            </div>
          </header>
        )}
        <main className={cn(
          "flex-1 overflow-hidden",
          !isLibraryDetail && !isFullBleedMain ? "overflow-y-auto px-8 py-8" : ""
        )}>
          {!isLibraryDetail && !isFullBleedMain ? (
            <div className="max-w-6xl mx-auto animate-in fade-in slide-in-from-bottom-2 duration-500">
              {children}
            </div>
          ) : children}
        </main>
      </div>
    </div>
  );
}
