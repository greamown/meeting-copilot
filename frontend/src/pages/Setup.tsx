import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  LoaderCircle,
  Mic,
  RefreshCw,
  Volume2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getClaudeStatus,
  getCodexStatus,
  getProviders,
  getSettings,
  getSystem,
  LanguageCode,
  post,
  put,
  SettingsData,
} from "../lib/api";
import { useMicrophone } from "../hooks/useMicrophone";
import { useI18n } from "../i18n";
const languages: Array<[LanguageCode, string]> = [
  ["zh-TW", "繁體中文"],
  ["zh-CN", "簡體中文"],
  ["en", "English"],
  ["ja", "日本語"],
  ["ko", "한국어"],
];

export function Setup() {
  const { t } = useI18n();
  const steps = [
    t("System check"),
    t("Engine sign-in"),
    t("Reasoning engine"),
    t("STT settings"),
    t("TTS settings"),
    t("Language settings"),
    t("Microphone test"),
    t("Setup complete"),
  ];
  const [step, setStep] = useState(0);
  const [languageForm, setLanguageForm] = useState<SettingsData | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const system = useQuery({ queryKey: ["system"], queryFn: getSystem });
  const codex = useQuery({
    queryKey: ["codex-status"],
    queryFn: getCodexStatus,
  });
  const claude = useQuery({
    queryKey: ["claude-status"],
    queryFn: getClaudeStatus,
  });
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: getProviders,
  });
  const settings = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const mic = useMicrophone();
  const providerTest = useMutation({
    mutationFn: (id: string) =>
      post<{ healthy: boolean; detail: string }>(`/providers/${id}/test`),
  });
  const authLabel = (s?: { installed?: boolean; authenticated?: boolean }) =>
    !s?.installed
      ? t("notInstalled")
      : s.authenticated
        ? t("Signed in")
        : t("Signed out");
  const form = languageForm ?? settings.data ?? null;
  const updateLanguage = <K extends keyof SettingsData>(
    key: K,
    value: SettingsData[K],
  ) => {
    if (form) setLanguageForm({ ...form, [key]: value });
  };
  const checks = useMemo(() => {
    if (!system.data) return [];
    const gpu = system.data.gpu.gpus[0];
    return [
      {
        label: "Docker container",
        ok: system.data.docker_available,
        detail: system.data.docker_available
          ? `Docker API · ${t("available")}`
          : `Docker API · ${t("notDetected")}`,
        command: "docker compose up -d",
      },
      {
        label: "Docker Compose stack",
        ok: system.data.docker_compose_available ?? false,
        detail: system.data.docker_compose_available
          ? `Compose · ${t("available")}`
          : `Compose · ${t("notDetected")}`,
        command: "docker compose ps",
      },
      {
        label: "NVIDIA Container Toolkit",
        ok: system.data.nvidia_container_toolkit_available ?? false,
        detail: system.data.nvidia_container_toolkit_available
          ? `NVIDIA runtime · ${t("available")}`
          : (system.data.gpu.error ?? `NVIDIA runtime · ${t("notDetected")}`),
        command: "docker info --format '{{json .Runtimes}}'",
      },
      {
        label: "A6000 / CUDA",
        ok:
          system.data.gpu.available && (system.data.gpu.cuda_available ?? true),
        detail: gpu
          ? `${gpu.name} · driver ${gpu.driver_version} · ${Math.round(gpu.memory_total_mb / 1024)} GB`
          : (system.data.gpu.error ?? `CUDA device · ${t("notDetected")}`),
        command: "docker compose up -d --no-deps --force-recreate stt-worker",
      },
      {
        label: "FFmpeg",
        ok: system.data.ffmpeg_available,
        detail: system.data.ffmpeg_available
          ? `FFmpeg · ${t("Installed")}`
          : `FFmpeg · ${t("notDetected")}`,
        command: "docker compose build backend stt-worker",
      },
      {
        label: "Engine CLI (cli-worker)",
        ok: system.data.codex.installed && (claude.data?.installed ?? false),
        detail: system.data.codex.installed
          ? (system.data.codex.version ?? `Codex CLI · ${t("Installed")}`)
          : (system.data.codex.error ?? `Engine CLI · ${t("notDetected")}`),
        command: "docker compose ps cli-worker",
      },
      {
        label: "PostgreSQL",
        ok: system.data.database.healthy,
        detail: `${system.data.database.dialect} · ${system.data.database.latency_ms} ms`,
        command: "docker compose ps postgres",
      },
      {
        label: "Redis",
        ok: system.data.redis.healthy === true,
        detail: `Redis PING · ${system.data.redis.healthy ? t("Passed") : t("Needs attention")}`,
        command: "docker compose ps redis",
      },
      {
        label: "Disk space > 5 GB",
        ok: system.data.disk.free_gb > 5,
        detail: t("Available {free} GB / {total} GB", {
          free: system.data.disk.free_gb,
          total: system.data.disk.total_gb,
        }),
        command: "df -h .",
      },
    ];
  }, [system.data, claude.data?.installed, t]);
  const speak = () => {
    const utterance = new SpeechSynthesisUtterance(t("Speech test is working"));
    utterance.lang = form?.tts_language ?? "zh-TW";
    speechSynthesis.cancel();
    speechSynthesis.speak(utterance);
  };
  const complete = async () => {
    if (!form) return;
    await put("/settings", { ...form, setup_completed: true });
    localStorage.setItem("meeting-copilot-setup", "complete");
    await queryClient.invalidateQueries({ queryKey: ["settings"] });
    navigate("/");
  };
  const providerFor = (role: string) =>
    providers.data?.find((item) => item.role === role && item.is_default) ??
    providers.data?.find((item) => item.role === role);
  const optionList = (special?: [string, string]) => (
    <>
      {special && <option value={special[0]}>{special[1]}</option>}
      {languages.map(([code, label]) => (
        <option value={code} key={code}>
          {label}
        </option>
      ))}
    </>
  );

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">INITIAL SETUP</p>
          <h1>{t("Setup wizard")}</h1>
          <p>
            {t(
              "Settings are stored in the backend; credentials remain only in the local CLI or environment secrets.",
            )}
          </p>
        </div>
      </header>
      <div className="wizard">
        <ol>
          {steps.map((label, index) => (
            <li
              className={index === step ? "active" : index < step ? "done" : ""}
              key={label}
            >
              <span>{index < step ? <Check size={14} /> : index + 1}</span>
              {label}
            </li>
          ))}
        </ol>
        <section className="wizard-body">
          {step === 0 && (
            <>
              <h2>{t("System check")}</h2>
              <p>
                {t(
                  "Checks actual service health for Compose, GPU, database, and tools.",
                )}
              </p>
              <div className="check-list">
                {system.isPending ? (
                  <LoaderCircle className="spin" />
                ) : (
                  checks.map((check) => (
                    <div className={check.ok ? "" : "failed"} key={check.label}>
                      <span
                        className={`check-icon ${check.ok ? "pass" : "fail"}`}
                      >
                        {check.ok ? (
                          <Check size={16} />
                        ) : (
                          <CircleAlert size={16} />
                        )}
                      </span>
                      <span className="check-detail">
                        <strong>{check.label}</strong>
                        <small>{check.detail}</small>
                        {!check.ok && (
                          <code>
                            {t("Verify/fix: {command}", {
                              command: check.command,
                            })}
                          </code>
                        )}
                      </span>
                      <span>
                        {check.ok ? t("Passed") : t("Needs attention")}
                      </span>
                    </div>
                  ))
                )}
              </div>
              <button className="button" onClick={() => void system.refetch()}>
                <RefreshCw />
                {t("Recheck")}
              </button>
            </>
          )}
          {step === 1 && (
            <>
              <h2>{t("Engine sign-in")}</h2>
              <p>
                {t(
                  "The reasoning CLI is selected and signed in on the CLI sign-in page. Credentials remain in the local CLI.",
                )}
              </p>
              <div className="fact-grid">
                <div>
                  <span>Codex CLI</span>
                  <strong>{authLabel(codex.data)}</strong>
                </div>
                <div>
                  <span>Claude Code</span>
                  <strong>{authLabel(claude.data)}</strong>
                </div>
              </div>
              <div className="button-row">
                <button
                  className="button primary"
                  onClick={() => navigate("/cli-auth")}
                >
                  {t("Go to CLI sign-in")}
                </button>
              </div>
            </>
          )}
          {step === 2 && (
            <>
              <h2>{t("Reasoning engine")}</h2>
              <p>
                {t(
                  "Manage the reasoning provider profile, model, sandbox, and network policy here.",
                )}
              </p>
              {providerFor("reasoning") ? (
                <div className="fact-grid">
                  <div>
                    <span>Provider</span>
                    <strong>{providerFor("reasoning")?.name}</strong>
                  </div>
                  <div>
                    <span>Model</span>
                    <strong>
                      {providerFor("reasoning")?.model ?? "CLI default"}
                    </strong>
                  </div>
                  <div>
                    <span>Sandbox</span>
                    <strong>
                      {String(
                        providerFor("reasoning")?.extra.sandbox ?? "read-only",
                      )}
                    </strong>
                  </div>
                  <div>
                    <span>Network</span>
                    <strong>
                      {providerFor("reasoning")?.extra.network_access
                        ? "enabled"
                        : "disabled"}
                    </strong>
                  </div>
                </div>
              ) : (
                <div className="alert error">{t("No reasoning provider")}</div>
              )}
              <button
                className="button primary"
                onClick={() => navigate("/providers")}
              >
                {t("Manage providers")}
              </button>
            </>
          )}
          {step === 3 && (
            <>
              <h2>{t("STT settings")}</h2>
              <p>
                {t(
                  "Local faster-whisper prefers the A6000 and explicitly falls back to CPU on failure.",
                )}
              </p>
              <div className="fact-grid">
                <div>
                  <span>Provider</span>
                  <strong>
                    {providerFor("stt")?.name ?? t("Not configured")}
                  </strong>
                </div>
                <div>
                  <span>GPU</span>
                  <strong>
                    {system.data?.gpu.gpus[0]?.name ?? "Unavailable"}
                  </strong>
                </div>
                <div>
                  <span>Model</span>
                  <strong>
                    {providerFor("stt")?.model ?? "large-v3-turbo"}
                  </strong>
                </div>
                <div>
                  <span>Compute</span>
                  <strong>
                    {String(
                      providerFor("stt")?.extra.compute_type ?? "float16",
                    )}
                  </strong>
                </div>
              </div>
              {providerFor("stt") && (
                <button
                  className="button"
                  onClick={() => providerTest.mutate(providerFor("stt")!.id)}
                >
                  {t("Test STT provider")}
                </button>
              )}
              {providerTest.data && (
                <div
                  className={`alert ${providerTest.data.healthy ? "success" : "error"}`}
                >
                  {providerTest.data.detail}
                </div>
              )}
            </>
          )}
          {step === 4 && (
            <>
              <h2>{t("TTS settings")}</h2>
              <p>
                {t(
                  "Browser speech is the fallback; server TTS can be selected from the provider registry.",
                )}
              </p>
              <div className="fact-grid">
                <div>
                  <span>Default</span>
                  <strong>
                    {providerFor("tts")?.name ?? "Browser Speech"}
                  </strong>
                </div>
                <div>
                  <span>Language</span>
                  <strong>{form?.tts_language ?? "zh-TW"}</strong>
                </div>
              </div>
              <div className="button-row">
                <button className="button primary" onClick={speak}>
                  <Volume2 />
                  {t("Play test")}
                </button>
                <button
                  className="button"
                  onClick={() => speechSynthesis.cancel()}
                >
                  {t("Stop")}
                </button>
                {providerFor("tts") && (
                  <button
                    className="button"
                    onClick={() => providerTest.mutate(providerFor("tts")!.id)}
                  >
                    {t("Test provider")}
                  </button>
                )}
              </div>
            </>
          )}
          {step === 5 && form && (
            <>
              <h2>{t("Language settings")}</h2>
              <p>
                {t(
                  "Input, transcript, translation, suggestions, summary, export, and TTS languages are configured independently.",
                )}
              </p>
              <div className="form-grid">
                <label>
                  UI language
                  <select
                    value={form.ui_language}
                    onChange={(e) =>
                      updateLanguage(
                        "ui_language",
                        e.target.value as LanguageCode,
                      )
                    }
                  >
                    {optionList()}
                  </select>
                </label>
                <label>
                  Meeting input
                  <select
                    value={form.meeting_input_language}
                    onChange={(e) =>
                      updateLanguage(
                        "meeting_input_language",
                        e.target
                          .value as SettingsData["meeting_input_language"],
                      )
                    }
                  >
                    {optionList(["auto", t("autoDetect")])}
                  </select>
                </label>
                <label>
                  Secondary language
                  <select
                    value={form.secondary_meeting_language}
                    onChange={(e) =>
                      updateLanguage(
                        "secondary_meeting_language",
                        e.target
                          .value as SettingsData["secondary_meeting_language"],
                      )
                    }
                  >
                    {optionList(["none", t("none")])}
                  </select>
                </label>
                <label>
                  Transcript display
                  <select
                    value={form.transcript_display_language}
                    onChange={(e) =>
                      updateLanguage(
                        "transcript_display_language",
                        e.target
                          .value as SettingsData["transcript_display_language"],
                      )
                    }
                  >
                    {optionList(["original", t("original")])}
                  </select>
                </label>
                <label>
                  Translation
                  <select
                    value={form.translation_language}
                    onChange={(e) =>
                      updateLanguage(
                        "translation_language",
                        e.target.value as SettingsData["translation_language"],
                      )
                    }
                  >
                    {optionList(["none", t("noTranslation")])}
                  </select>
                </label>
                <label>
                  {t("Suggestion output")}
                  <select
                    value={form.suggestion_output_language}
                    onChange={(e) =>
                      updateLanguage(
                        "suggestion_output_language",
                        e.target.value as LanguageCode,
                      )
                    }
                  >
                    {optionList()}
                  </select>
                </label>
                <label>
                  {t("Summary output")}
                  <select
                    value={form.summary_output_language}
                    onChange={(e) =>
                      updateLanguage(
                        "summary_output_language",
                        e.target.value as LanguageCode,
                      )
                    }
                  >
                    {optionList()}
                  </select>
                </label>
                <label>
                  Export
                  <select
                    value={form.export_language}
                    onChange={(e) =>
                      updateLanguage(
                        "export_language",
                        e.target.value as SettingsData["export_language"],
                      )
                    }
                  >
                    {optionList(["original", t("original")])}
                  </select>
                </label>
                <label>
                  TTS
                  <select
                    value={form.tts_language}
                    onChange={(e) =>
                      updateLanguage(
                        "tts_language",
                        e.target.value as LanguageCode,
                      )
                    }
                  >
                    {optionList()}
                  </select>
                </label>
              </div>
            </>
          )}
          {step === 6 && (
            <>
              <h2>{t("Microphone test")}</h2>
              <p>
                {t(
                  "The browser shows live input level after permission; this test neither uploads nor saves audio.",
                )}
              </p>
              <div className="meter">
                <i style={{ width: `${mic.level * 100}%` }} />
              </div>
              {mic.error && <div className="alert error">{mic.error}</div>}
              <button
                className={`button ${mic.active ? "" : "primary"}`}
                onClick={() => (mic.active ? mic.stop() : void mic.start())}
              >
                <Mic />
                {mic.active ? t("Stop test") : t("Allow and test")}
              </button>
            </>
          )}
          {step === 7 && (
            <>
              <h2>{t("Save and start")}</h2>
              <p>
                {t(
                  "Core services are ready. You can change these settings later from Setup, CLI sign-in, and Models and endpoints.",
                )}
              </p>
              <button
                className="button primary"
                disabled={!form}
                onClick={() => void complete()}
              >
                {t("Save and open workspace")}
              </button>
            </>
          )}
          <footer>
            <button
              className="button"
              disabled={step === 0}
              onClick={() => setStep((value) => value - 1)}
            >
              <ChevronLeft />
              {t("Previous")}
            </button>
            {step < 7 && (
              <button
                className="button primary"
                onClick={() => setStep((value) => value + 1)}
              >
                {t("Next")}
                <ChevronRight />
              </button>
            )}
          </footer>
        </section>
      </div>
    </div>
  );
}
