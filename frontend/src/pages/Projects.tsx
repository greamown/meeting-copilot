import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  BookOpen,
  Edit3,
  FolderKanban,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useDialogs } from "../components/DialogProvider";
import { useI18n } from "../i18n";
import {
  GlossaryEntry,
  LanguageCode,
  Project,
  ProjectMemory,
  getMeetings,
  getProject,
  getProjectGlossary,
  getProjectMemory,
  getProjects,
  post,
  put,
  remove,
} from "../lib/api";

const languages: LanguageCode[] = ["zh-TW", "zh-CN", "en", "ja", "ko"];
const categories = [
  "architecture",
  "apis",
  "data_model",
  "infrastructure",
  "security_constraints",
  "performance_constraints",
  "business_constraints",
  "naming_conventions",
  "coding_conventions",
  "deployment_conventions",
  "known_risks",
  "lessons_learned",
  "rejected_alternatives",
  "glossary",
  "stakeholders",
  "project_goals",
  "project_non_goals",
];
type MemoryForm = Pick<
  ProjectMemory,
  | "category"
  | "title"
  | "content"
  | "source_meeting_id"
  | "source_decision_id"
  | "confidence"
  | "status"
>;
const emptyProject = {
  name: "",
  description: "",
  goals: "",
  non_goals: "",
  default_language: "zh-TW" as LanguageCode,
};
const emptyGlossary = {
  term: "",
  language: "zh-TW" as LanguageCode,
  preferred_spelling: "",
  translation: "",
  description: "",
  aliases: "",
  do_not_translate: false,
};
const emptyMemory: MemoryForm = {
  category: "architecture",
  title: "",
  content: "",
  source_meeting_id: null,
  source_decision_id: null,
  confidence: 1,
  status: "active",
};

export function Projects() {
  const dialogs = useDialogs();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Project | null | undefined>();
  const [form, setForm] = useState(emptyProject);
  const [error, setError] = useState("");
  const open = (project?: Project) => {
    setEditing(project ?? null);
    setForm(
      project
        ? {
            name: project.name,
            description: project.description,
            goals: project.goals,
            non_goals: project.non_goals,
            default_language: project.default_language,
          }
        : emptyProject,
    );
    setError("");
  };
  const save = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      if (editing) await put(`/projects/${editing.id}`, form);
      else await post("/projects", form);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditing(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Save failed"));
    }
  };
  const destroy = async (project: Project) => {
    if (
      !(await dialogs.confirm({
        title: t("Delete project"),
        message: t(
          "Delete project “{name}” and its glossary and memory? Meetings will remain.",
          { name: project.name },
        ),
        confirmLabel: t("Delete"),
        danger: true,
      }))
    )
      return;
    await remove(`/projects/${project.id}`);
    await queryClient.invalidateQueries({ queryKey: ["projects"] });
  };
  const rows = (projects.data ?? []).filter((item) =>
    `${item.name} ${item.description}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">PROJECTS</p>
          <h1>{t("Projects")}</h1>
          <p>
            {t(
              "Manage goals, terminology, and long-term memory across meetings.",
            )}
          </p>
        </div>
        <div className="head-actions">
          <button className="button primary" onClick={() => open()}>
            <Plus size={17} />
            {t("New project")}
          </button>
        </div>
      </header>
      <div className="project-toolbar">
        <div className="search large">
          <Search size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("Search projects")}
          />
        </div>
        <span>{t("{count} projects", { count: rows.length })}</span>
      </div>
      <div className="project-grid">
        {rows.map((project) => (
          <article className="project-card" key={project.id}>
            <header>
              <FolderKanban />
              <span>{project.default_language}</span>
            </header>
            <Link to={`/projects/${project.id}`}>
              <h2>{project.name}</h2>
              <p>{project.description || t("No project description")}</p>
            </Link>
            <dl>
              <div>
                <dt>{t("Goal")}</dt>
                <dd>{project.goals || t("Not configured")}</dd>
              </div>
              <div>
                <dt>{t("Updated")}</dt>
                <dd>{new Date(project.updated_at).toLocaleDateString()}</dd>
              </div>
            </dl>
            <footer>
              <Link className="button" to={`/projects/${project.id}`}>
                {t("Open dashboard")}
              </Link>
              <button
                className="icon-button"
                title={t("Edit project")}
                onClick={() => open(project)}
              >
                <Edit3 size={15} />
              </button>
              <button
                className="icon-button danger"
                title={t("Delete project")}
                onClick={() => void destroy(project)}
              >
                <Trash2 size={15} />
              </button>
            </footer>
          </article>
        ))}
        {!rows.length && (
          <div className="empty full">
            <FolderKanban />
            <strong>{t("No matching projects")}</strong>
            <button className="button" onClick={() => open()}>
              {t("Create first project")}
            </button>
          </div>
        )}
      </div>
      {editing !== undefined && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={(event) => void save(event)}>
            <header>
              <h2>{editing ? t("Edit project") : t("New project")}</h2>
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
              <label className="wide">
                {t("Name")}
                <input
                  required
                  maxLength={200}
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>
              <label className="wide">
                {t("Description")}
                <textarea
                  rows={3}
                  value={form.description}
                  onChange={(e) =>
                    setForm({ ...form, description: e.target.value })
                  }
                />
              </label>
              <label>
                {t("Default language")}
                <select
                  value={form.default_language}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      default_language: e.target.value as LanguageCode,
                    })
                  }
                >
                  {languages.map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <label className="wide">
                {t("Goal")}
                <textarea
                  rows={4}
                  value={form.goals}
                  onChange={(e) => setForm({ ...form, goals: e.target.value })}
                />
              </label>
              <label className="wide">
                {t("Non-goals")}
                <textarea
                  rows={3}
                  value={form.non_goals}
                  onChange={(e) =>
                    setForm({ ...form, non_goals: e.target.value })
                  }
                />
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

export function ProjectDashboard() {
  const dialogs = useDialogs();
  const { t } = useI18n();
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const project = useQuery({
    queryKey: ["project", id],
    queryFn: () => getProject(id),
  });
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: getMeetings });
  const glossary = useQuery({
    queryKey: ["project-glossary", id],
    queryFn: () => getProjectGlossary(id),
  });
  const memory = useQuery({
    queryKey: ["project-memory", id],
    queryFn: () => getProjectMemory(id),
  });
  const [tab, setTab] = useState<"overview" | "memory" | "glossary">(
    "overview",
  );
  const [search, setSearch] = useState("");
  const [glossaryEdit, setGlossaryEdit] = useState<
    GlossaryEntry | null | undefined
  >();
  const [glossaryForm, setGlossaryForm] = useState(emptyGlossary);
  const [memoryEdit, setMemoryEdit] = useState<
    ProjectMemory | null | undefined
  >();
  const [memoryForm, setMemoryForm] = useState(emptyMemory);
  const [error, setError] = useState("");
  const openGlossary = (entry?: GlossaryEntry) => {
    setGlossaryEdit(entry ?? null);
    setGlossaryForm(
      entry
        ? {
            term: entry.term,
            language: entry.language,
            preferred_spelling: entry.preferred_spelling,
            translation: entry.translation,
            description: entry.description,
            aliases: entry.aliases.join(", "),
            do_not_translate: entry.do_not_translate,
          }
        : emptyGlossary,
    );
    setError("");
  };
  const saveGlossary = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const payload = {
      ...glossaryForm,
      aliases: glossaryForm.aliases
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
    };
    try {
      if (glossaryEdit)
        await put(`/project-glossary/${glossaryEdit.id}`, payload);
      else await post(`/projects/${id}/glossary`, payload);
      await queryClient.invalidateQueries({
        queryKey: ["project-glossary", id],
      });
      await queryClient.invalidateQueries({ queryKey: ["project", id] });
      setGlossaryEdit(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Save failed"));
    }
  };
  const openMemory = (entry?: ProjectMemory) => {
    setMemoryEdit(entry ?? null);
    setMemoryForm(
      entry
        ? {
            category: entry.category,
            title: entry.title,
            content: entry.content,
            source_meeting_id: entry.source_meeting_id,
            source_decision_id: entry.source_decision_id,
            confidence: entry.confidence,
            status: entry.status,
          }
        : emptyMemory,
    );
    setError("");
  };
  const saveMemory = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      if (memoryEdit) await put(`/project-memory/${memoryEdit.id}`, memoryForm);
      else await post(`/projects/${id}/memory`, memoryForm);
      await queryClient.invalidateQueries({ queryKey: ["project-memory", id] });
      await queryClient.invalidateQueries({ queryKey: ["project", id] });
      setMemoryEdit(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("Save failed"));
    }
  };
  const archive = async (entry: ProjectMemory) => {
    await put(`/project-memory/${entry.id}`, { ...entry, status: "archived" });
    await queryClient.invalidateQueries({ queryKey: ["project-memory", id] });
  };
  const removeGlossary = async (entry: GlossaryEntry) => {
    if (
      !(await dialogs.confirm({
        title: t("Delete term"),
        message: t("Delete term “{name}”?", { name: entry.term }),
        confirmLabel: t("Delete"),
        danger: true,
      }))
    )
      return;
    await remove(`/project-glossary/${entry.id}`);
    await queryClient.invalidateQueries({ queryKey: ["project-glossary", id] });
    await queryClient.invalidateQueries({ queryKey: ["project", id] });
  };
  const removeMemory = async (entry: ProjectMemory) => {
    if (
      !(await dialogs.confirm({
        title: t("Permanently delete project memory"),
        message: t(
          "Permanently delete memory “{name}”? This cannot be undone.",
          { name: entry.title },
        ),
        confirmLabel: t("Delete permanently"),
        danger: true,
      }))
    )
      return;
    await remove(`/project-memory/${entry.id}`);
    await queryClient.invalidateQueries({ queryKey: ["project-memory", id] });
    await queryClient.invalidateQueries({ queryKey: ["project", id] });
  };
  if (project.isPending)
    return (
      <div className="page">
        <div className="empty">{t("Loading project")}</div>
      </div>
    );
  if (!project.data)
    return (
      <div className="page">
        <div className="alert error">{t("Project not found")}</div>
      </div>
    );
  const data = project.data;
  const recent = (meetings.data ?? [])
    .filter((x) => x.project_id === id)
    .slice(0, 5);
  const memories = (memory.data ?? []).filter((x) =>
    `${x.title} ${x.content}`.toLowerCase().includes(search.toLowerCase()),
  );
  const terms = (glossary.data ?? []).filter((x) =>
    `${x.term} ${x.preferred_spelling} ${x.description}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">PROJECT · {data.default_language}</p>
          <h1>{data.name}</h1>
          <p>{data.description || t("No description")}</p>
        </div>
        <div className="head-actions">
          <Link className="button primary" to={`/meetings/new?project=${id}`}>
            <Plus size={16} />
            {t("Start meeting")}
          </Link>
        </div>
      </header>
      <div className="detail-summary">
        <div>
          <span>{t("Meeting")}</span>
          <strong>{data.meeting_count}</strong>
        </div>
        <div>
          <span>{t("Project memory")}</span>
          <strong>{data.memory_count}</strong>
        </div>
        <div>
          <span>{t("Terms")}</span>
          <strong>{data.glossary_count}</strong>
        </div>
        <div>
          <span>{t("Default language")}</span>
          <strong>{data.default_language}</strong>
        </div>
      </div>
      <div className="tabs">
        {(["overview", "memory", "glossary"] as const).map((x) => (
          <button
            className={tab === x ? "active" : ""}
            onClick={() => {
              setTab(x);
              setSearch("");
            }}
            key={x}
          >
            {t(x)}
          </button>
        ))}
      </div>
      {tab === "overview" && (
        <div className="project-overview">
          <section className="section-card">
            <h2>{t("Project goals")}</h2>
            <p className="prose">{data.goals || t("Not configured")}</p>
            <h2>{t("Non-goals")}</h2>
            <p className="prose">{data.non_goals || t("Not configured")}</p>
          </section>
          <section className="section-card">
            <div className="section-title">
              <h2>{t("Recent meetings")}</h2>
            </div>
            {recent.map((x) => (
              <Link
                className="project-meeting"
                to={`/history/${x.id}`}
                key={x.id}
              >
                <span>{x.title}</span>
                <small>
                  {x.status} · {new Date(x.created_at).toLocaleDateString()}
                </small>
              </Link>
            ))}
            {!recent.length && (
              <div className="empty small">{t("No meetings yet")}</div>
            )}
          </section>
        </div>
      )}
      {tab !== "overview" && (
        <div className="project-toolbar">
          <div className="search large">
            <Search size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={
                tab === "memory" ? t("Search memory") : t("Search terms")
              }
            />
          </div>
          <button
            className="button primary"
            onClick={() => (tab === "memory" ? openMemory() : openGlossary())}
          >
            <Plus size={16} />
            {tab === "memory" ? t("Add memory") : t("Add term")}
          </button>
        </div>
      )}
      {tab === "memory" && (
        <div className="memory-list">
          {memories.map((entry) => (
            <article
              key={entry.id}
              className={entry.status === "archived" ? "archived" : ""}
            >
              <header>
                <span>{entry.category.replaceAll("_", " ")}</span>
                <small>
                  v{entry.version} · {Math.round(entry.confidence * 100)}% ·{" "}
                  {entry.status}
                </small>
              </header>
              <h3>{entry.title}</h3>
              <p>{entry.content}</p>
              <footer>
                <button className="button" onClick={() => openMemory(entry)}>
                  <Edit3 size={14} />
                  {t("Edit")}
                </button>
                {entry.status === "active" && (
                  <button
                    className="icon-button"
                    title={t("Archive")}
                    onClick={() => void archive(entry)}
                  >
                    <Archive size={15} />
                  </button>
                )}
                <button
                  className="icon-button danger"
                  title={t("Delete")}
                  onClick={() => void removeMemory(entry)}
                >
                  <Trash2 size={15} />
                </button>
              </footer>
            </article>
          ))}
          {!memories.length && (
            <div className="empty">
              <BookOpen />
              <strong>{t("No matching project memory")}</strong>
            </div>
          )}
        </div>
      )}
      {tab === "glossary" && (
        <div className="glossary-table">
          <div className="glossary-head">
            <span>{t("Term")}</span>
            <span>{t("Preferred spelling / translation")}</span>
            <span>{t("Language")}</span>
            <span>{t("Rules")}</span>
            <span />
          </div>
          {terms.map((entry) => (
            <div className="glossary-row" key={entry.id}>
              <div>
                <strong>{entry.term}</strong>
                <small>{entry.aliases.join(", ") || entry.description}</small>
              </div>
              <span>
                {entry.preferred_spelling || entry.translation || "—"}
              </span>
              <code>{entry.language}</code>
              <span>
                {entry.do_not_translate
                  ? t("Do not translate")
                  : t("Translatable")}
              </span>
              <div>
                <button
                  className="icon-button"
                  title={t("Edit")}
                  onClick={() => openGlossary(entry)}
                >
                  <Edit3 size={14} />
                </button>
                <button
                  className="icon-button danger"
                  title={t("Delete")}
                  onClick={() => void removeGlossary(entry)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
          {!terms.length && (
            <div className="empty">
              <BookOpen />
              <strong>{t("No matching terms")}</strong>
            </div>
          )}
        </div>
      )}
      {glossaryEdit !== undefined && (
        <div className="modal-backdrop">
          <form
            className="modal"
            onSubmit={(event) => void saveGlossary(event)}
          >
            <header>
              <h2>{glossaryEdit ? t("Edit term") : t("Add term")}</h2>
              <button
                type="button"
                className="icon-button"
                title={t("Close")}
                onClick={() => setGlossaryEdit(undefined)}
              >
                <X />
              </button>
            </header>
            <div className="form-grid">
              <label>
                {t("Term")}
                <input
                  required
                  value={glossaryForm.term}
                  onChange={(e) =>
                    setGlossaryForm({ ...glossaryForm, term: e.target.value })
                  }
                />
              </label>
              <label>
                {t("Language")}
                <select
                  value={glossaryForm.language}
                  onChange={(e) =>
                    setGlossaryForm({
                      ...glossaryForm,
                      language: e.target.value as LanguageCode,
                    })
                  }
                >
                  {languages.map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("Preferred spelling")}
                <input
                  value={glossaryForm.preferred_spelling}
                  onChange={(e) =>
                    setGlossaryForm({
                      ...glossaryForm,
                      preferred_spelling: e.target.value,
                    })
                  }
                />
              </label>
              <label>
                {t("Translation")}
                <input
                  value={glossaryForm.translation}
                  onChange={(e) =>
                    setGlossaryForm({
                      ...glossaryForm,
                      translation: e.target.value,
                    })
                  }
                />
              </label>
              <label className="wide">
                {t("Aliases (comma-separated)")}
                <input
                  value={glossaryForm.aliases}
                  onChange={(e) =>
                    setGlossaryForm({
                      ...glossaryForm,
                      aliases: e.target.value,
                    })
                  }
                />
              </label>
              <label className="wide">
                {t("Description")}
                <textarea
                  rows={3}
                  value={glossaryForm.description}
                  onChange={(e) =>
                    setGlossaryForm({
                      ...glossaryForm,
                      description: e.target.value,
                    })
                  }
                />
              </label>
              <label className="wide switch">
                <input
                  type="checkbox"
                  checked={glossaryForm.do_not_translate}
                  onChange={(e) =>
                    setGlossaryForm({
                      ...glossaryForm,
                      do_not_translate: e.target.checked,
                    })
                  }
                />
                {t("Do not translate this term")}
              </label>
            </div>
            {error && <div className="alert error">{error}</div>}
            <footer>
              <button
                type="button"
                className="button"
                onClick={() => setGlossaryEdit(undefined)}
              >
                {t("Cancel")}
              </button>
              <button className="button primary">{t("Save")}</button>
            </footer>
          </form>
        </div>
      )}
      {memoryEdit !== undefined && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={(event) => void saveMemory(event)}>
            <header>
              <h2>
                {memoryEdit
                  ? t("Edit project memory")
                  : t("Add project memory")}
              </h2>
              <button
                type="button"
                className="icon-button"
                title={t("Close")}
                onClick={() => setMemoryEdit(undefined)}
              >
                <X />
              </button>
            </header>
            <div className="form-grid">
              <label>
                {t("Category")}
                <select
                  value={memoryForm.category}
                  onChange={(e) =>
                    setMemoryForm({ ...memoryForm, category: e.target.value })
                  }
                >
                  {categories.map((x) => (
                    <option value={x} key={x}>
                      {x.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t("Status")}
                <select
                  value={memoryForm.status}
                  onChange={(e) =>
                    setMemoryForm({
                      ...memoryForm,
                      status: e.target.value as
                        "active" | "archived" | "superseded",
                    })
                  }
                >
                  <option value="active">active</option>
                  <option value="archived">archived</option>
                  <option value="superseded">superseded</option>
                </select>
              </label>
              <label className="wide">
                {t("Title")}
                <input
                  required
                  value={memoryForm.title}
                  onChange={(e) =>
                    setMemoryForm({ ...memoryForm, title: e.target.value })
                  }
                />
              </label>
              <label className="wide">
                {t("Content")}
                <textarea
                  required
                  rows={8}
                  value={memoryForm.content}
                  onChange={(e) =>
                    setMemoryForm({ ...memoryForm, content: e.target.value })
                  }
                />
              </label>
              <label className="wide">
                {t("Confidence")}{" "}
                <output>{Math.round(memoryForm.confidence * 100)}%</output>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={memoryForm.confidence}
                  onChange={(e) =>
                    setMemoryForm({
                      ...memoryForm,
                      confidence: Number(e.target.value),
                    })
                  }
                />
              </label>
            </div>
            {error && <div className="alert error">{error}</div>}
            <footer>
              <button
                type="button"
                className="button"
                onClick={() => setMemoryEdit(undefined)}
              >
                {t("Cancel")}
              </button>
              <button className="button primary">{t("Save")}</button>
            </footer>
          </form>
        </div>
      )}
      <button
        className="button project-back"
        onClick={() => navigate("/projects")}
      >
        {t("Back to projects")}
      </button>
    </div>
  );
}
