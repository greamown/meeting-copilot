import { Activity, AudioLines, History, LayoutDashboard, RadioTower, Settings, SlidersHorizontal, Stethoscope } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const nav = [
  ["/", "總覽", LayoutDashboard], ["/setup", "設定精靈", RadioTower], ["/providers", "模型與端點", SlidersHorizontal],
  ["/meetings", "會議", AudioLines], ["/history", "歷史", History], ["/diagnostics", "診斷", Stethoscope], ["/settings", "設定", Settings],
] as const;

export function Layout() {
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Activity size={20}/></span><span>Meeting<br/><strong>Copilot</strong></span></div>
      <nav aria-label="主要導覽">{nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/"}><Icon size={18}/><span>{label}</span></NavLink>)}</nav>
      <div className="local-badge"><span className="status-dot ok"/>LOCAL FIRST</div>
    </aside>
    <main className="content"><Outlet/></main>
  </div>;
}
