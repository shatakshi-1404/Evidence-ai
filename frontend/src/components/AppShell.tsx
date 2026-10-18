import { useQuery } from "@tanstack/react-query";
import { Activity, BarChart3, History, Library, LogOut, MessageSquare, Search } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { cn } from "../lib/cn";
import { Button } from "./ui/button";

const NAV = [
  { to: "/library", label: "Library", icon: Library },
  { to: "/ask", label: "Ask", icon: MessageSquare },
  { to: "/search", label: "Search", icon: Search },
  { to: "/history", label: "History", icon: History },
  { to: "/evaluation", label: "Evaluation", icon: BarChart3 },
];

function ApiStatus() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: false,
  });
  const online = health.isSuccess;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
        online ? "bg-teal-light text-teal" : health.isError ? "bg-red-100 text-red-700" : "bg-line text-navy-soft",
      )}
    >
      <Activity aria-hidden="true" size={12} />
      {online ? "API online" : health.isError ? "API offline" : "Checking…"}
    </span>
  );
}

export function AppShell() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar (desktop) */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface p-5 md:flex">
        <div className="font-serif text-xl font-semibold">EvidenceAI</div>
        <nav aria-label="Main" className="mt-8 flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                  isActive
                    ? "bg-teal-light/60 font-medium text-navy"
                    : "text-navy-soft hover:bg-paper hover:text-navy",
                )
              }
            >
              <Icon aria-hidden="true" size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-line bg-surface/70 px-4 py-3 backdrop-blur md:px-6">
          <div className="font-serif text-lg font-semibold md:hidden">EvidenceAI</div>
          <div className="hidden md:block" />
          <div className="flex items-center gap-3">
            <ApiStatus />
            <span className="hidden max-w-[12rem] truncate text-sm text-navy-soft sm:block">
              {user?.full_name}
            </span>
            <Button variant="ghost" size="icon" aria-label="Sign out" onClick={() => void logout()}>
              <LogOut aria-hidden="true" size={16} />
            </Button>
          </div>
        </header>

        <main className="flex-1 px-4 pb-24 pt-6 md:px-6 md:pb-10">
          <Outlet />
        </main>
      </div>

      {/* Tab bar (mobile) */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-surface md:hidden"
      >
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex flex-1 flex-col items-center gap-0.5 py-2 text-xs",
                isActive ? "font-medium text-teal" : "text-navy-soft",
              )
            }
          >
            <Icon aria-hidden="true" size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
