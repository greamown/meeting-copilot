import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogIn, LogOut, Play, RefreshCw, Square } from "lucide-react";
import { useState } from "react";
import { getClaudeLoginStatus, getClaudeStatus, getCodexLoginStatus, getCodexStatus, post } from "../lib/api";

type Engine = "codex" | "claude";

const engines = {
  codex: {
    label: "Codex", eyebrow: "CODEX CLI", testLabel: "測試 Codex",
    note: "登入狀態由獨立 cli-worker 回報，credential 內容不會進入 API。",
    statusFn: getCodexStatus, loginFn: getCodexLoginStatus,
  },
  claude: {
    label: "Claude", eyebrow: "CLAUDE CODE", testLabel: "測試 Claude",
    note: "透過 Claude Code 帳號流程登入，credential 存於本機 ~/.claude，不會進入 API。",
    statusFn: getClaudeStatus, loginFn: getClaudeLoginStatus,
  },
} as const;

function AuthPanel({ engine }: { engine: Engine }) {
  const cfg = engines[engine];
  const client = useQueryClient();
  const status = useQuery({ queryKey: [engine, "status"], queryFn: cfg.statusFn, refetchInterval: 10_000 });
  const login = useQuery({
    queryKey: [engine, "login-status"],
    queryFn: cfg.loginFn,
    refetchInterval: query => query.state.data?.running ? 1_000 : false,
  });
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: [engine, "status"] });
    await client.invalidateQueries({ queryKey: ["system"] });
  };
  const action = useMutation({
    mutationFn: async ({ path }: { path: string }) => post<Record<string, unknown>>(path),
    onSuccess: async () => { await login.refetch(); await refresh(); },
  });
  const [code, setCode] = useState("");
  const submitCode = useMutation({
    mutationFn: () => post(`/${engine}/login/submit`, { code: code.trim() }),
    onSuccess: async () => { setCode(""); await login.refetch(); await refresh(); },
  });
  const data = status.data;
  const loginRunning = login.data?.running ?? false;
  const run = (suffix: string) => action.mutate({ path: `/${engine}${suffix}` });

  return <>
    <div className="button-row"><span className="eyebrow">{cfg.eyebrow}</span><p>{cfg.note}</p>
      <button className="icon-button" title="重新整理" onClick={() => void status.refetch()}><RefreshCw /></button>
    </div>
    <section className="section-card auth-status">
      <div className="system-row"><span>CLI</span><strong>{data?.installed ? "Installed" : "Unavailable"}</strong><code>{data?.version ?? "-"}</code></div>
      <div className="system-row"><span>Authentication</span><strong>{data?.authenticated ? "Authenticated" : "Signed out"}</strong><code>{data?.status ?? "-"}</code></div>
      <div className="system-row"><span>Provider</span><strong>{data?.provider ?? "-"}</strong><code>{data?.profile ?? "default"}</code></div>
      <div className="system-row"><span>Model</span><strong>{data?.model ?? "CLI default"}</strong><code>read-only</code></div>
      <div className="system-row"><span>Last test</span><strong>{data?.last_test?.healthy ? "Passed" : data?.last_test ? "Failed" : "Not run"}</strong><code>{data?.last_test?.error || data?.error || "No sanitized error"}</code></div>
    </section>
    <div className="button-row auth-actions">
      <button className="button primary" disabled={action.isPending || loginRunning || data?.authenticated} onClick={() => run("/login/start")}><LogIn />開始登入</button>
      <button className="button" disabled={action.isPending || !loginRunning} onClick={() => run("/login/cancel")}><Square />取消登入</button>
      <button className="button" title={!data?.authenticated ? "完成登入後才能測試" : cfg.testLabel} disabled={action.isPending || !data?.authenticated} onClick={() => run("/test")}><Play />{cfg.testLabel}</button>
      <button className="button danger" disabled={action.isPending || !data?.authenticated} onClick={() => run("/logout")}><LogOut />登出</button>
    </div>
    {login.data?.message && <div className="alert success" role="status"><pre>{login.data.message}</pre>{loginRunning && <small>尚未登入。請完成登入頁的帳號授權；狀態變成 Authenticated 後才能測試。</small>}</div>}
    {engine === "claude" && loginRunning && <div className="button-row"><input value={code} placeholder="開啟上方網址授權後，貼上取得的 code" onChange={e => setCode(e.target.value)} style={{ flex: 1 }} /><button className="button primary" disabled={!code.trim() || submitCode.isPending} onClick={() => submitCode.mutate()}>送出 code</button></div>}
    {submitCode.error && <div className="alert error">{submitCode.error.message}</div>}
    {action.data && !login.data?.message && <div className="alert success"><pre>{JSON.stringify(action.data, null, 2)}</pre></div>}
    {action.error && <div className="alert error">{action.error.message}</div>}
  </>;
}

export function CliAuth() {
  const [engine, setEngine] = useState<Engine>("codex");
  return <div className="page">
    <header className="page-head">
      <div><p className="eyebrow">CLI SIGN-IN</p><h1>CLI 登入</h1><p>登入底層推理引擎的 CLI；會議分析可用 Codex 或 Claude Code 執行。模型端點設定請見「模型與端點」。</p></div>
    </header>
    <div className="button-row" role="tablist">
      {(Object.keys(engines) as Engine[]).map(key =>
        <button key={key} role="tab" aria-selected={engine === key} className={`button ${engine === key ? "primary" : ""}`} onClick={() => setEngine(key)}>{engines[key].label}</button>)}
    </div>
    <AuthPanel key={engine} engine={engine} />
  </div>;
}
