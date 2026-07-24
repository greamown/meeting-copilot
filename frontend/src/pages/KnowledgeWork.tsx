import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  CircleAlert,
  FilePlus2,
  GitCompare,
  ListTodo,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { useDialogs } from "../components/DialogProvider";
import { useI18n } from "../i18n";
import {
  ActionItem,
  Decision,
  KnowledgeSearchResult,
  Meeting,
  Project,
  getActions,
  getDecisions,
  getMeetings,
  getProjects,
  post,
  put,
  remove,
  searchKnowledge,
} from "../lib/api";

const decisionStatuses = [
  "draft",
  "proposed",
  "confirmed",
  "rejected",
  "superseded",
  "archived",
] as const;
const actionStatuses = [
  "open",
  "in_progress",
  "blocked",
  "completed",
  "archived",
] as const;
const priorities = ["low", "normal", "high", "urgent"] as const;

type DecisionForm = {
  meeting_id: string;
  project_id: string;
  title: string;
  description: string;
  owner: string;
  status: Decision["status"];
  confidence: number;
  evidence_segment_ids: string[];
};
const emptyDecision: DecisionForm = {
  meeting_id: "",
  project_id: "",
  title: "",
  description: "",
  owner: "",
  status: "draft",
  confidence: 1,
  evidence_segment_ids: [],
};

export function Decisions() {
  const { t } = useI18n();
  const client = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: getMeetings });
  const [q, setQ] = useState("");
  const [project, setProject] = useState("");
  const [status, setStatus] = useState("");
  const [owner, setOwner] = useState("");
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (project) params.set("project_id", project);
  if (status) params.set("status", status);
  if (owner) params.set("owner", owner);
  const query = `?${params}`;
  const decisions = useQuery({
    queryKey: ["decisions", query],
    queryFn: () => getDecisions(query),
  });
  const [editing, setEditing] = useState<Decision | null | undefined>();
  const [form, setForm] = useState<DecisionForm>(emptyDecision);
  const [selected, setSelected] = useState<Decision | null>(null);
  const [error, setError] = useState("");
  const open = (row?: Decision) => {
    setEditing(row ?? null);
    setForm(
      row
        ? {
            meeting_id: row.meeting_id,
            project_id: row.project_id ?? "",
            title: row.title,
            description: row.description,
            owner: row.owner ?? "",
            status: row.status,
            confidence: row.confidence,
            evidence_segment_ids: row.evidence_segment_ids_json,
          }
        : emptyDecision,
    );
    setError("");
  };
  const save = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const payload = {
      ...form,
      project_id: form.project_id || null,
      owner: form.owner || null,
    };
    try {
      if (editing) await put(`/decisions/${editing.id}`, payload);
      else await post("/decisions", payload);
      setEditing(undefined);
      await client.invalidateQueries({ queryKey: ["decisions"] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Save failed"));
    }
  };
  const command = async (row: Decision, action: "confirm" | "reject") => {
    await post(`/decisions/${row.id}/${action}`);
    setSelected(null);
    await client.invalidateQueries({ queryKey: ["decisions"] });
  };
  const lineage = (decisions.data ?? []).filter(
    (row) =>
      selected &&
      (row.id === selected.supersedes_id ||
        row.id === selected.superseded_by_id),
  );
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">DECISION HISTORY</p>
          <h1>{t("Decision timeline")}</h1>
          <p>
            {t(
              "Preserve every decision version, source meeting, and status transition.",
            )}
          </p>
        </div>
        <button className="button primary" onClick={() => open()}>
          <FilePlus2 size={16} />
          {t("Add decision")}
        </button>
      </header>
      <div className="work-filter">
        <div className="search large">
          <Search size={16} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("Search title or content")}
          />
        </div>
        <select value={project} onChange={(e) => setProject(e.target.value)}>
          <option value="">{t("All projects")}</option>
          {projects.data?.map((row) => (
            <option value={row.id} key={row.id}>
              {row.name}
            </option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t("All statuses")}</option>
          {decisionStatuses.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
        <input
          value={owner}
          onChange={(e) => setOwner(e.target.value)}
          placeholder={t("Owner")}
        />
      </div>
      <div className="timeline-list">
        {decisions.data?.map((row) => (
          <article key={row.id} className={`work-row ${row.status}`}>
            <button className="row-main" onClick={() => setSelected(row)}>
              <span className="timeline-mark" />
              <span>
                <strong>{row.title || row.description}</strong>
                <small>{row.description}</small>
              </span>
              <code>v{row.version}</code>
              <span className="status-label">{row.status}</span>
              <time>{new Date(row.created_at).toLocaleString()}</time>
            </button>
            <div className="row-actions">
              {!(
                ["confirmed", "rejected", "superseded", "archived"] as string[]
              ).includes(row.status) && (
                <>
                  <button
                    title={t("Confirm decision")}
                    onClick={() => void command(row, "confirm")}
                  >
                    <Check />
                  </button>
                  <button
                    title={t("Reject decision")}
                    onClick={() => void command(row, "reject")}
                  >
                    <X />
                  </button>
                </>
              )}{" "}
              {!(["superseded", "archived"] as string[]).includes(
                row.status,
              ) && (
                <button
                  title={t("Create new version")}
                  onClick={() => open(row)}
                >
                  <GitCompare />
                </button>
              )}
            </div>
          </article>
        ))}
        {!decisions.isPending && !decisions.data?.length && (
          <div className="empty">
            <GitCompare />
            <strong>{t("No matching decisions")}</strong>
          </div>
        )}
      </div>
      {selected && (
        <div className="modal-backdrop">
          <section className="modal">
            <header>
              <h2>{selected.title}</h2>
              <button
                className="icon-button"
                title={t("Close")}
                onClick={() => setSelected(null)}
              >
                <X />
              </button>
            </header>
            <dl className="record-detail">
              <div>
                <dt>{t("Status")}</dt>
                <dd>{selected.status}</dd>
              </div>
              <div>
                <dt>{t("Version")}</dt>
                <dd>v{selected.version}</dd>
              </div>
              <div>
                <dt>{t("Owner")}</dt>
                <dd>{selected.owner || t("Unassigned")}</dd>
              </div>
              <div>
                <dt>{t("Confidence")}</dt>
                <dd>{Math.round(selected.confidence * 100)}%</dd>
              </div>
              <div className="wide">
                <dt>{t("Content")}</dt>
                <dd>{selected.description}</dd>
              </div>
              <div className="wide">
                <dt>{t("Source meeting")}</dt>
                <dd>
                  {meetings.data?.find((row) => row.id === selected.meeting_id)
                    ?.title ?? selected.meeting_id}
                </dd>
              </div>
            </dl>
            {lineage.length > 0 && (
              <div className="version-compare">
                <h3>{t("Adjacent versions")}</h3>
                {lineage.map((row) => (
                  <button key={row.id} onClick={() => setSelected(row)}>
                    v{row.version} · {row.title} · {row.status}
                  </button>
                ))}
              </div>
            )}
            <footer>
              <button
                className="button"
                onClick={() => {
                  setSelected(null);
                  open(selected);
                }}
              >
                <GitCompare size={15} />
                {t("Create new version")}
              </button>
            </footer>
          </section>
        </div>
      )}
      {editing !== undefined && (
        <DecisionEditor
          row={editing}
          form={form}
          setForm={setForm}
          meetings={meetings.data ?? []}
          projects={projects.data ?? []}
          error={error}
          close={() => setEditing(undefined)}
          save={save}
        />
      )}
    </div>
  );
}

function DecisionEditor({
  row,
  form,
  setForm,
  meetings,
  projects,
  error,
  close,
  save,
}: {
  row: Decision | null;
  form: DecisionForm;
  setForm: (value: DecisionForm) => void;
  meetings: Meeting[];
  projects: Project[];
  error: string;
  close: () => void;
  save: (event: FormEvent) => Promise<void>;
}) {
  const { t } = useI18n();
  const chooseMeeting = (id: string) => {
    const meeting = meetings.find((item) => item.id === id);
    setForm({ ...form, meeting_id: id, project_id: meeting?.project_id ?? "" });
  };
  return (
    <div className="modal-backdrop">
      <form className="modal" onSubmit={(event) => void save(event)}>
        <header>
          <h2>
            {row
              ? t("Create v{version}", { version: row.version + 1 })
              : t("Add decision")}
          </h2>
          <button
            type="button"
            className="icon-button"
            title={t("Close")}
            onClick={close}
          >
            <X />
          </button>
        </header>
        <div className="form-grid">
          <label>
            {t("Source meeting")}
            <select
              required
              disabled={Boolean(row)}
              value={form.meeting_id}
              onChange={(e) => chooseMeeting(e.target.value)}
            >
              <option value="">{t("Select meeting")}</option>
              {meetings.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("Project")}
            <select disabled value={form.project_id}>
              <option value="">{t("No project")}</option>
              {projects.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="wide">
            {t("Title")}
            <input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </label>
          <label className="wide">
            {t("Description")}
            <textarea
              rows={6}
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
            />
          </label>
          <label>
            {t("Owner")}
            <input
              value={form.owner}
              onChange={(e) => setForm({ ...form, owner: e.target.value })}
            />
          </label>
          <label>
            {t("Status")}
            <select
              value={form.status}
              onChange={(e) =>
                setForm({
                  ...form,
                  status: e.target.value as Decision["status"],
                })
              }
            >
              {decisionStatuses
                .filter(
                  (value) =>
                    !row || !["superseded", "archived"].includes(value),
                )
                .map((value) => (
                  <option key={value}>{value}</option>
                ))}
            </select>
          </label>
          <label className="wide">
            {t("Confidence")}{" "}
            <output>{Math.round(form.confidence * 100)}%</output>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={form.confidence}
              onChange={(e) =>
                setForm({ ...form, confidence: Number(e.target.value) })
              }
            />
          </label>
        </div>
        {error && <div className="alert error">{error}</div>}
        <footer>
          <button type="button" className="button" onClick={close}>
            {t("Cancel")}
          </button>
          <button className="button primary">
            {row ? t("Create new version") : t("Save")}
          </button>
        </footer>
      </form>
    </div>
  );
}

type ActionForm = {
  meeting_id: string;
  project_id: string;
  title: string;
  description: string;
  owner: string;
  due_at: string;
  priority: ActionItem["priority"];
  status: ActionItem["status"];
  linked_decision_id: string;
  evidence_segment_ids: string[];
};
const emptyAction: ActionForm = {
  meeting_id: "",
  project_id: "",
  title: "",
  description: "",
  owner: "",
  due_at: "",
  priority: "normal",
  status: "open",
  linked_decision_id: "",
  evidence_segment_ids: [],
};

export function Actions() {
  const dialogs = useDialogs();
  const { t } = useI18n();
  const client = useQueryClient();
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: getMeetings });
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const decisions = useQuery({
    queryKey: ["decisions", "actions"],
    queryFn: () => getDecisions(),
  });
  const actions = useQuery({
    queryKey: ["actions"],
    queryFn: () => getActions(),
  });
  const [view, setView] = useState("all");
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<ActionItem | null | undefined>();
  const [form, setForm] = useState<ActionForm>(emptyAction);
  const [error, setError] = useState("");
  const mine = localStorage.getItem("meeting-copilot-owner") ?? "";
  const now = Date.now();
  const rows = useMemo(
    () =>
      (actions.data ?? [])
        .filter((row) =>
          `${row.title} ${row.description} ${row.owner}`
            .toLowerCase()
            .includes(q.toLowerCase()),
        )
        .filter((row) => {
          const due = row.due_at ? new Date(row.due_at).getTime() : 0;
          if (view === "mine") return Boolean(mine) && row.owner === mine;
          if (view === "overdue")
            return (
              due > 0 &&
              due < now &&
              !(["completed", "archived"] as string[]).includes(row.status)
            );
          if (view === "due_soon")
            return due >= now && due <= now + 7 * 86400000;
          if (["in_progress", "blocked", "completed"].includes(view))
            return row.status === view;
          return view === "all";
        }),
    [actions.data, q, view, mine, now],
  );
  const open = (row?: ActionItem) => {
    setEditing(row ?? null);
    setForm(
      row
        ? {
            meeting_id: row.meeting_id,
            project_id: row.project_id ?? "",
            title: row.title,
            description: row.description,
            owner: row.owner ?? "",
            due_at: row.due_at
              ? new Date(row.due_at).toISOString().slice(0, 16)
              : "",
            priority: row.priority,
            status: row.status,
            linked_decision_id: row.linked_decision_id ?? "",
            evidence_segment_ids: row.evidence_segment_ids_json,
          }
        : emptyAction,
    );
    setError("");
  };
  const save = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const payload = {
      ...form,
      project_id: form.project_id || null,
      owner: form.owner || null,
      due_at: form.due_at ? new Date(form.due_at).toISOString() : null,
      linked_decision_id: form.linked_decision_id || null,
    };
    try {
      if (editing) await put(`/actions/${editing.id}`, payload);
      else await post("/actions", payload);
      setEditing(undefined);
      await client.invalidateQueries({ queryKey: ["actions"] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Save failed"));
    }
  };
  const destroy = async (row: ActionItem) => {
    if (
      !(await dialogs.confirm({
        title: t("Delete action item"),
        message: t("Delete action item “{name}”?", { name: row.title }),
        confirmLabel: t("Delete"),
        danger: true,
      }))
    )
      return;
    await remove(`/actions/${row.id}`);
    await client.invalidateQueries({ queryKey: ["actions"] });
  };
  const quickStatus = async (row: ActionItem, status: ActionItem["status"]) => {
    await put(`/actions/${row.id}`, {
      meeting_id: row.meeting_id,
      project_id: row.project_id,
      title: row.title,
      description: row.description,
      owner: row.owner,
      due_at: row.due_at,
      priority: row.priority,
      status,
      linked_decision_id: row.linked_decision_id,
      evidence_segment_ids: row.evidence_segment_ids_json,
    });
    await client.invalidateQueries({ queryKey: ["actions"] });
  };
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">ACTION TRACKER</p>
          <h1>{t("Action items")}</h1>
          <p>{t("Track work by owner, due date, priority, and status.")}</p>
        </div>
        <button className="button primary" onClick={() => open()}>
          <FilePlus2 size={16} />
          {t("Add item")}
        </button>
      </header>
      <div className="view-tabs">
        {(
          [
            "all",
            "mine",
            "overdue",
            "due_soon",
            "in_progress",
            "blocked",
            "completed",
          ] as const
        ).map((value) => (
          <button
            className={view === value ? "active" : ""}
            onClick={() => setView(value)}
            key={value}
          >
            {t(value)}
          </button>
        ))}
      </div>
      <div className="work-filter">
        <div className="search large">
          <Search size={16} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("Search work or owner")}
          />
        </div>
        <span>{t("{count} items", { count: rows.length })}</span>
      </div>
      <div className="action-table">
        <div className="action-head">
          <span>{t("Work")}</span>
          <span>{t("Owner")}</span>
          <span>{t("Due")}</span>
          <span>{t("Priority")}</span>
          <span>{t("Status")}</span>
          <span />
        </div>
        {rows.map((row) => (
          <div className="action-row" key={row.id}>
            <button className="action-title" onClick={() => open(row)}>
              <strong>{row.title}</strong>
              <small>{row.description}</small>
            </button>
            <span>{row.owner || t("Unassigned")}</span>
            <time
              className={
                row.due_at &&
                new Date(row.due_at).getTime() < now &&
                row.status !== "completed"
                  ? "overdue"
                  : ""
              }
            >
              {row.due_at ? new Date(row.due_at).toLocaleDateString() : "—"}
            </time>
            <code>{row.priority}</code>
            <select
              aria-label={t("{name} status", { name: row.title })}
              value={row.status}
              onChange={(e) =>
                void quickStatus(row, e.target.value as ActionItem["status"])
              }
            >
              {actionStatuses.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
            <button
              className="icon-button danger"
              title={t("Delete")}
              onClick={() => void destroy(row)}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {!rows.length && (
          <div className="empty">
            <ListTodo />
            <strong>{t("No action items in this view")}</strong>
          </div>
        )}
      </div>
      {editing !== undefined && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={(event) => void save(event)}>
            <header>
              <h2>{editing ? t("Edit action item") : t("Add action item")}</h2>
              <button
                type="button"
                className="icon-button"
                title={t("Close")}
                onClick={() => setEditing(undefined)}
              >
                <X />
              </button>
            </header>
            <div className="form-grid">
              <label>
                {t("Source meeting")}
                <select
                  required
                  value={form.meeting_id}
                  onChange={(e) => {
                    const meeting = meetings.data?.find(
                      (row) => row.id === e.target.value,
                    );
                    setForm({
                      ...form,
                      meeting_id: e.target.value,
                      project_id: meeting?.project_id ?? "",
                      linked_decision_id: "",
                    });
                  }}
                >
                  <option value="">{t("Select meeting")}</option>
                  {meetings.data?.map((row) => (
                    <option value={row.id} key={row.id}>
                      {row.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t("Project")}
                <select disabled value={form.project_id}>
                  <option value="">{t("No project")}</option>
                  {projects.data?.map((row) => (
                    <option value={row.id} key={row.id}>
                      {row.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="wide">
                {t("Title")}
                <input
                  required
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
              </label>
              <label className="wide">
                {t("Description")}
                <textarea
                  rows={5}
                  value={form.description}
                  onChange={(e) =>
                    setForm({ ...form, description: e.target.value })
                  }
                />
              </label>
              <label>
                {t("Owner")}
                <input
                  value={form.owner}
                  onChange={(e) => setForm({ ...form, owner: e.target.value })}
                />
              </label>
              <label>
                {t("Due date")}
                <input
                  type="datetime-local"
                  value={form.due_at}
                  onChange={(e) => setForm({ ...form, due_at: e.target.value })}
                />
              </label>
              <label>
                {t("Priority")}
                <select
                  value={form.priority}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      priority: e.target.value as ActionItem["priority"],
                    })
                  }
                >
                  {priorities.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("Status")}
                <select
                  value={form.status}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      status: e.target.value as ActionItem["status"],
                    })
                  }
                >
                  {actionStatuses.map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
              <label className="wide">
                {t("Linked decision")}
                <select
                  value={form.linked_decision_id}
                  onChange={(e) =>
                    setForm({ ...form, linked_decision_id: e.target.value })
                  }
                >
                  <option value="">{t("Not linked")}</option>
                  {decisions.data
                    ?.filter((row) => row.meeting_id === form.meeting_id)
                    .map((row) => (
                      <option value={row.id} key={row.id}>
                        v{row.version} · {row.title}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            {error && <div className="alert error">{error}</div>}
            <footer>
              <button
                type="button"
                className="button"
                onClick={() => setEditing(undefined)}
              >
                {t("Cancel")}
              </button>
              <button className="button primary">{t("Save")}</button>
            </footer>
          </form>
        </div>
      )}
    </div>
  );
}

export function Knowledge() {
  const dialogs = useDialogs();
  const { t } = useI18n();
  const client = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const [q, setQ] = useState("");
  const [project, setProject] = useState("");
  const [source, setSource] = useState("");
  const [submitted, setSubmitted] = useState("");
  const params = new URLSearchParams();
  params.set("q", submitted);
  if (project) params.set("project_id", project);
  if (source) params.set("source_type", source);
  const key = `?${params}`;
  const results = useQuery({
    queryKey: ["knowledge", key],
    queryFn: () => searchKnowledge(key),
  });
  const [creating, setCreating] = useState(false);
  const [preview, setPreview] = useState<KnowledgeSearchResult | null>(null);
  const [form, setForm] = useState({
    project_id: "",
    source_type: "uploaded",
    title: "",
    content: "",
    language: "zh-TW",
    metadata: {},
  });
  const [error, setError] = useState("");
  const save = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await post("/knowledge/documents", {
        ...form,
        project_id: form.project_id || null,
      });
      setCreating(false);
      setSubmitted(form.title);
      setQ(form.title);
      await client.invalidateQueries({ queryKey: ["knowledge"] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Creation failed"));
    }
  };
  const destroy = async (row: KnowledgeSearchResult) => {
    if (
      row.source_type !== "document" ||
      !(await dialogs.confirm({
        title: t("Delete knowledge document"),
        message: t("Delete document “{name}” and its indexed content?", {
          name: row.title,
        }),
        confirmLabel: t("Delete"),
        danger: true,
      }))
    )
      return;
    await remove(`/knowledge/documents/${row.id}`);
    setPreview(null);
    await client.invalidateQueries({ queryKey: ["knowledge"] });
  };
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">KNOWLEDGE BASE</p>
          <h1>{t("Knowledge base")}</h1>
          <p>
            {t(
              "Search meetings, transcripts, decisions, tasks, project memory, and documents.",
            )}
          </p>
        </div>
        <button className="button primary" onClick={() => setCreating(true)}>
          <FilePlus2 size={16} />
          {t("Add document")}
        </button>
      </header>
      <form
        className="knowledge-search"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(q);
        }}
      >
        <div className="search large">
          <Search size={17} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("Search all knowledge sources")}
          />
        </div>
        <select value={project} onChange={(e) => setProject(e.target.value)}>
          <option value="">{t("All projects")}</option>
          {projects.data?.map((row) => (
            <option value={row.id} key={row.id}>
              {row.name}
            </option>
          ))}
        </select>
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">{t("All sources")}</option>
          {[
            "document",
            "meeting",
            "transcript",
            "decision",
            "action",
            "risk",
            "question",
            "project_memory",
          ].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
        <button className="button primary">{t("Search")}</button>
      </form>
      <div className="knowledge-results">
        {results.data?.map((row) => (
          <button
            key={`${row.source_type}-${row.id}`}
            onClick={() => setPreview(row)}
          >
            <span className="source-badge">{row.source_type}</span>
            <span>
              <strong>{row.title}</strong>
              <small>{row.excerpt || t("No summary")}</small>
            </span>
            <time>{new Date(row.created_at).toLocaleDateString()}</time>
          </button>
        ))}
        {!results.isPending && !results.data?.length && (
          <div className="empty">
            <Search />
            <strong>{t("No matching knowledge found")}</strong>
          </div>
        )}
      </div>
      {preview && (
        <div className="modal-backdrop">
          <section className="modal">
            <header>
              <div>
                <span className="source-badge">{preview.source_type}</span>
                <h2>{preview.title}</h2>
              </div>
              <button
                className="icon-button"
                title={t("Close")}
                onClick={() => setPreview(null)}
              >
                <X />
              </button>
            </header>
            <p className="document-preview">{preview.excerpt}</p>
            <dl className="record-detail">
              <div>
                <dt>{t("Language")}</dt>
                <dd>{preview.language}</dd>
              </div>
              <div>
                <dt>{t("Status")}</dt>
                <dd>{preview.status || "—"}</dd>
              </div>
              <div>
                <dt>{t("Created date")}</dt>
                <dd>{new Date(preview.created_at).toLocaleString()}</dd>
              </div>
            </dl>
            <footer>
              {preview.source_type === "document" && (
                <button
                  className="button danger"
                  onClick={() => void destroy(preview)}
                >
                  <Trash2 size={15} />
                  {t("Delete document")}
                </button>
              )}
            </footer>
          </section>
        </div>
      )}
      {creating && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={(event) => void save(event)}>
            <header>
              <h2>{t("Add knowledge document")}</h2>
              <button
                type="button"
                className="icon-button"
                title={t("Close")}
                onClick={() => setCreating(false)}
              >
                <X />
              </button>
            </header>
            <div className="form-grid">
              <label>
                {t("Project")}
                <select
                  value={form.project_id}
                  onChange={(e) =>
                    setForm({ ...form, project_id: e.target.value })
                  }
                >
                  <option value="">{t("Global knowledge")}</option>
                  {projects.data?.map((row) => (
                    <option value={row.id} key={row.id}>
                      {row.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t("Language")}
                <select
                  value={form.language}
                  onChange={(e) =>
                    setForm({ ...form, language: e.target.value })
                  }
                >
                  {["zh-TW", "zh-CN", "en", "ja", "ko"].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
              <label className="wide">
                {t("Title")}
                <input
                  required
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
              </label>
              <label className="wide">
                {t("Content")}
                <textarea
                  required
                  rows={14}
                  value={form.content}
                  onChange={(e) =>
                    setForm({ ...form, content: e.target.value })
                  }
                />
              </label>
            </div>
            {error && (
              <div className="alert error">
                <CircleAlert size={15} />
                {error}
              </div>
            )}
            <footer>
              <button
                type="button"
                className="button"
                onClick={() => setCreating(false)}
              >
                {t("Cancel")}
              </button>
              <button className="button primary">{t("Create index")}</button>
            </footer>
          </form>
        </div>
      )}
    </div>
  );
}
