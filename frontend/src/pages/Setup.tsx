import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronLeft, ChevronRight, CircleAlert, LoaderCircle, Mic, RefreshCw, Volume2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getClaudeStatus, getCodexStatus, getProviders, getSettings, getSystem, LanguageCode, post, put, SettingsData } from "../lib/api";
import { useMicrophone } from "../hooks/useMicrophone";

const steps = ["系統檢查", "引擎登入", "推理引擎", "STT 設定", "TTS 設定", "語言設定", "麥克風測試", "儲存完成"];
const languages: Array<[LanguageCode, string]> = [["zh-TW", "繁體中文"], ["zh-CN", "簡體中文"], ["en", "English"], ["ja", "日本語"], ["ko", "한국어"]];

export function Setup() {
  const [step, setStep] = useState(0);
  const [languageForm, setLanguageForm] = useState<SettingsData | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const system = useQuery({ queryKey: ["system"], queryFn: getSystem });
  const codex = useQuery({ queryKey: ["codex-status"], queryFn: getCodexStatus });
  const claude = useQuery({ queryKey: ["claude-status"], queryFn: getClaudeStatus });
  const providers = useQuery({ queryKey: ["providers"], queryFn: getProviders });
  const settings = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const mic = useMicrophone();
  const providerTest = useMutation({ mutationFn: (id: string) => post<{healthy:boolean;detail:string}>(`/providers/${id}/test`) });
  const authLabel = (s?: { installed?: boolean; authenticated?: boolean }) => !s?.installed ? "未安裝" : s.authenticated ? "已登入" : "尚未登入";
  const form = languageForm ?? settings.data ?? null;
  const updateLanguage = <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => {
    if (form) setLanguageForm({ ...form, [key]: value });
  };
  const checks = useMemo(() => system.data ? [
    ["Docker container", system.data.docker_available],
    ["Docker Compose stack", system.data.docker_compose_available ?? false],
    ["NVIDIA Container Toolkit", system.data.nvidia_container_toolkit_available ?? false],
    ["A6000 / CUDA", system.data.gpu.available && (system.data.gpu.cuda_available ?? true)],
    ["FFmpeg", system.data.ffmpeg_available],
    ["Engine CLI (cli-worker)", system.data.codex.installed && (claude.data?.installed ?? false)],
    ["PostgreSQL", system.data.database.healthy],
    ["Redis", system.data.redis.healthy === true],
    ["Disk space > 5 GB", system.data.disk.free_gb > 5],
  ] as Array<[string, boolean]> : [], [system.data, claude.data?.installed]);
  const speak = () => {
    const utterance = new SpeechSynthesisUtterance("Meeting Copilot 語音測試正常");
    utterance.lang = form?.tts_language ?? "zh-TW";
    speechSynthesis.cancel(); speechSynthesis.speak(utterance);
  };
  const complete = async () => {
    if (!form) return;
    await put("/settings", { ...form, setup_completed: true });
    localStorage.setItem("meeting-copilot-setup", "complete");
    await queryClient.invalidateQueries({ queryKey: ["settings"] });
    navigate("/");
  };
  const providerFor = (role: string) => providers.data?.find(item => item.role === role && item.is_default) ?? providers.data?.find(item => item.role === role);
  const optionList = (special?: [string, string]) => <>{special && <option value={special[0]}>{special[1]}</option>}{languages.map(([code, label]) => <option value={code} key={code}>{label}</option>)}</>;

  return <div className="page"><header className="page-head"><div><p className="eyebrow">INITIAL SETUP</p><h1>設定精靈</h1><p>設定會儲存在後端；credential 僅留在本機 CLI 或環境 secret。</p></div></header><div className="wizard"><ol>{steps.map((label,index)=><li className={index===step?"active":index<step?"done":""} key={label}><span>{index<step?<Check size={14}/>:index+1}</span>{label}</li>)}</ol><section className="wizard-body">
    {step===0&&<><h2>系統檢查</h2><p>由實際服務健康狀態確認 Compose、GPU、資料庫與工具鏈。</p><div className="check-list">{system.isPending?<LoaderCircle className="spin"/>:checks.map(([label,ok])=><div key={label}><span className={`check-icon ${ok?"pass":"fail"}`}>{ok?<Check size={16}/>:<CircleAlert size={16}/>}</span><strong>{label}</strong><span>{ok?"通過":"需要處理"}</span></div>)}</div><button className="button" onClick={()=>void system.refetch()}><RefreshCw/>重新檢查</button></>}
    {step===1&&<><h2>引擎登入</h2><p>推理引擎可用 Codex CLI 或 Claude Code。登入與切換都在「CLI 登入」頁完成，credential 僅留在本機 CLI。</p><div className="fact-grid"><div><span>Codex CLI</span><strong>{authLabel(codex.data)}</strong></div><div><span>Claude Code</span><strong>{authLabel(claude.data)}</strong></div></div><div className="button-row"><button className="button primary" onClick={()=>navigate("/cli-auth")}>前往 CLI 登入</button></div></>}
    {step===2&&<><h2>推理引擎</h2><p>Reasoning 可透過 Codex CLI 或 Claude Code；此處管理 reasoning provider 的 profile、base URL、model 與 secret reference。</p>{providerFor("reasoning")?<div className="fact-grid"><div><span>Provider</span><strong>{providerFor("reasoning")?.name}</strong></div><div><span>Model</span><strong>{providerFor("reasoning")?.model??"CLI default"}</strong></div><div><span>Sandbox</span><strong>{String(providerFor("reasoning")?.extra.sandbox??"read-only")}</strong></div><div><span>Network</span><strong>{providerFor("reasoning")?.extra.network_access?"enabled":"disabled"}</strong></div></div>:<div className="alert error">尚無 reasoning provider</div>}<button className="button primary" onClick={()=>navigate("/providers")}>管理 Provider</button></>}
    {step===3&&<><h2>STT 設定</h2><p>本機 faster-whisper 優先使用 A6000，失敗才切換明確的 CPU fallback。</p><div className="fact-grid"><div><span>Provider</span><strong>{providerFor("stt")?.name??"未設定"}</strong></div><div><span>GPU</span><strong>{system.data?.gpu.gpus[0]?.name??"Unavailable"}</strong></div><div><span>Model</span><strong>{providerFor("stt")?.model??"large-v3-turbo"}</strong></div><div><span>Compute</span><strong>{String(providerFor("stt")?.extra.compute_type??"float16")}</strong></div></div>{providerFor("stt")&&<button className="button" onClick={()=>providerTest.mutate(providerFor("stt")!.id)}>測試 STT Provider</button>}{providerTest.data&&<div className={`alert ${providerTest.data.healthy?"success":"error"}`}>{providerTest.data.detail}</div>}</>}
    {step===4&&<><h2>TTS 設定</h2><p>瀏覽器語音是 fallback；server TTS 可在 Provider registry 中選用。</p><div className="fact-grid"><div><span>Default</span><strong>{providerFor("tts")?.name??"Browser Speech"}</strong></div><div><span>Language</span><strong>{form?.tts_language??"zh-TW"}</strong></div></div><div className="button-row"><button className="button primary" onClick={speak}><Volume2/>播放測試</button><button className="button" onClick={()=>speechSynthesis.cancel()}>停止</button>{providerFor("tts")&&<button className="button" onClick={()=>providerTest.mutate(providerFor("tts")!.id)}>測試 Provider</button>}</div></>}
    {step===5&&form&&<><h2>語言設定</h2><p>輸入、逐字稿、翻譯、建議、摘要、匯出與 TTS 可獨立設定。</p><div className="form-grid"><label>UI language<select value={form.ui_language} onChange={e=>updateLanguage("ui_language",e.target.value as LanguageCode)}>{optionList()}</select></label><label>Meeting input<select value={form.meeting_input_language} onChange={e=>updateLanguage("meeting_input_language",e.target.value as SettingsData["meeting_input_language"])}>{optionList(["auto","自動偵測"])}</select></label><label>Secondary language<select value={form.secondary_meeting_language} onChange={e=>updateLanguage("secondary_meeting_language",e.target.value as SettingsData["secondary_meeting_language"])}>{optionList(["none","無"])}</select></label><label>Transcript display<select value={form.transcript_display_language} onChange={e=>updateLanguage("transcript_display_language",e.target.value as SettingsData["transcript_display_language"])}>{optionList(["original","原文"])}</select></label><label>Translation<select value={form.translation_language} onChange={e=>updateLanguage("translation_language",e.target.value as SettingsData["translation_language"])}>{optionList(["none","不翻譯"])}</select></label><label>Suggestion output<select value={form.suggestion_output_language} onChange={e=>updateLanguage("suggestion_output_language",e.target.value as LanguageCode)}>{optionList()}</select></label><label>Summary output<select value={form.summary_output_language} onChange={e=>updateLanguage("summary_output_language",e.target.value as LanguageCode)}>{optionList()}</select></label><label>Export<select value={form.export_language} onChange={e=>updateLanguage("export_language",e.target.value as SettingsData["export_language"])}>{optionList(["original","原文"])}</select></label><label>TTS<select value={form.tts_language} onChange={e=>updateLanguage("tts_language",e.target.value as LanguageCode)}>{optionList()}</select></label></div></>}
    {step===6&&<><h2>麥克風測試</h2><p>瀏覽器取得權限後顯示即時音量；此測試不會上傳或保存音訊。</p><div className="meter"><i style={{width:`${mic.level*100}%`}}/></div>{mic.error&&<div className="alert error">{mic.error}</div>}<button className={`button ${mic.active?"":"primary"}`} onClick={()=>mic.active?mic.stop():void mic.start()}><Mic/>{mic.active?"停止測試":"允許並測試"}</button></>}
    {step===7&&<><h2>儲存並開始使用</h2><p>所有基礎服務已可用。儲存後仍可從設定精靈、CLI 登入與模型端點頁面重新調整。</p><button className="button primary" disabled={!form} onClick={()=>void complete()}>儲存並開啟工作台</button></>}
    <footer><button className="button" disabled={step===0} onClick={()=>setStep(value=>value-1)}><ChevronLeft/>上一步</button>{step<7&&<button className="button primary" onClick={()=>setStep(value=>value+1)}>下一步<ChevronRight/></button>}</footer>
  </section></div></div>;
}
