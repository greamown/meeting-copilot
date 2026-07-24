import { useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogOut, ShieldCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import { getAuthStatus, post } from "../lib/api";
import { useI18n } from "../i18n";

export function Access() {
  const { t } = useI18n();
  const client = useQueryClient();
  const status = useQuery({
    queryKey: ["auth-status"],
    queryFn: getAuthStatus,
  });
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const bootstrap = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError(t("Passwords do not match"));
      return;
    }
    try {
      await post("/auth/bootstrap", { username, password });
      setPassword("");
      setConfirmPassword("");
      setMessage(
        t("Administrator created; devices on this domain must now sign in."),
      );
      await client.invalidateQueries({ queryKey: ["auth-status"] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Setup failed"));
    }
  };
  const logout = async () => {
    await post("/auth/logout");
    await client.invalidateQueries({ queryKey: ["auth-status"] });
  };
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">REMOTE ACCESS</p>
          <h1>{t("Access control")}</h1>
          <p>
            {t(
              "LAN access uses an Argon2 administrator password, HttpOnly session, and CSRF validation.",
            )}
          </p>
        </div>
      </header>
      {message && <div className="alert success">{message}</div>}
      {status.data?.configured ? (
        <section className="section-card access-status">
          <ShieldCheck />
          <div>
            <h2>{t("Administrator configured")}</h2>
            <p>
              {status.data.authenticated
                ? `${status.data.username} · ${status.data.role}`
                : t(
                    "Localhost currently requires no sign-in; remote addresses show the sign-in screen.",
                  )}
            </p>
          </div>
          {status.data.authenticated && (
            <button className="button" onClick={() => void logout()}>
              <LogOut size={15} />
              {t("Sign out of this session")}
            </button>
          )}
        </section>
      ) : (
        <form
          className="settings-form"
          onSubmit={(event) => void bootstrap(event)}
        >
          <section>
            <KeyRound />
            <h2>{t("Create administrator")}</h2>
            <p>
              {t(
                "This action is available only from localhost. The password is stored only as an Argon2 hash.",
              )}
            </p>
            <div className="form-grid">
              <label>
                {t("Username")}
                <input
                  required
                  minLength={3}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </label>
              <label>
                {t("Password")}
                <input
                  required
                  type="password"
                  minLength={12}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <label>
                {t("Confirm password")}
                <input
                  required
                  type="password"
                  minLength={12}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </label>
            </div>
            {error && <div className="alert error">{error}</div>}
            <button className="button primary">
              {t("Enable remote sign-in")}
            </button>
          </section>
        </form>
      )}
    </div>
  );
}
