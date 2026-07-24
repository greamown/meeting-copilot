import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Download,
  FlaskConical,
  RefreshCw,
  Terminal,
} from "lucide-react";
import { post, request } from "../lib/api";
import { useDialogs } from "../components/DialogProvider";
import { useI18n } from "../i18n";

interface DiagnosticsData {
  os: string;
  python_version: string;
  docker_available: boolean;
  ffmpeg_available: boolean;
  codex: { installed: boolean; authenticated: boolean; version: string | null };
  gpu: {
    available: boolean;
    gpus: Array<{
      name: string;
      memory_total_mb: number;
      memory_used_mb: number;
      utilization_percent: number;
    }>;
  };
  database: { healthy: boolean; latency_ms: number };
  redis: {
    enabled: boolean;
    healthy: boolean | null;
    latency_ms: number | null;
  };
  metrics: Record<string, number | null>;
  providers: Array<{
    id: string;
    name: string;
    health: string;
    latency_ms: number | null;
  }>;
  events: Array<{
    id: string;
    sequence: number;
    type: string;
    source: string;
    created_at: string;
    payload: unknown;
  }>;
}
export function Diagnostics() {
  const { t } = useI18n();
  const dialogs = useDialogs();
  const diagnostics = useQuery({
    queryKey: ["diagnostics"],
    queryFn: () => request<DiagnosticsData>("/diagnostics"),
    refetchInterval: 10000,
  });
  const data = diagnostics.data;
  const bundle = () => {
    const anchor = document.createElement("a");
    anchor.href = "/api/diagnostics/bundle";
    anchor.click();
  };
  const metricLabels: Record<string, string> = {
    active_meetings: "Active meetings",
    audio_chunks_received: "Audio received",
    audio_chunks_dropped: "Audio dropped",
    stt_latency_ms: "STT latency ms",
    stt_real_time_factor: "STT RTF",
    stt_queue_depth: "STT queue",
    codex_queue_depth: "Codex queue",
    codex_latency_ms: "Codex latency ms",
    codex_success_rate: "Codex success",
    codex_failure_rate: "Codex failure",
    codex_timeout_rate: "Codex timeout",
    suggestions_generated: "Suggestions generated",
    suggestions_accepted: "Suggestions accepted",
    suggestions_ignored: "Suggestions ignored",
    duplicate_suggestions_suppressed: "Duplicates suppressed",
    tts_latency_ms: "TTS latency ms",
    websocket_connections: "WebSockets",
  };
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">OBSERVABILITY</p>
          <h1>{t("System diagnostics")}</h1>
          <p>{t("All events and errors are secret-redacted before output.")}</p>
        </div>
        <div className="head-actions">
          <button
            className="icon-button"
            title={t("refresh")}
            onClick={() => void diagnostics.refetch()}
          >
            <RefreshCw />
          </button>
          <button className="button" onClick={bundle}>
            <Download />
            {t("Diagnostic bundle")}
          </button>
        </div>
      </header>
      <div className="metric-grid compact">
        {Object.entries(metricLabels).map(([key, label]) => (
          <article className="metric" key={key}>
            <Activity />
            <span>{label}</span>
            <strong>{data?.metrics[key] ?? "—"}</strong>
          </article>
        ))}
        <article className="metric">
          <FlaskConical />
          <span>DB latency</span>
          <strong>{data ? `${data.database.latency_ms} ms` : "—"}</strong>
        </article>
        <article className="metric">
          <Terminal />
          <span>Redis latency</span>
          <strong>
            {data?.redis.latency_ms != null
              ? `${data.redis.latency_ms} ms`
              : "—"}
          </strong>
        </article>
      </div>
      <div className="diagnostic-grid">
        <section className="section-card">
          <h2>Providers</h2>
          {data?.providers.map((item) => (
            <div className="system-row" key={item.id}>
              <span>{item.name}</span>
              <strong>
                {item.health} {item.latency_ms && `· ${item.latency_ms} ms`}
              </strong>
              <button
                className="button"
                onClick={() =>
                  void post(`/providers/${item.id}/test`).then(() =>
                    diagnostics.refetch(),
                  )
                }
              >
                {t("Test")}
              </button>
            </div>
          ))}
        </section>
        <section className="section-card">
          <h2>{t("Test actions")}</h2>
          <div className="button-stack">
            <button
              className="button"
              onClick={() =>
                void post("/codex/test").then((value) =>
                  dialogs.alert({
                    title: t("Codex test result"),
                    message: JSON.stringify(value, null, 2),
                  }),
                )
              }
            >
              {t("Run fixed Codex JSON task")}
            </button>
            <button
              className="button"
              onClick={() => {
                speechSynthesis.cancel();
                speechSynthesis.speak(
                  new SpeechSynthesisUtterance("Diagnostic speech test"),
                );
              }}
            >
              {t("Play test speech")}
            </button>
            <button
              className="button"
              onClick={() =>
                void post("/diagnostics/migrations").then((value) =>
                  dialogs.alert({
                    title: t("Migration validation result"),
                    message: JSON.stringify(value, null, 2),
                  }),
                )
              }
            >
              {t("Validate migrations")}
            </button>
          </div>
        </section>
      </div>
      <section className="event-log">
        <header>
          <h2>{t("Latest 100 events")}</h2>
          <code>sanitized</code>
        </header>
        {data?.events.map((item) => (
          <div key={item.id}>
            <time>{new Date(item.created_at).toLocaleTimeString()}</time>
            <span>#{item.sequence}</span>
            <strong>{item.type}</strong>
            <code>{item.source}</code>
            <pre>{JSON.stringify(item.payload)}</pre>
          </div>
        ))}
      </section>
    </div>
  );
}
