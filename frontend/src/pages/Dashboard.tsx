import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, Cpu, Database, HardDrive, Mic2, Plus, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { getClaudeStatus, getSystem } from "../lib/api";
import { useI18n } from "../i18n";

function Status({ ok, label }: { ok: boolean; label: string }) { return <span className={`pill ${ok ? "good" : "warn"}`}><span className="status-dot"/>{label}</span>; }

export function Dashboard() {
  const {t}=useI18n();
  const system = useQuery({ queryKey: ["system"], queryFn: getSystem, refetchInterval: 15_000 });
  const claude = useQuery({ queryKey: ["claude-status"], queryFn: getClaudeStatus, refetchInterval: 15_000 });
  const data = system.data;
  const gpu = data?.gpu.gpus[0];
  const codexAuth = data?.codex.authenticated ?? false;
  const claudeAuth = claude.data?.authenticated ?? false;
  const engineLabel = codexAuth && claudeAuth ? t("bothEnginesSignedIn") : codexAuth ? t("codexSignedIn") : claudeAuth ? t("claudeSignedIn") : t("signInRequired");
  return <div className="page dashboard">
    <header className="page-head"><div><p className="eyebrow">CONTROL ROOM</p><h1>{t("dashboardTitle")}</h1><p>{t("dashboardSubtitle")}</p></div><div className="head-actions"><button className="icon-button" title={t("refresh")} onClick={() => void system.refetch()}><RefreshCw size={18}/></button><Link className="button primary" to="/meetings/new"><Plus size={18}/>{t("startMeeting")}</Link></div></header>
    {system.isError && <div className="alert error">{t("backendUnavailable")}：{system.error.message}</div>}
    <section className="health-strip">
      <div><span>BACKEND</span><Status ok={!system.isError} label={system.isPending ? t("checking") : t("healthy")}/></div>
      <div><span>ENGINE</span><Status ok={codexAuth || claudeAuth} label={engineLabel}/></div>
      <div><span>STT</span><Status ok={data?.gpu.available ?? false} label={data?.gpu.available ? t("cudaAvailable") : t("cpuFallback")}/></div>
      <div><span>DATABASE</span><Status ok={data?.database.healthy ?? false} label={data?.database.dialect ?? t("checking")}/></div>
    </section>
    <div className="metric-grid">
      <article className="metric"><Cpu/><span>{t("gpuUsage")}</span><strong>{gpu ? `${gpu.utilization_percent}%` : "N/A"}</strong><small>{gpu?.name ?? t("gpuNotDetected")}</small></article>
      <article className="metric"><HardDrive/><span>{t("gpuMemory")}</span><strong>{gpu ? `${(gpu.memory_used_mb / 1024).toFixed(1)} / ${(gpu.memory_total_mb / 1024).toFixed(1)} GB` : "N/A"}</strong><small>{gpu ? t("gpuMemoryNote") : t("sttUsesCpu")}</small></article>
      <article className="metric"><Database/><span>{t("databaseLatency")}</span><strong>{data ? `${data.database.latency_ms} ms` : "—"}</strong><small>Meeting state persistence</small></article>
      <article className="metric"><Bot/><span>{t("inferenceQueue")}</span><strong>0</strong><small>{t("noInferenceJobs")}</small></article>
    </div>
    <div className="dashboard-grid">
      <section className="section"><div className="section-title"><div><p className="eyebrow">RECENT</p><h2>{t("recentMeetings")}</h2></div><Link to="/history">{t("viewAll")} <ArrowRight size={15}/></Link></div><div className="empty"><Mic2 size={28}/><strong>{t("noMeetings")}</strong><span>{t("noMeetingsHint")}</span><Link className="button" to="/meetings/new">{t("createMeeting")}</Link></div></section>
      <section className="section system-list"><div className="section-title"><div><p className="eyebrow">SYSTEM</p><h2>{t("runtime")}</h2></div></div>
        {[ [t("operatingSystem"), data?.os], ["Python", data?.python_version], ["Codex CLI", data?.codex.version ?? t("notDetected")], ["Claude Code", claude.data?.version ?? t("notDetected")], ["FFmpeg", data?.ffmpeg_available ? t("available") : t("notInstalled")], [t("diskSpace"), data ? `${data.disk.free_gb} ${t("gbAvailable")}` : "—"] ].map(([k,v]) => <div className="system-row" key={k}><span>{k}</span><strong>{v ?? t("checking")}</strong></div>)}
      </section>
    </div>
  </div>;
}
