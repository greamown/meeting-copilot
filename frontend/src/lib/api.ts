import { z } from "zod";

const healthSchema = z.object({ status: z.literal("ok"), service: z.string(), version: z.string() });

export const systemSchema = z.object({
  os: z.string(),
  python_version: z.string(),
  docker_available: z.boolean(),
  docker_compose_available: z.boolean().optional(),
  nvidia_container_toolkit_available: z.boolean().optional(),
  ffmpeg_available: z.boolean(),
  codex: z.object({ installed: z.boolean(), authenticated: z.boolean(), version: z.string().nullable(), profile: z.string().nullable(), model: z.string().nullable(), provider: z.string(), error: z.string().optional(), status: z.string().optional() }),
  gpu: z.object({ available: z.boolean(), cuda_available: z.boolean().optional(), gpus: z.array(z.object({ name: z.string(), memory_total_mb: z.number(), memory_used_mb: z.number(), utilization_percent: z.number(), driver_version: z.string() })), error: z.string().optional() }),
  database: z.object({ healthy: z.boolean(), latency_ms: z.number(), dialect: z.string() }),
  redis: z.object({ enabled: z.boolean(), healthy: z.boolean().nullable() }),
  disk: z.object({ free_gb: z.number(), total_gb: z.number() }),
});

export type SystemStatus = z.infer<typeof systemSchema>;

function csrfToken():string|undefined { const item=document.cookie.split("; ").find(value=>value.startsWith("mc_csrf="));return item?decodeURIComponent(item.split("=").slice(1).join("=")):undefined; }

export function csrfHeaders():Record<string,string> { const token=csrfToken();return token?{"X-CSRF-Token":token}:{}; }

export async function api<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const method=(init?.method??"GET").toUpperCase();const csrf=!["GET","HEAD","OPTIONS"].includes(method)?csrfToken():undefined;
  const response = await fetch(`/api${path}`, { ...init, credentials:"same-origin", headers: { "Content-Type": "application/json", ...(csrf?{"X-CSRF-Token":csrf}:{}), ...init?.headers } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? `HTTP ${response.status}`);
  if (response.status === 204) return undefined as T;
  return schema.parse(await response.json());
}

export const getHealth = (): Promise<z.infer<typeof healthSchema>> => api("/health", healthSchema);
export const getSystem = (): Promise<SystemStatus> => api("/system/status", systemSchema);

export interface Provider { id:string; name:string; role:string; provider_type:string; base_url:string|null; secret_ref:string|null; model:string|null; enabled:boolean; is_default:boolean; timeout_seconds:number; max_retries:number; extra:Record<string,unknown>; health_status:string; last_latency_ms:number|null; }
export interface Meeting { id:string; project_id:string|null; title:string; goal:string; language:string; status:string; started_at:string|null; ended_at:string|null; configuration_json:Record<string,unknown>; audio_saved:boolean; repository_context_enabled:boolean; repository_path:string|null; created_at:string; updated_at:string; }
export interface Transcript { id:string; meeting_id:string; sequence:number; speaker_id:string|null; language:string; translated_language:string|null; start_ms:number; end_ms:number; text:string; translated_text:string|null; confidence:number|null; is_final:boolean; is_edited:boolean; is_pinned:boolean; created_at:string; }
export interface Suggestion { id:string; meeting_id:string; category:string; content:string; reason:string; follow_up_question:string|null; confidence:number; trigger:string; status:string; evidence_segment_ids_json:string[]; created_at:string; updated_at:string; }
export interface MeetingDetail { meeting:Meeting; transcripts:Transcript[]; suggestions:Suggestion[]; decisions:Array<Record<string,unknown>>; open_questions:Array<Record<string,unknown>>; risks:Array<Record<string,unknown>>; action_items:Array<Record<string,unknown>>; codex_runs:Array<Record<string,unknown>>; }

export type LanguageCode = "zh-TW" | "zh-CN" | "en" | "ja" | "ko";
export interface SettingsData {
  setup_completed:boolean;
  ui_language:LanguageCode;
  meeting_input_language:"auto"|LanguageCode;
  secondary_meeting_language:"none"|LanguageCode;
  transcript_display_language:"original"|LanguageCode;
  translation_language:"none"|LanguageCode;
  suggestion_output_language:LanguageCode;
  summary_output_language:LanguageCode;
  export_language:"original"|LanguageCode;
  tts_language:LanguageCode;
  periodic_analysis_seconds:number;
  minimum_new_characters:number;
  codex_cooldown_seconds:number;
  suggestion_cooldown_seconds:number;
  maximum_recent_transcript_minutes:number;
  maximum_recent_transcript_characters:number;
  automatic_analysis_enabled:boolean;
  tts_voice:string;
  tts_rate:number;
  tts_volume:number;
}
export interface CodexStatus {
  installed:boolean; authenticated:boolean; version:string|null; provider:string;
  profile:string|null; model:string|null; error?:string; status?:string;
  last_test?:{healthy?:boolean;error?:string;output?:string}|null;
}
export interface CodexLoginStatus { started:boolean; running:boolean; completed:boolean; message:string; }
export interface Project { id:string; name:string; description:string; goals:string; non_goals:string; default_language:LanguageCode; created_at:string; updated_at:string; }
export interface ProjectDetail extends Project { meeting_count:number; memory_count:number; glossary_count:number; }
export interface GlossaryEntry { id:string; project_id:string; term:string; language:LanguageCode; preferred_spelling:string; translation:string; description:string; aliases:string[]; do_not_translate:boolean; created_at:string; updated_at:string; }
export interface ProjectMemory { id:string; project_id:string; category:string; title:string; content:string; source_meeting_id:string|null; source_decision_id:string|null; confidence:number; status:"active"|"archived"|"superseded"; version:number; created_at:string; updated_at:string; }
export interface Decision { id:string; project_id:string|null; meeting_id:string; title:string; description:string; owner:string|null; status:"draft"|"proposed"|"confirmed"|"rejected"|"superseded"|"archived"; confidence:number; version:number; supersedes_id:string|null; superseded_by_id:string|null; evidence_segment_ids_json:string[]; created_by:string; updated_by:string; created_at:string; updated_at:string; }
export interface ActionItem { id:string; project_id:string|null; meeting_id:string; title:string; description:string; owner:string|null; due_at:string|null; priority:"low"|"normal"|"high"|"urgent"; status:"open"|"in_progress"|"blocked"|"completed"|"archived"; linked_decision_id:string|null; source_suggestion_id:string|null; evidence_segment_ids_json:string[]; created_at:string; updated_at:string; }
export interface KnowledgeDocument { id:string; project_id:string|null; source_type:string; title:string; content:string; language:string; metadata_json:Record<string,unknown>; created_at:string; updated_at:string; }
export interface KnowledgeSearchResult { id:string; source_type:string; project_id:string|null; meeting_id:string|null; title:string; excerpt:string; language:string; status:string|null; created_at:string; }
export interface AuthStatus { configured:boolean; authentication_required:boolean; authenticated:boolean; username:string|null; role:string|null; }

const loose = z.any();
export const request = <T>(path:string, init?:RequestInit):Promise<T> => api(path, loose, init) as Promise<T>;
export const getProviders = ():Promise<Provider[]> => request("/providers");
export const getMeetings = ():Promise<Meeting[]> => request("/meetings");
export const getMeeting = (id:string):Promise<MeetingDetail> => request(`/meetings/${id}`);
export const getSettings = ():Promise<SettingsData> => request("/settings");
export const getCodexStatus = ():Promise<CodexStatus> => request("/codex/status");
export const getCodexLoginStatus = ():Promise<CodexLoginStatus> => request("/codex/login/status");
export const getClaudeStatus = ():Promise<CodexStatus> => request("/claude/status");
export const getClaudeLoginStatus = ():Promise<CodexLoginStatus> => request("/claude/login/status");
export const getProjects = ():Promise<Project[]> => request("/projects");
export const getProject = (id:string):Promise<ProjectDetail> => request(`/projects/${id}`);
export const getProjectGlossary = (id:string):Promise<GlossaryEntry[]> => request(`/projects/${id}/glossary`);
export const getProjectMemory = (id:string):Promise<ProjectMemory[]> => request(`/projects/${id}/memory`);
export const getAuthStatus = ():Promise<AuthStatus> => request("/auth/status");
export const getDecisions = (query=""):Promise<Decision[]> => request(`/decisions${query}`);
export const getActions = (query=""):Promise<ActionItem[]> => request(`/actions${query}`);
export const searchKnowledge = (query=""):Promise<KnowledgeSearchResult[]> => request(`/knowledge/search${query}`);
export const post = <T>(path:string, body?:unknown):Promise<T> => request(path,{method:"POST",body:body === undefined ? undefined : JSON.stringify(body)});
export const put = <T>(path:string, body:unknown):Promise<T> => request(path,{method:"PUT",body:JSON.stringify(body)});
export const patch = <T>(path:string, body:unknown):Promise<T> => request(path,{method:"PATCH",body:JSON.stringify(body)});
export const remove = (path:string):Promise<void> => request(path,{method:"DELETE"});

export async function downloadExport(meetingId:string, format:"markdown"|"json"|"pdf"|"vtt"|"srt"):Promise<void>{
  const response=await fetch(`/api/meetings/${meetingId}/export/${format}`,{method:"POST",credentials:"same-origin",headers:csrfHeaders()});
  if(!response.ok) throw new Error(`Export failed: ${response.status}`);
  const blob=await response.blob(); const url=URL.createObjectURL(blob); const anchor=document.createElement("a");
  anchor.href=url; anchor.download=`${meetingId}.${format === "markdown" ? "md" : format}`; anchor.click(); URL.revokeObjectURL(url);
}
