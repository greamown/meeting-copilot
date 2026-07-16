import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, Cpu, Database, HardDrive, Mic2, Plus, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { getClaudeStatus, getSystem } from "../lib/api";

function Status({ ok, label }: { ok: boolean; label: string }) { return <span className={`pill ${ok ? "good" : "warn"}`}><span className="status-dot"/>{label}</span>; }

export function Dashboard() {
  const system = useQuery({ queryKey: ["system"], queryFn: getSystem, refetchInterval: 15_000 });
  const claude = useQuery({ queryKey: ["claude-status"], queryFn: getClaudeStatus, refetchInterval: 15_000 });
  const data = system.data;
  const gpu = data?.gpu.gpus[0];
  const codexAuth = data?.codex.authenticated ?? false;
  const claudeAuth = claude.data?.authenticated ?? false;
  const engineLabel = codexAuth && claudeAuth ? "雙引擎已登入" : codexAuth ? "Codex 已登入" : claudeAuth ? "Claude 已登入" : "待登入";
  return <div className="page dashboard">
    <header className="page-head"><div><p className="eyebrow">CONTROL ROOM</p><h1>會議工作台</h1><p>本機處理語音，推理引擎（Codex / Claude Code）僅在需要時參與。</p></div><div className="head-actions"><button className="icon-button" title="重新整理" onClick={() => void system.refetch()}><RefreshCw size={18}/></button><Link className="button primary" to="/meetings/new"><Plus size={18}/>開始新會議</Link></div></header>
    {system.isError && <div className="alert error">無法連線後端：{system.error.message}</div>}
    <section className="health-strip">
      <div><span>BACKEND</span><Status ok={!system.isError} label={system.isPending ? "檢查中" : "正常"}/></div>
      <div><span>ENGINE</span><Status ok={codexAuth || claudeAuth} label={engineLabel}/></div>
      <div><span>STT</span><Status ok={data?.gpu.available ?? false} label={data?.gpu.available ? "CUDA 可用" : "CPU 備援"}/></div>
      <div><span>DATABASE</span><Status ok={data?.database.healthy ?? false} label={data?.database.dialect ?? "檢查中"}/></div>
    </section>
    <div className="metric-grid">
      <article className="metric"><Cpu/><span>GPU 使用率</span><strong>{gpu ? `${gpu.utilization_percent}%` : "N/A"}</strong><small>{gpu?.name ?? "未偵測到 NVIDIA GPU"}</small></article>
      <article className="metric"><HardDrive/><span>GPU 記憶體</span><strong>{gpu ? `${(gpu.memory_used_mb / 1024).toFixed(1)} / ${(gpu.memory_total_mb / 1024).toFixed(1)} GB` : "N/A"}</strong><small>{gpu ? "全卡用量（含其他程序）· ECC 保留後容量" : "STT 將使用 CPU"}</small></article>
      <article className="metric"><Database/><span>資料庫延遲</span><strong>{data ? `${data.database.latency_ms} ms` : "—"}</strong><small>Meeting state persistence</small></article>
      <article className="metric"><Bot/><span>推理佇列</span><strong>0</strong><small>無等待中的推理工作</small></article>
    </div>
    <div className="dashboard-grid">
      <section className="section"><div className="section-title"><div><p className="eyebrow">RECENT</p><h2>最近會議</h2></div><Link to="/history">查看全部 <ArrowRight size={15}/></Link></div><div className="empty"><Mic2 size={28}/><strong>尚無會議紀錄</strong><span>開始第一場會議後，逐字稿與決策會出現在這裡。</span><Link className="button" to="/meetings/new">建立會議</Link></div></section>
      <section className="section system-list"><div className="section-title"><div><p className="eyebrow">SYSTEM</p><h2>執行環境</h2></div></div>
        {[ ["作業系統", data?.os], ["Python", data?.python_version], ["Codex CLI", data?.codex.version ?? "未偵測"], ["Claude Code", claude.data?.version ?? "未偵測"], ["FFmpeg", data?.ffmpeg_available ? "可用" : "未安裝"], ["磁碟空間", data ? `${data.disk.free_gb} GB 可用` : "—"] ].map(([k,v]) => <div className="system-row" key={k}><span>{k}</span><strong>{v ?? "檢查中"}</strong></div>)}
      </section>
    </div>
  </div>;
}
