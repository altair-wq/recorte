export type SourceStatus = 'queued' | 'downloading' | 'transcribing' | 'finding_moments' | 'ready' | 'error'
export type MomentStatus = 'candidate' | 'approved' | 'rejected'
export type ClipStatus = 'rendering' | 'ready' | 'error'
export type FlagType =
  | 'mid_sentence_cut' | 'missing_qualifier' | 'missing_attribution' | 'question_without_answer'
  | 'hypothetical_or_sarcasm' | 'needs_prior_context' | 'speaker_change_at_edge'

export interface Word { w: string; start: number; end: number }
export interface Utterance { id: number; start: number; end: number; speaker: string | null; text: string; words: Word[] }
export interface Transcript { source_id: string; language: string; asr_model: string; utterances: Utterance[] }

export interface Source {
  id: string; url: string | null; title: string; channel: string | null; duration: number
  status: SourceStatus; error: string | null; created_at: string
  moment_count: number; approved_count: number; sha256: string
  file_url: string | null; poster_url: string | null
}

export interface Flag { type: FlagType; evidence: string; at: number; suggestion: string | null }
export interface Integrity {
  score: number; flags: Flag[]; suggested_start: number | null; suggested_end: number | null
  checked_with: string; rationale: string | null
}
export interface Adjustment { field: string; from: number; to: number; at: string; by?: string }
export interface Review { decision: 'approved' | 'rejected'; by: string; at: string; reason: string | null; adjustments: Adjustment[] }
export interface Moment {
  id: string; source_id: string; start: number; end: number; orig_start: number; orig_end: number
  start_utt: number; end_utt: number; headline: string; summary: string; why: string; quote: string
  speaker: string | null; newsworthiness: number; integrity: Integrity; status: MomentStatus
  review: Review | null; origin: 'agent' | 'chat' | 'manual'; adjustments: Adjustment[]; clip_id: string | null
}
export interface Clip {
  id: string; moment_id: string; source_id: string; status: ClipStatus; error: string | null; sha256: string
  created_at: string; file_url: string | null; thumb_url: string | null; manifest_url: string | null; verify_url: string
  moment: Moment | null; source: { id: string; title: string; channel: string | null; url: string | null; duration: number } | null
}
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
export interface ChatReply { reply: string; created_moment_ids: string[] }
export interface Health { ok: boolean; demo_mode: boolean; fixtures: boolean; llm: boolean; asr: boolean; captions: boolean; hosted?: boolean }

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) {
    let msg = `${r.status}`
    try { msg = (await r.json()).detail ?? msg } catch { /* ignore */ }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}

export const api = {
  health: () => req<Health>('/api/health'),
  createSource: (body: { url?: string; demo?: boolean }) => req<{ id: string }>('/api/sources', { method: 'POST', body: JSON.stringify(body) }),
  uploadSource: async (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch('/api/sources/upload', { method: 'POST', body: fd })
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json() as Promise<{ id: string }>
  },
  listSources: () => req<Source[]>('/api/sources'),
  source: (id: string) => req<Source>(`/api/sources/${id}`),
  transcript: (id: string) => req<Transcript>(`/api/sources/${id}/transcript`),
  moments: (id: string) => req<Moment[]>(`/api/sources/${id}/moments`),
  moment: (id: string) => req<Moment>(`/api/moments/${id}`),
  patchMoment: (id: string, body: { start?: number; end?: number; start_utt?: number; end_utt?: number; by?: string }) =>
    req<Moment>(`/api/moments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  approve: (id: string, by: string, reason?: string) =>
    req<{ clip_id: string; moment: Moment }>(`/api/moments/${id}/approve`, { method: 'POST', body: JSON.stringify({ by, reason }) }),
  reject: (id: string, by: string, reason: string) =>
    req<Moment>(`/api/moments/${id}/reject`, { method: 'POST', body: JSON.stringify({ by, reason }) }),
  clip: (id: string) => req<Clip>(`/api/clips/${id}`),
  manifest: (id: string) => req<Record<string, unknown>>(`/api/clips/${id}/manifest`),
  chat: (sourceId: string, messages: ChatMessage[], lang: string) =>
    req<ChatReply>(`/api/sources/${sourceId}/chat`, { method: 'POST', body: JSON.stringify({ messages, lang }) }),
}
