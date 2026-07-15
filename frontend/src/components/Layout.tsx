import { Activity, AudioLines, BookOpen, FolderKanban, GitCompare, History, KeyRound, LayoutDashboard, ListTodo, LockKeyhole, RadioTower, Settings, SlidersHorizontal, Stethoscope } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useI18n } from "../i18n";

const nav = [
  ["/", "dashboard", LayoutDashboard], ["/setup", "setup", RadioTower], ["/providers", "providers", SlidersHorizontal],
  ["/cli-auth", "cliAuth", KeyRound],
  ["/projects", "projects", FolderKanban],
  ["/decisions", "decisions", GitCompare], ["/actions", "actions", ListTodo], ["/knowledge", "knowledge", BookOpen],
  ["/meetings", "meetings", AudioLines], ["/history", "history", History], ["/diagnostics", "diagnostics", Stethoscope], ["/settings", "settings", Settings],
  ["/access", "access", LockKeyhole],
] as const;

export function Layout() {
  const {t}=useI18n();
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Activity size={20}/></span><span>Meeting<br/><strong>Copilot</strong></span></div>
      <nav aria-label="主要導覽">{nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/"}><Icon size={18}/><span>{t(label)}</span></NavLink>)}</nav>
      <div className="local-badge"><span className="status-dot ok"/>{t("local").toUpperCase()}</div>
    </aside>
    <main className="content"><Outlet/></main>
  </div>;
}
