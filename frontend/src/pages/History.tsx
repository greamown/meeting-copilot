import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, ChevronRight, Download, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useDialogs } from "../components/DialogProvider";
import { MeetingAnalytics, downloadExport, getMeeting, getMeetingAnalytics, getMeetings, post, remove } from "../lib/api";

const percent=(value:number|null|undefined)=>value==null?"—":`${Math.round(value*100)}%`;
const duration=(seconds:number)=>seconds<60?`${Math.round(seconds)} 秒`:`${Math.floor(seconds/3600)?`${Math.floor(seconds/3600)} 小時 `:""}${Math.round(seconds%3600/60)} 分`;

function Analytics({id}:{id:string}){
  const query=useQuery({queryKey:["analytics",id],queryFn:()=>getMeetingAnalytics(id)});
  if(query.isPending)return <div className="empty">計算中</div>;
  if(!query.data)return <div className="empty"><strong>無法計算分析</strong><small>{query.error instanceof Error?query.error.message:""}</small></div>;
  const a:MeetingAnalytics=query.data;
  return <div className="analytics">
    <p className="provenance">所有數字直接由資料庫統計，未經由推理引擎產生。時長來源：{a.duration_source==="meeting_timestamps"?"會議起訖時間":"逐字稿時間軸（估算）"}。</p>
    <div className="detail-summary">
      <div><span>會議時長</span><strong>{duration(a.duration_seconds)}</strong></div>
      <div><span>逐字稿字數</span><strong>{a.transcript.characters}</strong></div>
      <div><span>決策</span><strong>{a.decisions.total}</strong></div>
      <div><span>行動項目</span><strong>{a.actions.total}</strong></div>
      <div><span>逾期行動</span><strong className={a.actions.overdue?"danger-text":""}>{a.actions.overdue}</strong></div>
      <div><span>未解決問題</span><strong>{percent(a.effectiveness.unresolved_question_ratio)}</strong></div>
    </div>
    <div className="analytics-grid">
      <section className="section-card"><h3>建議處理</h3><dl className="record-detail">
        <div><dt>總數</dt><dd>{a.suggestions.total}</dd></div>
        {(["accepted","edited","converted","ignored"] as const).map(key=><div key={key}><dt>{key}</dt><dd>{percent(a.suggestion_rates[key])}</dd></div>)}
      </dl></section>
      <section className="section-card"><h3>行動品質</h3><dl className="record-detail">
        <div><dt>有負責人</dt><dd>{percent(a.effectiveness.actions_with_owner_ratio)}</dd></div>
        <div><dt>有期限</dt><dd>{percent(a.effectiveness.actions_with_due_date_ratio)}</dd></div>
        <div><dt>已完成</dt><dd>{a.actions.completed} / {a.actions.total}</dd></div>
        <div><dt>平均完成時間</dt><dd>{a.actions.average_completion_hours==null?"—":`${a.actions.average_completion_hours} 小時`}</dd></div>
        <div><dt>每小時決策數</dt><dd>{a.effectiveness.decisions_per_hour??"—"}</dd></div>
      </dl></section>
      <section className="section-card"><h3>引擎執行</h3><dl className="record-detail">
        <div><dt>次數</dt><dd>{a.engine_runs.total}</dd></div>
        <div><dt>平均耗時</dt><dd>{a.engine_runs.average_duration_ms==null?"—":`${Math.round(a.engine_runs.average_duration_ms)} ms`}</dd></div>
        <div><dt>失敗率</dt><dd>{percent(a.engine_runs.failure_rate)}</dd></div>
        <div><dt>逾時率</dt><dd>{percent(a.engine_runs.timeout_rate)}</dd></div>
      </dl></section>
      <section className="section-card"><h3>發言時間</h3>{a.transcript.speakers.length?<><dl className="record-detail">{a.transcript.speakers.map(row=><div key={row.speaker_id}><dt>{row.speaker_id}</dt><dd>{duration(row.seconds)} · {percent(row.share)}</dd></div>)}</dl><small>僅涵蓋已標記講者的段落（{percent(a.transcript.speaker_labelled_ratio)}），系統沒有自動分離講者。</small></>:<p className="prose">逐字稿沒有講者標記，無法計算發言比例。</p>}</section>
    </div>
  </div>;
}

export function History(){const meetings=useQuery({queryKey:["meetings"],queryFn:getMeetings});const [filter,setFilter]=useState("");const rows=meetings.data?.filter(item=>item.title.toLowerCase().includes(filter.toLowerCase()))??[];return <div className="page"><header className="page-head"><div><p className="eyebrow">ARCHIVE</p><h1>會議歷史</h1><p>檢視逐字稿、決策、Codex runs 與匯出。</p></div><div className="search large"><Search/><input value={filter} onChange={e=>setFilter(e.target.value)} placeholder="依標題搜尋"/></div></header><div className="meeting-table"><div className="table-head"><span>會議</span><span>狀態</span><span>開始時間</span><span>語言</span><span/></div>{rows.map(item=><Link to={`/history/${item.id}`} key={item.id}><div><strong className="truncate" title={item.title}>{item.title}</strong><small className="truncate" title={item.goal}>{item.goal}</small></div><span className={`status-label ${item.status}`}>{item.status}</span><span>{item.started_at?new Date(item.started_at).toLocaleString():"尚未開始"}</span><span>{item.language}</span><ChevronRight/></Link>)}{rows.length===0&&<div className="empty"><Calendar/><strong>找不到會議</strong></div>}</div></div>}

export function HistoryDetail(){const dialogs=useDialogs();const {id=""}=useParams();const navigate=useNavigate();const client=useQueryClient();const detail=useQuery({queryKey:["meeting",id],queryFn:()=>getMeeting(id)});const [tab,setTab]=useState("transcript");const data=detail.data;if(!data)return <div className="page"><div className="empty">載入中</div></div>;const removeMeeting=async()=>{if(!await dialogs.confirm({title:"刪除會議",message:"完整刪除此會議、逐字稿與事件？此操作無法復原。",confirmLabel:"永久刪除",danger:true}))return;await remove(`/meetings/${id}`);await client.invalidateQueries({queryKey:["meetings"]});navigate("/history")};return <div className="page"><header className="page-head"><div><p className="eyebrow">MEETING DETAIL · {data.meeting.status}</p><h1>{data.meeting.title}</h1><p>{data.meeting.goal}</p></div><div className="head-actions"><button className="button" onClick={()=>void post(`/meetings/${id}/analyze`)}>重新分析</button><button className="icon-button danger" title="刪除會議" onClick={()=>void removeMeeting()}><Trash2/></button></div></header><div className="detail-summary"><div><span>逐字稿</span><strong>{data.transcripts.length}</strong></div><div><span>建議接受率</span><strong>{data.suggestions.length?`${Math.round(data.suggestions.filter(x=>x.status==="accepted").length/data.suggestions.length*100)}%`:"—"}</strong></div><div><span>Codex runs</span><strong>{data.codex_runs.length}</strong></div><div><span>行動項目</span><strong>{data.action_items.length}</strong></div></div>{data.meeting.audio_saved&&<audio className="meeting-audio" controls preload="metadata" src={`/api/meetings/${id}/audio`}/>}<div className="tabs">{["transcript","suggestions","state","analytics","codex"].map(item=><button className={tab===item?"active":""} onClick={()=>setTab(item)} key={item}>{item}</button>)}</div><section className="detail-content">{tab==="transcript"&&data.transcripts.map(item=><div className="detail-row" key={item.id}><time>{(item.start_ms/1000).toFixed(1)}s</time><p>{item.text}</p></div>)}{tab==="suggestions"&&data.suggestions.map(item=><div className="detail-row" key={item.id}><span>{item.category}</span><p>{item.content}</p><strong>{item.status}</strong></div>)}{tab==="state"&&[["Decisions",data.decisions],["Open questions",data.open_questions],["Risks",data.risks],["Actions",data.action_items]].map(([name,items])=><div className="state-group" key={String(name)}><h3>{String(name)}</h3>{Array.isArray(items)&&items.map(item=><p key={String(item.id)}>{String(item.content)}</p>)}</div>)}{tab==="analytics"&&<Analytics id={id}/>}{tab==="codex"&&data.codex_runs.map(run=><div className="detail-row" key={String(run.id)}><code>{String(run.id).slice(0,8)}</code><p>{String(run.job_type)} · {String(run.trigger)}</p><strong>{String(run.status)}</strong><small>{String(run.sanitized_stderr||"")}</small></div>)}</section><div className="export-bar"><Download/><strong>匯出</strong>{(["markdown","json","pdf","vtt","srt"] as const).map(format=><button className="button" onClick={()=>void downloadExport(id,format)} key={format}>{format.toUpperCase()}</button>)}<button className="button danger" onClick={()=>void (async()=>{if(await dialogs.confirm({title:"刪除會議音訊",message:"刪除已保存的原始音訊？逐字稿與會議資料會保留。",confirmLabel:"刪除音訊",danger:true})){await remove(`/meetings/${id}/audio`);await client.invalidateQueries({queryKey:["meeting",id]})}})()}>僅刪除音訊</button></div></div>}
