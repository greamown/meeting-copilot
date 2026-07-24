import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  FlaskConical,
  Plus,
  Power,
  Save,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useState } from "react";
import { getProviders, post, Provider, put, remove } from "../lib/api";
import { useDialogs } from "../components/DialogProvider";
import { useI18n } from "../i18n";

const blank = {
  id: "",
  name: "",
  role: "stt",
  provider_type: "local_faster_whisper",
  base_url: "",
  secret_ref: "",
  model: "",
  enabled: true,
  timeout_seconds: 60,
  max_retries: 2,
  profile: "",
  sandbox: "read-only",
  approval_policy: "never",
  network_access: false,
  working_directory_policy: "runtime-only",
  extra: "{}",
};
export function Providers() {
  const { t } = useI18n();
  const dialogs = useDialogs();
  const queryClient = useQueryClient();
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: getProviders,
  });
  const [editing, setEditing] = useState<typeof blank | null>(null);
  const refresh = () =>
    void queryClient.invalidateQueries({ queryKey: ["providers"] });
  const test = useMutation({
    mutationFn: (id: string) =>
      post<{ healthy: boolean; detail: string }>(`/providers/${id}/test`),
    onSuccess: refresh,
  });
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!editing) return;
    const {
      profile,
      sandbox,
      approval_policy,
      network_access,
      working_directory_policy,
      extra,
      ...fields
    } = editing;
    const advanced = JSON.parse(extra);
    const body = {
      ...fields,
      base_url: fields.base_url || null,
      secret_ref: fields.secret_ref || null,
      model: fields.model || null,
      extra: {
        ...advanced,
        profile: profile || null,
        sandbox,
        approval_policy,
        network_access,
        working_directory_policy,
      },
    };
    const exists = providers.data?.some((item) => item.id === editing.id);
    if (exists) await put(`/providers/${editing.id}`, body);
    else await post("/providers", body);
    setEditing(null);
    refresh();
  };
  const edit = (item: Provider) =>
    setEditing({
      ...blank,
      ...item,
      base_url: item.base_url ?? "",
      secret_ref: item.secret_ref ?? "",
      model: item.model ?? "",
      profile: String(item.extra.profile ?? ""),
      sandbox: String(item.extra.sandbox ?? "read-only"),
      approval_policy: String(item.extra.approval_policy ?? "never"),
      network_access: Boolean(item.extra.network_access),
      working_directory_policy: String(
        item.extra.working_directory_policy ?? "runtime-only",
      ),
      extra: JSON.stringify(
        Object.fromEntries(
          Object.entries(item.extra).filter(
            ([key]) =>
              ![
                "profile",
                "sandbox",
                "approval_policy",
                "network_access",
                "working_directory_policy",
              ].includes(key),
          ),
        ),
        null,
        2,
      ),
    });
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">MODEL REGISTRY</p>
          <h1>{t("Models and endpoints")}</h1>
          <p>
            {t(
              "Secrets accept only injected environment variable names. Advanced JSON forbids secret, token, and credential fields.",
            )}
          </p>
        </div>
        <button className="button primary" onClick={() => setEditing(blank)}>
          <Plus size={16} />
          {t("Add provider")}
        </button>
      </header>
      <div className="provider-grid">
        {providers.data?.map((item) => (
          <article
            className={`provider ${item.enabled ? "" : "disabled"}`}
            key={item.id}
          >
            <div className="provider-head">
              <span className="role">{item.role}</span>
              {item.is_default && (
                <span className="default">
                  <Star size={12} />
                  DEFAULT
                </span>
              )}
            </div>
            <h2>{item.name}</h2>
            <code>
              {item.provider_type} · {item.model || "no model"}
            </code>
            <dl>
              <div>
                <dt>Status</dt>
                <dd>{item.enabled ? "enabled" : "disabled"}</dd>
              </div>
              <div>
                <dt>Health</dt>
                <dd
                  className={
                    item.health_status === "healthy" ? "text-good" : ""
                  }
                >
                  {item.health_status}
                </dd>
              </div>
              <div>
                <dt>Latency</dt>
                <dd>
                  {item.last_latency_ms ? `${item.last_latency_ms} ms` : "—"}
                </dd>
              </div>
              <div>
                <dt>Secret ref</dt>
                <dd>{item.secret_ref || "none"}</dd>
              </div>
            </dl>
            <div className="card-actions">
              <button
                className="icon-button"
                title={t("Test connection")}
                onClick={() => test.mutate(item.id)}
              >
                <FlaskConical size={16} />
              </button>
              <button className="button" onClick={() => edit(item)}>
                {t("Edit")}
              </button>
              <button
                className="icon-button"
                title={item.enabled ? t("Disable") : t("Enable")}
                onClick={() =>
                  void post(`/providers/${item.id}/toggle`).then(refresh)
                }
              >
                <Power size={16} />
              </button>
              <button
                className="icon-button"
                title={t("Set as default")}
                disabled={!item.enabled}
                onClick={() =>
                  void post(`/providers/${item.id}/set-default`).then(refresh)
                }
              >
                <Star size={16} />
              </button>
              <button
                className="icon-button danger"
                title={t("Delete")}
                onClick={() =>
                  void (async () => {
                    if (
                      await dialogs.confirm({
                        title: t("Delete provider"),
                        message: t(
                          "Delete “{name}”? New jobs using this provider will no longer start.",
                          { name: item.name },
                        ),
                        confirmLabel: t("Delete"),
                        danger: true,
                      })
                    )
                      await remove(`/providers/${item.id}`).then(refresh);
                  })()
                }
              >
                <Trash2 size={16} />
              </button>
            </div>
          </article>
        ))}
      </div>
      {test.data && (
        <div className={`toast ${test.data.healthy ? "success" : "error"}`}>
          <CheckCircle2 size={16} />
          {test.data.detail}
        </div>
      )}
      {editing && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={(event) => void submit(event)}>
            <header>
              <h2>{t("Provider settings")}</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setEditing(null)}
              >
                <X />
              </button>
            </header>
            <div className="form-grid">
              <label>
                ID
                <input
                  value={editing.id}
                  required
                  pattern="[a-z0-9][a-z0-9_-]{2,63}"
                  onChange={(e) =>
                    setEditing({ ...editing, id: e.target.value })
                  }
                />
              </label>
              <label>
                {t("Name")}
                <input
                  value={editing.name}
                  required
                  onChange={(e) =>
                    setEditing({ ...editing, name: e.target.value })
                  }
                />
              </label>
              <label>
                {t("Role")}
                <select
                  value={editing.role}
                  onChange={(e) =>
                    setEditing({ ...editing, role: e.target.value })
                  }
                >
                  <option>reasoning</option>
                  <option>stt</option>
                  <option>tts</option>
                  <option>embedding</option>
                  <option>reranker</option>
                </select>
              </label>
              <label>
                Provider type
                <select
                  value={editing.provider_type}
                  onChange={(e) =>
                    setEditing({ ...editing, provider_type: e.target.value })
                  }
                >
                  <option>codex_cli</option>
                  <option>claude_code</option>
                  <option>local_faster_whisper</option>
                  <option>openai_compatible_stt</option>
                  <option>browser_speech_synthesis</option>
                  <option>openai_compatible_tts</option>
                  <option>openai_compatible_embedding</option>
                  <option>custom_http</option>
                </select>
              </label>
              <label className="wide">
                Base URL
                <input
                  type="url"
                  value={editing.base_url}
                  onChange={(e) =>
                    setEditing({ ...editing, base_url: e.target.value })
                  }
                />
              </label>
              <label>
                Model
                <input
                  value={editing.model}
                  onChange={(e) =>
                    setEditing({ ...editing, model: e.target.value })
                  }
                />
              </label>
              <label>
                {t("Secret environment variable")}
                <input
                  value={editing.secret_ref}
                  pattern="[A-Za-z_][A-Za-z0-9_]*"
                  onChange={(e) =>
                    setEditing({ ...editing, secret_ref: e.target.value })
                  }
                />
              </label>
              <label>
                Timeout
                <input
                  type="number"
                  min="1"
                  max="600"
                  value={editing.timeout_seconds}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      timeout_seconds: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                Retries
                <input
                  type="number"
                  min="0"
                  max="5"
                  value={editing.max_retries}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      max_retries: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                CLI profile
                <input
                  value={editing.profile}
                  onChange={(e) =>
                    setEditing({ ...editing, profile: e.target.value })
                  }
                />
              </label>
              <label>
                Sandbox
                <select
                  value={editing.sandbox}
                  onChange={(e) =>
                    setEditing({ ...editing, sandbox: e.target.value })
                  }
                >
                  <option>read-only</option>
                  <option>workspace-write</option>
                </select>
              </label>
              <label>
                Approval policy
                <select
                  value={editing.approval_policy}
                  onChange={(e) =>
                    setEditing({ ...editing, approval_policy: e.target.value })
                  }
                >
                  <option>never</option>
                  <option>on-request</option>
                </select>
              </label>
              <label>
                Working directory
                <select
                  value={editing.working_directory_policy}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      working_directory_policy: e.target.value,
                    })
                  }
                >
                  <option>runtime-only</option>
                  <option>allowlisted-repository</option>
                </select>
              </label>
              <label className="switch wide">
                <input
                  type="checkbox"
                  checked={editing.network_access}
                  onChange={(e) =>
                    setEditing({ ...editing, network_access: e.target.checked })
                  }
                />
                <span />
                {t("Allow Engine CLI network access")}
              </label>
              <label className="wide">
                Advanced JSON
                <textarea
                  rows={6}
                  value={editing.extra}
                  onChange={(e) =>
                    setEditing({ ...editing, extra: e.target.value })
                  }
                />
              </label>
            </div>
            <footer>
              <button
                type="button"
                className="button"
                onClick={() => setEditing(null)}
              >
                {t("Cancel")}
              </button>
              <button className="button primary">
                <Save size={16} />
                {t("Save")}
              </button>
            </footer>
          </form>
        </div>
      )}
    </div>
  );
}
