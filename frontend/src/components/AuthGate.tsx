import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LockKeyhole } from "lucide-react";
import { FormEvent, ReactNode, useState } from "react";
import { getAuthStatus, post } from "../lib/api";
import { useI18n } from "../i18n";

function LoginForm() {
  const { t } = useI18n();
  const client = useQueryClient();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const login = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await post("/auth/login", { username, password });
      await client.invalidateQueries({ queryKey: ["auth-status"] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Login failed");
    }
  };
  return (
    <form className="auth-panel" onSubmit={(event) => void login(event)}>
      <LockKeyhole />
      <h1>Meeting Copilot</h1>
      <p>{t("This network address requires administrator sign-in.")}</p>
      <label>
        {t("Username")}
        <input
          autoComplete="username"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
      </label>
      <label>
        {t("Password")}
        <input
          autoComplete="current-password"
          type="password"
          required
          minLength={12}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {error && <div className="alert error">{error}</div>}
      <button className="button primary">{t("Sign in")}</button>
    </form>
  );
}

export function AuthGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const status = useQuery({
    queryKey: ["auth-status"],
    queryFn: getAuthStatus,
    retry: false,
  });
  if (status.isPending)
    return (
      <main className="auth-screen">
        <div className="auth-panel">{t("Checking access")}</div>
      </main>
    );
  if (status.isError)
    return (
      <main className="auth-screen">
        <div className="auth-panel">
          <LockKeyhole />
          <h1>{t("Unable to verify access")}</h1>
          <p>{status.error.message}</p>
        </div>
      </main>
    );
  if (status.data.authentication_required && !status.data.configured)
    return (
      <main className="auth-screen">
        <div className="auth-panel">
          <LockKeyhole />
          <h1>{t("Administrator is not configured")}</h1>
          <p>
            {t(
              "Open https://localhost/access on the host to create an administrator password, then return here to sign in.",
            )}
          </p>
        </div>
      </main>
    );
  if (status.data.authentication_required && !status.data.authenticated)
    return (
      <main className="auth-screen">
        <LoginForm />
      </main>
    );
  return children;
}
