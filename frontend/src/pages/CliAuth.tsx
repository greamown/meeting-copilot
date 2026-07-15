import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogIn, LogOut, Play, RefreshCw, Square } from "lucide-react";
import { getCodexLoginStatus, getCodexStatus, post } from "../lib/api";

export function CodexAuth() {
  const client = useQueryClient();
  const status = useQuery({
    queryKey: ["codex-status"],
    queryFn: getCodexStatus,
    refetchInterval: 10_000,
  });
  const login = useQuery({
    queryKey: ["codex-login-status"],
    queryFn: getCodexLoginStatus,
    refetchInterval: query => query.state.data?.running ? 1_000 : false,
  });
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ["codex-status"] });
    await client.invalidateQueries({ queryKey: ["system"] });
  };
  const action = useMutation({
    mutationFn: async ({ path }: { path: string }) => post<Record<string, unknown>>(path),
    onSuccess: async () => {
      await login.refetch();
      await refresh();
    },
  });
  const data = status.data;
  const loginRunning = login.data?.running ?? false;
  const run = (path: string) => action.mutate({ path });

  return <div className="page">
    <header className="page-head">
      <div><p className="eyebrow">CODEX CLI</p><h1>Codex 驗證</h1><p>登入狀態由獨立 codex-worker 回報，credential 內容不會進入 API。</p></div>
      <button className="icon-button" title="重新整理" onClick={() => void status.refetch()}><RefreshCw /></button>
    </header>
    <section className="section-card auth-status">
      <div className="system-row"><span>CLI</span><strong>{data?.installed ? "Installed" : "Unavailable"}</strong><code>{data?.version ?? "-"}</code></div>
      <div className="system-row"><span>Authentication</span><strong>{data?.authenticated ? "Authenticated" : "Signed out"}</strong><code>{data?.status ?? "-"}</code></div>
      <div className="system-row"><span>Provider</span><strong>{data?.provider ?? "codex_cli"}</strong><code>{data?.profile ?? "default profile"}</code></div>
      <div className="system-row"><span>Model</span><strong>{data?.model ?? "CLI default"}</strong><code>read-only sandbox</code></div>
      <div className="system-row"><span>Last test</span><strong>{data?.last_test?.healthy ? "Passed" : data?.last_test ? "Failed" : "Not run"}</strong><code>{data?.last_test?.error || data?.error || "No sanitized error"}</code></div>
    </section>
    <div className="button-row auth-actions">
      <button className="button primary" disabled={action.isPending || loginRunning || data?.authenticated} onClick={() => run("/codex/login/start")}><LogIn />開始登入</button>
      <button className="button" disabled={action.isPending || !loginRunning} onClick={() => run("/codex/login/cancel")}><Square />取消登入</button>
      <button className="button" title={!data?.authenticated ? "完成裝置授權後才能測試" : "測試 Codex"} disabled={action.isPending || !data?.authenticated} onClick={() => run("/codex/test")}><Play />測試 Codex</button>
      <button className="button danger" disabled={action.isPending || !data?.authenticated} onClick={() => run("/codex/logout")}><LogOut />登出</button>
    </div>
    {login.data?.message && <div className="alert success" role="status"><pre>{login.data.message}</pre>{loginRunning && <small>尚未登入。請完成裝置登入頁的帳號授權；狀態變成 Authenticated 後才能測試 Codex。</small>}</div>}
    {action.data && !login.data?.message && <div className="alert success"><pre>{JSON.stringify(action.data, null, 2)}</pre></div>}
    {action.error && <div className="alert error">{action.error.message}</div>}
  </div>;
}
