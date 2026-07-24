import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AudioLines,
  BookOpen,
  FolderKanban,
  GitCompare,
  History,
  KeyRound,
  LayoutDashboard,
  ListTodo,
  LockKeyhole,
  RadioTower,
  Settings,
  SlidersHorizontal,
  Stethoscope,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useI18n } from "../i18n";
import { getActions } from "../lib/api";

const nav = [
  ["/", "dashboard", LayoutDashboard],
  ["/setup", "setup", RadioTower],
  ["/providers", "providers", SlidersHorizontal],
  ["/cli-auth", "cliAuth", KeyRound],
  ["/projects", "projects", FolderKanban],
  ["/decisions", "decisions", GitCompare],
  ["/actions", "actions", ListTodo],
  ["/knowledge", "knowledge", BookOpen],
  ["/meetings", "meetings", AudioLines],
  ["/history", "history", History],
  ["/diagnostics", "diagnostics", Stethoscope],
  ["/settings", "settings", Settings],
  ["/access", "access", LockKeyhole],
] as const;

const closed = ["completed", "archived"];

export function Layout() {
  const { t } = useI18n();
  // ponytail: polled off the existing action list, no notification table. Add one when a
  // reminder has to survive a page reload or leave the browser.
  const actions = useQuery({
    queryKey: ["actions"],
    queryFn: () => getActions(),
    staleTime: 60_000,
    refetchInterval: 300_000,
  });
  const now = Date.now();
  const overdue = (actions.data ?? []).filter(
    (row) =>
      row.due_at &&
      new Date(row.due_at).getTime() < now &&
      !closed.includes(row.status),
  ).length;
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Activity size={20} />
          </span>
          <span>
            Meeting
            <br />
            <strong>Copilot</strong>
          </span>
        </div>
        <nav aria-label={t("Primary navigation")}>
          {nav.map(([to, label, Icon]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              title={t(label)}
              aria-label={t(label)}
            >
              <Icon size={18} />
              <span>{t(label)}</span>
              {to === "/actions" && overdue > 0 && (
                <span
                  className="nav-badge"
                  title={t("{count} overdue action items", { count: overdue })}
                >
                  {overdue}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="local-badge">
          <span className="status-dot ok" />
          {t("local").toUpperCase()}
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
