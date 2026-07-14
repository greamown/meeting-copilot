import { z } from "zod";

const healthSchema = z.object({ status: z.literal("ok"), service: z.string(), version: z.string() });

export const systemSchema = z.object({
  os: z.string(),
  python_version: z.string(),
  docker_available: z.boolean(),
  ffmpeg_available: z.boolean(),
  codex: z.object({ installed: z.boolean(), authenticated: z.boolean(), version: z.string().nullable(), profile: z.string().nullable(), model: z.string().nullable(), provider: z.string(), error: z.string().optional(), status: z.string().optional() }),
  gpu: z.object({ available: z.boolean(), cuda_available: z.boolean().optional(), gpus: z.array(z.object({ name: z.string(), memory_total_mb: z.number(), memory_used_mb: z.number(), utilization_percent: z.number(), driver_version: z.string() })), error: z.string().optional() }),
  database: z.object({ healthy: z.boolean(), latency_ms: z.number(), dialect: z.string() }),
  redis: z.object({ enabled: z.boolean(), healthy: z.boolean().nullable() }),
  disk: z.object({ free_gb: z.number(), total_gb: z.number() }),
});

export type SystemStatus = z.infer<typeof systemSchema>;

export async function api<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? `HTTP ${response.status}`);
  return schema.parse(await response.json());
}

export const getHealth = (): Promise<z.infer<typeof healthSchema>> => api("/health", healthSchema);
export const getSystem = (): Promise<SystemStatus> => api("/system/status", systemSchema);

export interface Provider { id:string; name:string; role:string; provider_type:string; base_url:string|null; secret_ref:string|null; model:string|null; enabled:boolean; is_default:boolean; timeout_seconds:number; max_retries:number; extra:Record<string,unknown>; health_status:string; last_latency_ms:number|null; }
export interface Meeting { id:string; title:string; goal:string; language:string; status:string; started_at:string|null; ended_at:string|null; configuration_json:Record<string,unknown>; audio_saved:boolean; repository_context_enabled:boolean; repository_path:string|null; created_at:string; updated_at:string; }
export interface Transcript { id:string; meeting_id:string; sequence:number; speaker_id:string|null; start_ms:number; end_ms:number; text:string; confidence:number|null; is_final:boolean; is_edited:boolean; is_pinned:boolean; created_at:string; }
export interface Suggestion { id:string; meeting_id:string; category:string; content:string; reason:string; follow_up_question:string|null; confidence:number; trigger:string; status:string; evidence_segment_ids_json:string[]; created_at:string; updated_at:string; }
export interface MeetingDetail { meeting:Meeting; transcripts:Transcript[]; suggestions:Suggestion[]; decisions:Array<Record<string,unknown>>; open_questions:Array<Record<string,unknown>>; risks:Array<Record<string,unknown>>; action_items:Array<Record<string,unknown>>; codex_runs:Array<Record<string,unknown>>; }

const loose = z.any();
export const request = <T>(path:string, init?:RequestInit):Promise<T> => api(path, loose, init) as Promise<T>;
export const getProviders = ():Promise<Provider[]> => request("/providers");
export const getMeetings = ():Promise<Meeting[]> => request("/meetings");
export const getMeeting = (id:string):Promise<MeetingDetail> => request(`/meetings/${id}`);
export const post = <T>(path:string, body?:unknown):Promise<T> => request(path,{method:"POST",body:body === undefined ? undefined : JSON.stringify(body)});
export const put = <T>(path:string, body:unknown):Promise<T> => request(path,{method:"PUT",body:JSON.stringify(body)});
export const patch = <T>(path:string, body:unknown):Promise<T> => request(path,{method:"PATCH",body:JSON.stringify(body)});
export const remove = (path:string):Promise<void> => request(path,{method:"DELETE"});

export async function downloadExport(meetingId:string, format:"markdown"|"json"|"vtt"):Promise<void>{
  const response=await fetch(`/api/meetings/${meetingId}/export/${format}`,{method:"POST"});
  if(!response.ok) throw new Error(`Export failed: ${response.status}`);
  const blob=await response.blob(); const url=URL.createObjectURL(blob); const anchor=document.createElement("a");
  anchor.href=url; anchor.download=`${meetingId}.${format === "markdown" ? "md" : format}`; anchor.click(); URL.revokeObjectURL(url);
}
