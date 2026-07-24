import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogIn, LogOut, Play, RefreshCw, Square } from "lucide-react";
import { useState } from "react";
import {
  getClaudeLoginStatus,
  getClaudeStatus,
  getCodexLoginStatus,
  getCodexStatus,
  post,
} from "../lib/api";
import { useI18n } from "../i18n";

type Engine = "codex" | "claude";

const engines = {
  codex: {
    label: "Codex",
    eyebrow: "CODEX CLI",
    testKey: "Test Codex",
    noteKey:
      "Sign-in status is reported by the isolated CLI worker; credential contents never enter the API.",
    statusFn: getCodexStatus,
    loginFn: getCodexLoginStatus,
  },
  claude: {
    label: "Claude",
    eyebrow: "CLAUDE CODE",
    testKey: "Test Claude",
    noteKey:
      "Sign in through the Claude Code account flow; credentials stay in local ~/.claude and never enter the API.",
    statusFn: getClaudeStatus,
    loginFn: getClaudeLoginStatus,
  },
} as const;

function AuthPanel({ engine }: { engine: Engine }) {
  const { t } = useI18n();
  const cfg = engines[engine];
  const client = useQueryClient();
  const status = useQuery({
    queryKey: [engine, "status"],
    queryFn: cfg.statusFn,
    refetchInterval: 10_000,
  });
  const login = useQuery({
    queryKey: [engine, "login-status"],
    queryFn: cfg.loginFn,
    refetchInterval: (query) => (query.state.data?.running ? 1_000 : false),
  });
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: [engine, "status"] });
    await client.invalidateQueries({ queryKey: ["system"] });
  };
  const action = useMutation({
    mutationFn: async ({ path }: { path: string }) =>
      post<Record<string, unknown>>(path),
    onSuccess: async () => {
      await login.refetch();
      await refresh();
    },
  });
  const [code, setCode] = useState("");
  const submitCode = useMutation({
    mutationFn: () => post(`/${engine}/login/submit`, { code: code.trim() }),
    onSuccess: async () => {
      setCode("");
      await login.refetch();
      await refresh();
    },
  });
  const data = status.data;
  const loginRunning = login.data?.running ?? false;
  const run = (suffix: string) =>
    action.mutate({ path: `/${engine}${suffix}` });

  return (
    <>
      <div className="button-row">
        <span className="eyebrow">{cfg.eyebrow}</span>
        <p>{t(cfg.noteKey)}</p>
        <button
          className="icon-button"
          title={t("refresh")}
          onClick={() => void status.refetch()}
        >
          <RefreshCw />
        </button>
      </div>
      <section className="section-card auth-status">
        <div className="system-row">
          <span>CLI</span>
          <strong>{data?.installed ? "Installed" : "Unavailable"}</strong>
          <code>{data?.version ?? "-"}</code>
        </div>
        <div className="system-row">
          <span>Authentication</span>
          <strong>
            {data?.authenticated ? "Authenticated" : "Signed out"}
          </strong>
          <code>{data?.status ?? "-"}</code>
        </div>
        <div className="system-row">
          <span>Provider</span>
          <strong>{data?.provider ?? "-"}</strong>
          <code>{data?.profile ?? "default"}</code>
        </div>
        <div className="system-row">
          <span>Model</span>
          <strong>{data?.model ?? "CLI default"}</strong>
          <code>read-only</code>
        </div>
        <div className="system-row">
          <span>Last test</span>
          <strong>
            {data?.last_test?.healthy
              ? "Passed"
              : data?.last_test
                ? "Failed"
                : "Not run"}
          </strong>
          <code>
            {data?.last_test?.error || data?.error || "No sanitized error"}
          </code>
        </div>
      </section>
      <div className="button-row auth-actions">
        <button
          className="button primary"
          disabled={action.isPending || loginRunning || data?.authenticated}
          onClick={() => run("/login/start")}
        >
          <LogIn />
          {t("Start sign-in")}
        </button>
        <button
          className="button"
          disabled={action.isPending || !loginRunning}
          onClick={() => run("/login/cancel")}
        >
          <Square />
          {t("Cancel sign-in")}
        </button>
        <button
          className="button"
          title={
            !data?.authenticated
              ? t("Complete sign-in before testing")
              : t(cfg.testKey)
          }
          disabled={action.isPending || !data?.authenticated}
          onClick={() => run("/test")}
        >
          <Play />
          {t(cfg.testKey)}
        </button>
        <button
          className="button danger"
          disabled={action.isPending || !data?.authenticated}
          onClick={() => run("/logout")}
        >
          <LogOut />
          {t("Sign out")}
        </button>
      </div>
      {login.data?.message && (
        <div className="alert success" role="status">
          <pre>{login.data.message}</pre>
          {loginRunning && (
            <small>
              {t(
                "Not signed in. Complete account authorization on the sign-in page; testing is available after the status becomes Authenticated.",
              )}
            </small>
          )}
        </div>
      )}
      {engine === "claude" && loginRunning && (
        <div className="button-row">
          <input
            value={code}
            placeholder={t(
              "After authorizing at the URL above, paste the code",
            )}
            onChange={(e) => setCode(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="button primary"
            disabled={!code.trim() || submitCode.isPending}
            onClick={() => submitCode.mutate()}
          >
            {t("Submit code")}
          </button>
        </div>
      )}
      {submitCode.error && (
        <div className="alert error">{submitCode.error.message}</div>
      )}
      {action.data && !login.data?.message && (
        <div className="alert success">
          <pre>{JSON.stringify(action.data, null, 2)}</pre>
        </div>
      )}
      {action.error && (
        <div className="alert error">{action.error.message}</div>
      )}
    </>
  );
}

export function CliAuth() {
  const { t } = useI18n();
  const [engine, setEngine] = useState<Engine>("codex");
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">CLI SIGN-IN</p>
          <h1>{t("CLI sign-in")}</h1>
          <p>
            {t(
              "Sign in to the CLI used by the reasoning engine. Configure models and endpoints separately.",
            )}
          </p>
        </div>
      </header>
      <div className="button-row" role="tablist">
        {(Object.keys(engines) as Engine[]).map((key) => (
          <button
            key={key}
            role="tab"
            aria-selected={engine === key}
            className={`button ${engine === key ? "primary" : ""}`}
            onClick={() => setEngine(key)}
          >
            {engines[key].label}
          </button>
        ))}
      </div>
      <AuthPanel key={engine} engine={engine} />
    </div>
  );
}
