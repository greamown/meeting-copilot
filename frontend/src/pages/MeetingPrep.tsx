import { useQuery } from "@tanstack/react-query";
import { Mic, Play, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  LanguageCode,
  Meeting,
  getProjects,
  getProviders,
  getSettings,
  post,
} from "../lib/api";
import { useMicrophone } from "../hooks/useMicrophone";
import { useI18n } from "../i18n";

const languages: Array<[LanguageCode, string]> = [
  ["zh-TW", "繁體中文"],
  ["zh-CN", "简体中文"],
  ["en", "English"],
  ["ja", "日本語"],
  ["ko", "한국어"],
];
const defaults = {
  project_id: "",
  title: "",
  goal: "",
  language: "auto",
  secondary_language: "none",
  transcript_display_language: "original",
  translation_language: "none",
  analysis_language_mode: "original",
  suggestion_language: "zh-TW",
  summary_language: "zh-TW",
  export_language: "original",
  tts_language: "zh-TW",
  tts_voice: "",
  tts_rate: 1,
  tts_volume: 1,
  stt_provider_id: "local-stt-primary",
  tts_provider_id: "browser-tts",
  codex_profile: "",
  analysis_engine: "codex",
  automatic_analysis_enabled: true,
  analysis_interval_seconds: 120,
  suggestion_cooldown_seconds: 180,
  human_approval_before_speech: true,
  save_audio: false,
  repository_context_enabled: false,
  repository_path: "",
  repository_read_only: true,
  reference_notes: "",
  participants: "",
  privacy_acknowledged: false,
};

export function MeetingPrep() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: getProviders,
  });
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const settings = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const mic = useMicrophone();
  const [form, setForm] = useState({
    ...defaults,
    project_id: params.get("project") ?? "",
  });
  const [initialized, setInitialized] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (settings.data && !initialized) {
      const value = settings.data;
      setForm((current) => ({
        ...current,
        language: value.meeting_input_language,
        secondary_language: value.secondary_meeting_language,
        transcript_display_language: value.transcript_display_language,
        translation_language: value.translation_language,
        analysis_language_mode:
          value.translation_language === "none" ? "original" : "both",
        suggestion_language: value.suggestion_output_language,
        summary_language: value.summary_output_language,
        export_language: value.export_language,
        tts_language: value.tts_language,
        tts_voice: value.tts_voice,
        tts_rate: value.tts_rate,
        tts_volume: value.tts_volume,
        automatic_analysis_enabled: value.automatic_analysis_enabled,
        analysis_interval_seconds: value.periodic_analysis_seconds,
        suggestion_cooldown_seconds: value.suggestion_cooldown_seconds,
      }));
      setInitialized(true);
    }
  }, [settings.data, initialized]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      const meeting = await post<Meeting>("/meetings", {
        ...form,
        project_id: form.project_id || null,
        participants: form.participants
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        repository_path: form.repository_path || null,
      });
      await post(`/meetings/${meeting.id}/start`);
      navigate(`/meetings/${meeting.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Creation failed"));
    }
  };
  const field = <K extends keyof typeof form>(
    key: K,
    value: (typeof form)[K],
  ) => setForm((current) => ({ ...current, [key]: value }));
  const options = (special?: [string, string]) => (
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
          <p className="eyebrow">MEETING PREPARATION</p>
          <h1>{t("Prepare new meeting")}</h1>
          <p>
            {t(
              "Configure input, transcript, translation, analysis output, export, and speech languages independently.",
            )}
          </p>
        </div>
      </header>
      <form className="prep" onSubmit={(event) => void submit(event)}>
        <section>
          <h2>{t("Meeting details")}</h2>
          <div className="form-grid">
            <label>
              {t("Project")}
              <select
                value={form.project_id}
                onChange={(e) => field("project_id", e.target.value)}
              >
                <option value="">{t("No project")}</option>
                {projects.data?.map((project) => (
                  <option value={project.id} key={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="wide">
              {t("Title")}
              <input
                required
                maxLength={200}
                value={form.title}
                onChange={(e) => field("title", e.target.value)}
              />
            </label>
            <label className="wide">
              {t("Goal")}
              <textarea
                required
                rows={3}
                value={form.goal}
                onChange={(e) => field("goal", e.target.value)}
              />
            </label>
            <label>
              {t("Participants (comma-separated)")}
              <input
                value={form.participants}
                onChange={(e) => field("participants", e.target.value)}
              />
            </label>
            <label className="wide">
              {t("Reference notes")}
              <textarea
                rows={4}
                value={form.reference_notes}
                onChange={(e) => field("reference_notes", e.target.value)}
              />
            </label>
          </div>
        </section>
        <section>
          <h2>{t("languageMatrix")}</h2>
          <div className="form-grid">
            <label>
              {t("meetingInput")}
              <select
                value={form.language}
                onChange={(e) => field("language", e.target.value)}
              >
                {options(["auto", t("autoDetect")])}
              </select>
            </label>
            <label>
              {t("secondaryInput")}
              <select
                value={form.secondary_language}
                onChange={(e) => field("secondary_language", e.target.value)}
              >
                {options(["none", t("none")])}
              </select>
            </label>
            <label>
              {t("transcriptDisplay")}
              <select
                value={form.transcript_display_language}
                onChange={(e) =>
                  field("transcript_display_language", e.target.value)
                }
              >
                {options([
                  "original",
                  t("Original with available translation"),
                ])}
              </select>
            </label>
            <label>
              {t("translation")}
              <select
                value={form.translation_language}
                onChange={(e) => {
                  field("translation_language", e.target.value);
                  if (e.target.value === "none")
                    field("analysis_language_mode", "original");
                }}
              >
                {options(["none", t("noTranslation")])}
              </select>
            </label>
            <label>
              Codex {t("Analysis content")}
              <select
                value={form.analysis_language_mode}
                disabled={form.translation_language === "none"}
                onChange={(e) =>
                  field("analysis_language_mode", e.target.value)
                }
              >
                <option value="original">{t("original")}</option>
                <option value="translated">{t("translation")}</option>
                <option value="both">{t("Original and translation")}</option>
              </select>
            </label>
            <label>
              {t("Suggestion output")}
              <select
                value={form.suggestion_language}
                onChange={(e) => field("suggestion_language", e.target.value)}
              >
                {options()}
              </select>
            </label>
            <label>
              {t("Summary output")}
              <select
                value={form.summary_language}
                onChange={(e) => field("summary_language", e.target.value)}
              >
                {options()}
              </select>
            </label>
            <label>
              {t("export")}
              <select
                value={form.export_language}
                onChange={(e) => field("export_language", e.target.value)}
              >
                {options(["original", t("original")])}
              </select>
            </label>
            <label>
              TTS
              <select
                value={form.tts_language}
                onChange={(e) => field("tts_language", e.target.value)}
              >
                {options()}
              </select>
            </label>
          </div>
        </section>
        <section>
          <h2>{t("Audio and models")}</h2>
          <div className="form-grid">
            <label>
              STT
              <select
                value={form.stt_provider_id}
                onChange={(e) => field("stt_provider_id", e.target.value)}
              >
                {providers.data
                  ?.filter((p) => p.role === "stt")
                  .map((p) => (
                    <option value={p.id} key={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              TTS
              <select
                value={form.tts_provider_id}
                onChange={(e) => field("tts_provider_id", e.target.value)}
              >
                {providers.data
                  ?.filter((p) => p.role === "tts")
                  .map((p) => (
                    <option value={p.id} key={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              {t("Analysis engine")}
              <select
                value={form.analysis_engine}
                onChange={(e) => field("analysis_engine", e.target.value)}
              >
                <option value="codex">Codex</option>
                <option value="claude">Claude Code</option>
              </select>
            </label>
            <label>
              Codex profile
              <input
                value={form.codex_profile}
                disabled={form.analysis_engine !== "codex"}
                onChange={(e) => field("codex_profile", e.target.value)}
              />
            </label>
            <label>
              {t("Analysis interval (seconds)")}
              <input
                type="number"
                min="30"
                value={form.analysis_interval_seconds}
                onChange={(e) =>
                  field("analysis_interval_seconds", Number(e.target.value))
                }
              />
            </label>
            <label>
              {t("Suggestion cooldown (seconds)")}
              <input
                type="number"
                min="0"
                value={form.suggestion_cooldown_seconds}
                onChange={(e) =>
                  field("suggestion_cooldown_seconds", Number(e.target.value))
                }
              />
            </label>
          </div>
          <div className="meter">
            <i style={{ width: `${mic.level * 100}%` }} />
          </div>
          <button
            type="button"
            className="button"
            onClick={() => (mic.active ? mic.stop() : void mic.start())}
          >
            <Mic size={16} />
            {mic.active ? t("Stop microphone test") : t("Microphone test")}
          </button>
          {mic.error && <span className="field-error">{mic.error}</span>}
        </section>
        <section>
          <h2>{t("Policies and privacy")}</h2>
          <div className="toggle-list">
            <label>
              <input
                type="checkbox"
                checked={form.automatic_analysis_enabled}
                onChange={(e) =>
                  field("automatic_analysis_enabled", e.target.checked)
                }
              />
              <span>{t("Automatic analysis")}</span>
              <small>
                {t(
                  "Run Codex only when rules trigger and cooldown has elapsed",
                )}
              </small>
            </label>
            <label>
              <input
                type="checkbox"
                checked={!form.human_approval_before_speech}
                onChange={(e) =>
                  field("human_approval_before_speech", !e.target.checked)
                }
              />
              <span>{t("Automatically read AI suggestions")}</span>
              <small>
                {t(
                  "Play each new suggestion immediately with the selected TTS",
                )}
              </small>
            </label>
            <label>
              <input
                type="checkbox"
                checked={form.save_audio}
                onChange={(e) => field("save_audio", e.target.checked)}
              />
              <span>{t("Save original audio")}</span>
              <small>{t("Off by default")}</small>
            </label>
            <label>
              <input
                type="checkbox"
                checked={form.repository_context_enabled}
                onChange={(e) =>
                  field("repository_context_enabled", e.target.checked)
                }
              />
              <span>{t("Enable repository context")}</span>
              <small>
                {t("Must be inside the backend allowlist and read-only")}
              </small>
            </label>
            {form.repository_context_enabled && (
              <label className="path-field">
                Repository path
                <input
                  required
                  value={form.repository_path}
                  onChange={(e) => field("repository_path", e.target.value)}
                />
              </label>
            )}
            <label className="consent">
              <input
                required
                type="checkbox"
                checked={form.privacy_acknowledged}
                onChange={(e) =>
                  field("privacy_acknowledged", e.target.checked)
                }
              />
              <ShieldCheck />
              <span>
                {t(
                  "I have informed participants that microphone audio will be transcribed locally and agree to the storage settings above.",
                )}
              </span>
            </label>
          </div>
        </section>
        {error && <div className="alert error">{error}</div>}
        <footer className="form-footer">
          <button
            type="button"
            className="button"
            onClick={() => navigate("/")}
          >
            {t("Cancel")}
          </button>
          <button className="button primary">
            <Play size={16} />
            {t("Start meeting")}
          </button>
        </footer>
      </form>
    </div>
  );
}
