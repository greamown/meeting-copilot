import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, ChevronRight, Download, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useDialogs } from "../components/DialogProvider";
import { useI18n } from "../i18n";
import {
  MeetingAnalytics,
  downloadExport,
  getMeeting,
  getMeetingAnalytics,
  getMeetings,
  post,
  remove,
} from "../lib/api";

const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${Math.round(value * 100)}%`;
const duration = (seconds: number, t: ReturnType<typeof useI18n>["t"]) =>
  seconds < 60
    ? t("{count} seconds", { count: Math.round(seconds) })
    : `${Math.floor(seconds / 3600) ? t("{count} hours", { count: Math.floor(seconds / 3600) }) + " " : ""}${t("{count} minutes", { count: Math.round((seconds % 3600) / 60) })}`;

function Analytics({ id }: { id: string }) {
  const { t } = useI18n();
  const query = useQuery({
    queryKey: ["analytics", id],
    queryFn: () => getMeetingAnalytics(id),
  });
  if (query.isPending) return <div className="empty">{t("Calculating")}</div>;
  if (!query.data)
    return (
      <div className="empty">
        <strong>{t("Unable to calculate analytics")}</strong>
        <small>{query.error instanceof Error ? query.error.message : ""}</small>
      </div>
    );
  const a: MeetingAnalytics = query.data;
  return (
    <div className="analytics">
      <p className="provenance">
        {t(
          "All figures are calculated directly from the database without the reasoning engine. Duration source:",
        )}{" "}
        {a.duration_source === "meeting_timestamps"
          ? t("meeting start and end times")
          : t("transcript timeline (estimated)")}
        .
      </p>
      <div className="detail-summary">
        <div>
          <span>{t("Meeting duration")}</span>
          <strong>{duration(a.duration_seconds, t)}</strong>
        </div>
        <div>
          <span>{t("Transcript characters")}</span>
          <strong>{a.transcript.characters}</strong>
        </div>
        <div>
          <span>{t("decisions")}</span>
          <strong>{a.decisions.total}</strong>
        </div>
        <div>
          <span>{t("actions")}</span>
          <strong>{a.actions.total}</strong>
        </div>
        <div>
          <span>{t("Overdue actions")}</span>
          <strong className={a.actions.overdue ? "danger-text" : ""}>
            {a.actions.overdue}
          </strong>
        </div>
        <div>
          <span>{t("Unresolved questions")}</span>
          <strong>{percent(a.effectiveness.unresolved_question_ratio)}</strong>
        </div>
      </div>
      <div className="analytics-grid">
        <section className="section-card">
          <h3>{t("Suggestion handling")}</h3>
          <dl className="record-detail">
            <div>
              <dt>{t("Total")}</dt>
              <dd>{a.suggestions.total}</dd>
            </div>
            {(["accepted", "edited", "converted", "ignored"] as const).map(
              (key) => (
                <div key={key}>
                  <dt>{t(key)}</dt>
                  <dd>{percent(a.suggestion_rates[key])}</dd>
                </div>
              ),
            )}
          </dl>
        </section>
        <section className="section-card">
          <h3>{t("Action quality")}</h3>
          <dl className="record-detail">
            <div>
              <dt>{t("With owner")}</dt>
              <dd>{percent(a.effectiveness.actions_with_owner_ratio)}</dd>
            </div>
            <div>
              <dt>{t("With due date")}</dt>
              <dd>{percent(a.effectiveness.actions_with_due_date_ratio)}</dd>
            </div>
            <div>
              <dt>{t("Completed")}</dt>
              <dd>
                {a.actions.completed} / {a.actions.total}
              </dd>
            </div>
            <div>
              <dt>{t("Average completion time")}</dt>
              <dd>
                {a.actions.average_completion_hours == null
                  ? "—"
                  : t("{count} hours", {
                      count: a.actions.average_completion_hours,
                    })}
              </dd>
            </div>
            <div>
              <dt>{t("Decisions per hour")}</dt>
              <dd>{a.effectiveness.decisions_per_hour ?? "—"}</dd>
            </div>
          </dl>
        </section>
        <section className="section-card">
          <h3>{t("Engine runs")}</h3>
          <dl className="record-detail">
            <div>
              <dt>{t("Runs")}</dt>
              <dd>{a.engine_runs.total}</dd>
            </div>
            <div>
              <dt>{t("Average duration")}</dt>
              <dd>
                {a.engine_runs.average_duration_ms == null
                  ? "—"
                  : `${Math.round(a.engine_runs.average_duration_ms)} ms`}
              </dd>
            </div>
            <div>
              <dt>{t("Failure rate")}</dt>
              <dd>{percent(a.engine_runs.failure_rate)}</dd>
            </div>
            <div>
              <dt>{t("Timeout rate")}</dt>
              <dd>{percent(a.engine_runs.timeout_rate)}</dd>
            </div>
          </dl>
        </section>
        <section className="section-card">
          <h3>{t("Speaking time")}</h3>
          {a.transcript.speakers.length ? (
            <>
              <dl className="record-detail">
                {a.transcript.speakers.map((row) => (
                  <div key={row.speaker_id}>
                    <dt>{row.speaker_id}</dt>
                    <dd>
                      {duration(row.seconds, t)} · {percent(row.share)}
                    </dd>
                  </div>
                ))}
              </dl>
              <small>
                {t("Only speaker-labelled segments are included")} (
                {percent(a.transcript.speaker_labelled_ratio)}
                ). {t("The system does not separate speakers automatically.")}
              </small>
            </>
          ) : (
            <p className="prose">
              {t(
                "The transcript has no speaker labels, so speaking share cannot be calculated.",
              )}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

export function History() {
  const { t } = useI18n();
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: getMeetings });
  const [filter, setFilter] = useState("");
  const rows =
    meetings.data?.filter((item) =>
      item.title.toLowerCase().includes(filter.toLowerCase()),
    ) ?? [];
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">ARCHIVE</p>
          <h1>{t("Meeting history")}</h1>
          <p>{t("Review transcripts, decisions, Codex runs, and exports.")}</p>
        </div>
        <div className="search large">
          <Search />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t("Search by title")}
          />
        </div>
      </header>
      <div className="meeting-table">
        <div className="table-head">
          <span>{t("Meeting")}</span>
          <span>{t("Status")}</span>
          <span>{t("Start time")}</span>
          <span>{t("Language")}</span>
          <span />
        </div>
        {rows.map((item) => (
          <Link to={`/history/${item.id}`} key={item.id}>
            <div>
              <strong className="truncate" title={item.title}>
                {item.title}
              </strong>
              <small className="truncate" title={item.goal}>
                {item.goal}
              </small>
            </div>
            <span className={`status-label ${item.status}`}>{item.status}</span>
            <span>
              {item.started_at
                ? new Date(item.started_at).toLocaleString()
                : t("Not started")}
            </span>
            <span>{item.language}</span>
            <ChevronRight />
          </Link>
        ))}
        {rows.length === 0 && (
          <div className="empty">
            <Calendar />
            <strong>{t("No meetings found")}</strong>
          </div>
        )}
      </div>
    </div>
  );
}

export function HistoryDetail() {
  const dialogs = useDialogs();
  const { t } = useI18n();
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const detail = useQuery({
    queryKey: ["meeting", id],
    queryFn: () => getMeeting(id),
  });
  const [tab, setTab] = useState("transcript");
  const data = detail.data;
  if (!data)
    return (
      <div className="page">
        <div className="empty">{t("loading")}</div>
      </div>
    );
  const removeMeeting = async () => {
    if (
      !(await dialogs.confirm({
        title: t("Delete meeting"),
        message: t(
          "Permanently delete this meeting, transcript, and events? This cannot be undone.",
        ),
        confirmLabel: t("Delete permanently"),
        danger: true,
      }))
    )
      return;
    await remove(`/meetings/${id}`);
    await client.invalidateQueries({ queryKey: ["meetings"] });
    navigate("/history");
  };
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">MEETING DETAIL · {data.meeting.status}</p>
          <h1>{data.meeting.title}</h1>
          <p>{data.meeting.goal}</p>
        </div>
        <div className="head-actions">
          <button
            className="button"
            onClick={() => void post(`/meetings/${id}/analyze`)}
          >
            {t("Analyze again")}
          </button>
          <button
            className="icon-button danger"
            title={t("Delete meeting")}
            onClick={() => void removeMeeting()}
          >
            <Trash2 />
          </button>
        </div>
      </header>
      <div className="detail-summary">
        <div>
          <span>{t("Transcript")}</span>
          <strong>{data.transcripts.length}</strong>
        </div>
        <div>
          <span>{t("Suggestion acceptance rate")}</span>
          <strong>
            {data.suggestions.length
              ? `${Math.round((data.suggestions.filter((x) => x.status === "accepted").length / data.suggestions.length) * 100)}%`
              : "—"}
          </strong>
        </div>
        <div>
          <span>Codex runs</span>
          <strong>{data.codex_runs.length}</strong>
        </div>
        <div>
          <span>{t("actions")}</span>
          <strong>{data.action_items.length}</strong>
        </div>
      </div>
      {data.meeting.audio_saved && (
        <audio
          className="meeting-audio"
          controls
          preload="metadata"
          src={`/api/meetings/${id}/audio`}
        />
      )}
      <div className="tabs">
        {(
          ["transcript", "suggestions", "state", "analytics", "codex"] as const
        ).map((item) => (
          <button
            className={tab === item ? "active" : ""}
            onClick={() => setTab(item)}
            key={item}
          >
            {t(item === "codex" ? "Codex runs" : item)}
          </button>
        ))}
      </div>
      <section className="detail-content">
        {tab === "transcript" &&
          data.transcripts.map((item) => (
            <div className="detail-row" key={item.id}>
              <time>{(item.start_ms / 1000).toFixed(1)}s</time>
              <p>{item.text}</p>
            </div>
          ))}
        {tab === "suggestions" &&
          data.suggestions.map((item) => (
            <div className="detail-row" key={item.id}>
              <span>{item.category}</span>
              <p>{item.content}</p>
              <strong>{item.status}</strong>
            </div>
          ))}
        {tab === "state" &&
          [
            [t("decisions"), data.decisions],
            [t("Open questions"), data.open_questions],
            [t("Risks"), data.risks],
            [t("actions"), data.action_items],
          ].map(([name, items]) => (
            <div className="state-group" key={String(name)}>
              <h3>{String(name)}</h3>
              {Array.isArray(items) &&
                items.map((item) => (
                  <p key={String(item.id)}>{String(item.content)}</p>
                ))}
            </div>
          ))}
        {tab === "analytics" && <Analytics id={id} />}
        {tab === "codex" &&
          data.codex_runs.map((run) => (
            <div className="detail-row" key={String(run.id)}>
              <code>{String(run.id).slice(0, 8)}</code>
              <p>
                {String(run.job_type)} · {String(run.trigger)}
              </p>
              <strong>{String(run.status)}</strong>
              <small>{String(run.sanitized_stderr || "")}</small>
            </div>
          ))}
      </section>
      <div className="export-bar">
        <Download />
        <strong>{t("Export")}</strong>
        {(["markdown", "json", "pdf", "vtt", "srt"] as const).map((format) => (
          <button
            className="button"
            onClick={() => void downloadExport(id, format)}
            key={format}
          >
            {format.toUpperCase()}
          </button>
        ))}
        <button
          className="button danger"
          onClick={() =>
            void (async () => {
              if (
                await dialogs.confirm({
                  title: t("Delete meeting audio"),
                  message: t(
                    "Delete the saved original audio? The transcript and meeting data will remain.",
                  ),
                  confirmLabel: t("Delete audio"),
                  danger: true,
                })
              ) {
                await remove(`/meetings/${id}/audio`);
                await client.invalidateQueries({ queryKey: ["meeting", id] });
              }
            })()
          }
        >
          {t("Delete audio only")}
        </button>
      </div>
    </div>
  );
}
