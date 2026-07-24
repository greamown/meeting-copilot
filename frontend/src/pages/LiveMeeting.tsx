import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Check,
  Clipboard,
  Edit3,
  Mic,
  Pause,
  Pin,
  Play,
  Search,
  Send,
  Square,
  Volume2,
  X,
} from "lucide-react";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import { csrfHeaders, getMeeting, patch, post, Suggestion } from "../lib/api";
import { useMicrophone } from "../hooks/useMicrophone";
import { useDialogs } from "../components/DialogProvider";
import { useI18n } from "../i18n";

export function takeNewSuggestion(
  suggestions: Suggestion[],
  seen: Set<string>,
) {
  const next = suggestions.find(
    (item) => !seen.has(item.id) && item.status !== "ignored",
  );
  suggestions.forEach((item) => seen.add(item.id));
  return next;
}

export function LiveMeeting() {
  const dialogs = useDialogs();
  const { t } = useI18n();
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const detail = useQuery({
    queryKey: ["meeting", id],
    queryFn: () => getMeeting(id),
    refetchInterval: 5000,
  });
  const mic = useMicrophone();
  const audioSocket = useRef<WebSocket | null>(null);
  const audioReconnect = useRef<number | null>(null);
  const recording = useRef(false);
  const playback = useRef<HTMLAudioElement | null>(null);
  const sequence = useRef(0);
  const seenSuggestions = useRef<Set<string> | null>(null);
  const [events, setEvents] = useState<Array<Record<string, unknown>>>([]);
  const [query, setQuery] = useState("");
  const [question, setQuestion] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(
    null,
  );
  const [job, setJob] = useState<{ run_id: string; status: string } | null>(
    null,
  );
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [autoSpeechOverride, setAutoSpeechOverride] = useState<boolean | null>(
    null,
  );
  const refresh = useCallback(
    () => void queryClient.invalidateQueries({ queryKey: ["meeting", id] }),
    [id, queryClient],
  );
  useEffect(() => {
    let closed = false;
    let ws: WebSocket | null = null;
    let timer: number | null = null;
    let attempt = 0;
    const connect = () => {
      const protocol = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(
        `${protocol}://${location.host}/api/meetings/${id}/events`,
      );
      ws.onopen = () => {
        attempt = 0;
        ws?.send("subscribe");
        refresh();
      };
      ws.onmessage = (event) => {
        const item = JSON.parse(event.data) as Record<string, unknown>;
        setEvents((old) => [...old.slice(-99), item]);
        if (
          String(item.type).startsWith("transcript.") ||
          String(item.type).startsWith("suggestion.") ||
          String(item.type).startsWith("codex.")
        )
          refresh();
      };
      ws.onclose = () => {
        if (!closed) {
          timer = window.setTimeout(
            connect,
            Math.min(1000 * 2 ** attempt++, 15000),
          );
        }
      };
    };
    connect();
    return () => {
      closed = true;
      if (timer !== null) clearTimeout(timer);
      ws?.close();
    };
  }, [id, refresh]);
  useEffect(() => {
    const started = detail.data?.meeting.started_at;
    if (!started) return;
    const tick = () =>
      setElapsed(
        Math.max(
          0,
          Math.floor((Date.now() - new Date(started).getTime()) / 1000),
        ),
      );
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [detail.data?.meeting.started_at]);
  const connectAudio = useCallback(async () => {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(
      `${protocol}://${location.host}/api/meetings/${id}/audio`,
    );
    ws.binaryType = "arraybuffer";
    audioSocket.current = ws;
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      ws.onerror = () =>
        reject(new Error(t("Unable to connect to audio service")));
    });
    ws.onclose = () => {
      if (recording.current) {
        audioReconnect.current = window.setTimeout(
          () => void connectAudio(),
          1000,
        );
      }
    };
  }, [id, t]);
  const startAudio = async () => {
    recording.current = true;
    setAudioError(null);
    try {
      await connectAudio();
      await mic.start(undefined, (chunk) => {
        const ws = audioSocket.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        const framed = new Uint8Array(chunk.byteLength + 8);
        new DataView(framed.buffer).setBigUint64(
          0,
          BigInt(sequence.current++),
          true,
        );
        framed.set(new Uint8Array(chunk), 8);
        ws.send(framed);
      });
    } catch (reason) {
      recording.current = false;
      audioSocket.current?.close();
      audioSocket.current = null;
      setAudioError(
        reason instanceof Error
          ? reason.message
          : t("Unable to start recording"),
      );
    }
  };
  const stopAudio = () => {
    recording.current = false;
    if (audioReconnect.current !== null) clearTimeout(audioReconnect.current);
    audioReconnect.current = null;
    mic.stop();
    audioSocket.current?.close();
    audioSocket.current = null;
  };
  useEffect(() => stopAudio, []);
  const command = async (action: "pause" | "resume" | "end") => {
    if (action !== "resume") stopAudio();
    await post(`/meetings/${id}/${action}`);
    refresh();
    if (action === "end") navigate(`/history/${id}`);
  };
  const ask = async (event: FormEvent) => {
    event.preventDefault();
    const result = await post<{ run_id: string; status: string }>(
      `/meetings/${id}/ask`,
      { question, repository_context: false },
    );
    setJob(result);
    setQuestion("");
  };
  const addManualSuggestion = async () => {
    const content = await dialogs.prompt({
      title: t("Add manual suggestion"),
      message: t("Add a suggestion from a participant."),
      label: t("Suggestion content"),
      confirmLabel: t("Add"),
    });
    if (content)
      await post(`/meetings/${id}/suggestions`, {
        content,
        category: "other",
        reason: "Added by a meeting participant",
      }).then(refresh);
  };
  const suggestions = detail.data?.suggestions ?? [];
  const autoSpeech =
    autoSpeechOverride ??
    !Boolean(
      detail.data?.meeting.configuration_json.human_approval_before_speech ??
      true,
    );
  const displayLanguage = String(
    detail.data?.meeting.configuration_json.transcript_display_language ??
      "original",
  );
  const transcripts = (detail.data?.transcripts ?? []).filter((item) =>
    `${item.text} ${item.translated_text ?? ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const status = detail.data?.meeting.status;
  useEffect(() => {
    const list = document.querySelector<HTMLElement>(".transcript-list");
    if (autoScroll && list) list.scrollTop = list.scrollHeight;
  }, [autoScroll, transcripts.length]);
  const stopSpeech = () => {
    speechSynthesis.cancel();
    playback.current?.pause();
    playback.current = null;
    setSpeakingId(null);
  };
  const speak = async (item: Suggestion) => {
    if (item.status === "ignored") return;
    setSpeechError(null);
    if (speakingId === item.id) {
      stopSpeech();
      return;
    }
    stopSpeech();
    const response = await fetch(`/api/suggestions/${item.id}/speak`, {
      method: "POST",
      credentials: "same-origin",
      headers: csrfHeaders(),
    });
    if (!response.ok) throw new Error("TTS failed");
    setSpeakingId(item.id);
    if (response.headers.get("content-type")?.includes("application/json")) {
      const payload = (await response.json()) as {
        text: string;
        language: string;
        voice: string;
        rate: number;
        volume: number;
      };
      const utterance = new SpeechSynthesisUtterance(payload.text);
      utterance.lang = payload.language;
      utterance.rate = payload.rate;
      utterance.volume = payload.volume;
      const voice = speechSynthesis
        .getVoices()
        .find(
          (value) =>
            value.name === payload.voice ||
            value.lang.startsWith(payload.language),
        );
      if (voice) utterance.voice = voice;
      utterance.onend = () => setSpeakingId(null);
      utterance.onerror = () => setSpeakingId(null);
      speechSynthesis.speak(utterance);
    } else {
      const url = URL.createObjectURL(await response.blob());
      const audio = new Audio(url);
      playback.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        playback.current = null;
        setSpeakingId(null);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        playback.current = null;
        setSpeakingId(null);
      };
      await audio.play();
    }
  };
  useEffect(() => stopSpeech, []);
  const fmt = (seconds: number) =>
    `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor((seconds % 3600) / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  useEffect(() => {
    if (!detail.data) return;
    if (!seenSuggestions.current) {
      seenSuggestions.current = new Set(suggestions.map((item) => item.id));
      return;
    }
    const next = takeNewSuggestion(suggestions, seenSuggestions.current);
    if (autoSpeech && next)
      void speak(next).catch(() =>
        setSpeechError(t("Unable to play this suggestion automatically")),
      );
  }, [autoSpeech, detail.data, suggestions, t]);
  return (
    <div className="live">
      <header className="live-head">
        <div>
          <span className={`record-dot ${mic.active ? "active" : ""}`} />
          <div>
            <h1>{detail.data?.meeting.title ?? t("loading")}</h1>
            <span>
              {fmt(elapsed)} · {status}
            </span>
          </div>
        </div>
        <div className="live-status">
          <span>
            STT {audioError ? "ERROR" : mic.active ? "STREAMING" : "READY"}
          </span>
          <span>CODEX {job?.status ?? "IDLE"}</span>
          <span>QUEUE 0</span>
        </div>
        <div className="head-actions">
          {!mic.active && status === "active" && (
            <button
              className="button"
              title={t("Start recording")}
              onClick={() => void startAudio()}
            >
              <Mic />
              {t("Start recording")}
            </button>
          )}
          {status === "active" ? (
            <button
              className="icon-button"
              title={t("Pause")}
              onClick={() => void command("pause")}
            >
              <Pause />
            </button>
          ) : (
            status === "paused" && (
              <button
                className="icon-button"
                title={t("Resume")}
                onClick={() => void command("resume")}
              >
                <Play />
              </button>
            )
          )}
          <button className="button danger" onClick={() => void command("end")}>
            <Square size={14} />
            {t("End")}
          </button>
        </div>
      </header>
      <div className="live-grid">
        <section className="transcript-panel">
          <div className="panel-head">
            <h2>{t("Live transcript")}</h2>
            <div className="search">
              <Search size={15} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("Search")}
              />
            </div>
            <label className="compact-toggle">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
              />
              {t("Auto-scroll")}
            </label>
          </div>
          {(audioError || mic.error) && (
            <div className="alert error">{audioError || mic.error}</div>
          )}
          <div className="transcript-list">
            {transcripts.length === 0 && (
              <div className="empty">
                <Mic />
                <strong>
                  {mic.active
                    ? t("Listening; captions appear in about 4 seconds")
                    : t("Start recording to receive transcripts")}
                </strong>
              </div>
            )}
            {transcripts.map((item) => (
              <article key={item.id} className={item.is_pinned ? "pinned" : ""}>
                <time>{fmt(Math.floor(item.start_ms / 1000))}</time>
                <div>
                  <span>
                    {item.speaker_id ?? "Speaker"} · {item.language}
                  </span>
                  {editing?.id === item.id ? (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        void patch(`/transcripts/${item.id}`, {
                          text: editing.text,
                          speaker_id: item.speaker_id,
                        }).then(() => {
                          setEditing(null);
                          refresh();
                        });
                      }}
                    >
                      <textarea
                        value={editing.text}
                        onChange={(e) =>
                          setEditing({ ...editing, text: e.target.value })
                        }
                      />
                      <button className="button">{t("Save")}</button>
                    </form>
                  ) : (
                    <>
                      <p>
                        {displayLanguage !== "original" &&
                        item.translated_language === displayLanguage &&
                        item.translated_text
                          ? item.translated_text
                          : item.text}
                      </p>
                      {item.translated_text && (
                        <p className="translation">
                          {displayLanguage === "original"
                            ? item.translated_text
                            : item.text}
                          <small>{item.translated_language}</small>
                        </p>
                      )}
                    </>
                  )}
                </div>
                <div className="row-tools">
                  <button
                    title={t("Edit source text")}
                    onClick={() => setEditing({ id: item.id, text: item.text })}
                  >
                    <Edit3 />
                  </button>
                  <button
                    title={t("Pin")}
                    onClick={() =>
                      void patch(`/transcripts/${item.id}`, {
                        text: item.text,
                        speaker_id: item.speaker_id,
                        is_pinned: !item.is_pinned,
                      }).then(refresh)
                    }
                  >
                    <Pin />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
        <aside className="suggestion-panel">
          <div className="panel-head">
            <h2>{t("AI suggestions")}</h2>
            <label className="compact-toggle">
              <input
                type="checkbox"
                checked={autoSpeech}
                onChange={(event) =>
                  setAutoSpeechOverride(event.target.checked)
                }
              />
              {t("Auto-read")}
            </label>
            <div className="button-row">
              <button
                className="button"
                onClick={() => void addManualSuggestion()}
              >
                {t("Manual suggestion")}
              </button>
              <button
                className="button"
                onClick={() =>
                  void post(`/meetings/${id}/analyze`).then((value) =>
                    setJob(value as { run_id: string; status: string }),
                  )
                }
              >
                <Bot size={15} />
                {t("Analyze now")}
              </button>
            </div>
          </div>
          {speechError && <div className="alert error">{speechError}</div>}
          <div className="suggestions">
            {suggestions.length === 0 && (
              <div className="empty small">
                <Bot />
                <strong>{t("No suggestions yet")}</strong>
                <span>
                  {t(
                    "Codex displays content only when it adds meaningful new value.",
                  )}
                </span>
              </div>
            )}
            {suggestions.map((item) => (
              <article key={item.id}>
                <header>
                  <span>{item.category.replaceAll("_", " ")}</span>
                  <strong>{Math.round(item.confidence * 100)}%</strong>
                </header>
                <p>{item.content}</p>
                <small>{item.reason}</small>
                <div className="suggestion-actions">
                  <button
                    title={t("Accept")}
                    onClick={() =>
                      void post(`/suggestions/${item.id}/accept`).then(refresh)
                    }
                  >
                    <Check />
                  </button>
                  <button
                    title={t("Ignore")}
                    onClick={() =>
                      void post(`/suggestions/${item.id}/ignore`).then(refresh)
                    }
                  >
                    <X />
                  </button>
                  <button
                    title={t("Copy")}
                    onClick={() =>
                      void navigator.clipboard.writeText(item.content)
                    }
                  >
                    <Clipboard />
                  </button>
                  <button
                    title={t("Edit suggestion")}
                    onClick={() =>
                      void dialogs
                        .prompt({
                          title: t("Edit AI suggestion"),
                          message: t("Update the suggestion and save it."),
                          label: t("Suggestion content"),
                          initialValue: item.content,
                          confirmLabel: t("Save"),
                        })
                        .then(
                          (content) =>
                            content &&
                            post(`/suggestions/${item.id}/edit`, {
                              content,
                            }).then(refresh),
                        )
                    }
                  >
                    <Edit3 />
                  </button>
                  <button
                    title={
                      speakingId === item.id ? t("Stop playback") : t("Play")
                    }
                    onClick={() => void speak(item)}
                    disabled={item.status === "ignored"}
                  >
                    <Volume2 />
                  </button>
                  {(
                    [
                      ["Decision", "to-decision"],
                      ["Open question", "to-question"],
                      ["Risk", "to-risk"],
                      ["Action item", "to-action"],
                    ] as const
                  ).map(([label, route]) => (
                    <button
                      className="text-action"
                      key={route}
                      onClick={() =>
                        void post(`/suggestions/${item.id}/${route}`).then(
                          refresh,
                        )
                      }
                    >
                      + {t(label)}
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>
          <form className="ask" onSubmit={(event) => void ask(event)}>
            <label>ASK CODEX</label>
            <textarea
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t("Ask about the current discussion…")}
            />
            <div>
              <span>{job && `${job.status} · ${job.run_id.slice(0, 8)}`}</span>
              {job && (
                <button
                  type="button"
                  className="button"
                  onClick={() =>
                    void post(`/codex-runs/${job.run_id}/cancel`).then(() =>
                      setJob({ ...job, status: "cancelled" }),
                    )
                  }
                >
                  {t("Cancel")}
                </button>
              )}
              <button className="button primary">
                <Send size={15} />
                {t("Send")}
              </button>
            </div>
          </form>
        </aside>
        <aside className="state-panel">
          <h2>{t("Meeting state")}</h2>
          {[
            [t("decisions"), detail.data?.decisions],
            [t("Open questions"), detail.data?.open_questions],
            [t("Risks"), detail.data?.risks],
            [t("actions"), detail.data?.action_items],
          ].map(([label, items]) => (
            <section key={String(label)}>
              <h3>
                {String(label)}{" "}
                <span>{Array.isArray(items) ? items.length : 0}</span>
              </h3>
              {Array.isArray(items) &&
                items.map((item) => (
                  <p key={String(item.id)}>{String(item.content)}</p>
                ))}
            </section>
          ))}
        </aside>
      </div>
    </div>
  );
}
