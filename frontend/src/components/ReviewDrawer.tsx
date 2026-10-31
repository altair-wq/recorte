import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Moment, type Transcript, type Utterance } from '../api'
import { useLang } from '../hooks/useLang'
import { mmss, span, dur } from '../lib/time'
import IntegrityBadge from './IntegrityBadge'

type Props = {
  moment: Moment; transcript: Transcript | null; editor: string; onEditor: (s: string) => void
  onUpdated: (m: Moment) => void; onApproved: (m: Moment, clipId: string) => void; onSeek: (t: number) => void; onClose: () => void
}

const CONTEXT_S = 20

export default function ReviewDrawer({ moment: m, transcript, editor, onEditor, onUpdated, onApproved, onSeek, onClose }: Props) {
  const { t } = useLang()
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState('')

  useEffect(() => { setRejecting(false); setReason(''); setErr(null) }, [m.id])

  const utts = useMemo(() => {
    if (!transcript) return [] as Utterance[]
    return transcript.utterances.filter((u) => u.end >= m.start - CONTEXT_S && u.start <= m.end + CONTEXT_S)
  }, [transcript, m.start, m.end])

  const evidenceAt = new Set(m.integrity.flags.map((f) => Math.round(f.at * 10)))
  const hasSuggestion = m.integrity.suggested_start !== null || m.integrity.suggested_end !== null
  const canEdit = m.status === 'candidate'

  async function run<T>(key: string, fn: () => Promise<T>, after: (v: T) => void) {
    setBusy(key); setErr(null)
    try { after(await fn()) } catch (e) { setErr(e instanceof Error ? e.message : String(e)) } finally { setBusy(null) }
  }
  const patch = (body: Parameters<typeof api.patchMoment>[1]) => run('patch', () => api.patchMoment(m.id, { ...body, by: editor }), onUpdated)
  const extend = () => patch({
    start: m.integrity.suggested_start ?? undefined,
    end: m.integrity.suggested_end ?? undefined,
  })
  const approve = () => run('approve', () => api.approve(m.id, editor), (r) => onApproved(r.moment, r.clip_id))
  const reject = () => {
    if (!reason.trim()) { setErr(t('reasonRequired')); return }
    void run('reject', () => api.reject(m.id, editor, reason.trim()), onUpdated)
  }

  // keyboard: E extend, A approve
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'TEXTAREA') return
      if (!canEdit) return
      if (e.key === 'e' && hasSuggestion) { e.preventDefault(); void extend() }
      if (e.key === 'a') { e.preventDefault(); void approve() }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [m.id, m.start, m.end, hasSuggestion, canEdit, editor])

  return (
    <aside className="card flex flex-col h-full overflow-hidden">
      <div className="flex items-start justify-between gap-3 p-4 border-b border-line">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-ink2">{t('reviewTitle')}</div>
          <h2 className="font-serif text-xl leading-tight mt-1">{m.headline}</h2>
          <div className="text-xs text-ink2 mt-1 tabular-nums">{m.speaker ?? '—'} · {span(m.start, m.end)} · {dur(m.start, m.end)}</div>
        </div>
        <button className="btn-ghost shrink-0" onClick={onClose}>← {t('moments')} <span className="kbd">Esc</span></button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <IntegrityBadge score={m.integrity.score} size="lg" />

        <section>
          <div className="text-[11px] uppercase tracking-wider text-ink2 mb-1">{t('quote')}</div>
          <blockquote className="font-serif text-lg leading-snug border-l-2 border-teal pl-3">«{m.quote}»</blockquote>
          {m.why && <p className="text-sm text-ink2 mt-2"><span className="font-medium text-ink">{t('why')}:</span> {m.why}</p>}
        </section>

        <section>
          <div className="text-[11px] uppercase tracking-wider text-ink2 mb-1">{t('flags')}</div>
          {m.integrity.flags.length === 0 ? (
            <p className="text-sm text-teal">✓ {t('noFlags')}</p>
          ) : (
            <ul className="space-y-2">
              {m.integrity.flags.map((f, i) => (
                <li key={i} className="border-l-2 border-amber bg-ambersoft/40 rounded-r-md px-3 py-2 text-sm">
                  <div className="font-medium text-amber">⚑ {t(`flag_${f.type}`)}
                    <button className="ml-2 text-xs underline tabular-nums" onClick={() => onSeek(f.at)}>[{mmss(f.at)}]</button>
                  </div>
                  <div className="mt-0.5">«{f.evidence}»</div>
                  {f.suggestion && <div className="text-xs text-ink2 mt-0.5">{t('suggestion')}: {f.suggestion}</div>}
                </li>
              ))}
            </ul>
          )}
          {m.integrity.rationale && <p className="text-xs text-ink2 mt-2 italic">{m.integrity.rationale}</p>}
          <p className="text-[11px] text-ink2 mt-1">{t('integrity')}: {m.integrity.checked_with}</p>
        </section>

        <section>
          <div className="text-[11px] uppercase tracking-wider text-ink2 mb-1">{t('context')}</div>
          <div className="text-sm leading-relaxed space-y-1">
            {utts.map((u) => {
              const inside = u.id >= m.start_utt && u.id <= m.end_utt
              const flagged = evidenceAt.has(Math.round(u.start * 10))
              return (
                <p key={u.id} className={`${inside ? 'text-ink' : 'text-ink2/70'} ${flagged ? 'bg-ambersoft rounded px-1 -mx-1' : ''}`}>
                  <button className="text-[11px] tabular-nums text-ink2 mr-1 hover:underline" onClick={() => onSeek(u.start)}>[{mmss(u.start)}]</button>
                  <span className="text-[11px] text-ink2 mr-1">{u.speaker}:</span>
                  <span className={inside ? 'font-medium' : ''}>{u.text}</span>
                </p>
              )
            })}
          </div>
        </section>

        {m.adjustments.length > 0 && (
          <section>
            <div className="text-[11px] uppercase tracking-wider text-ink2 mb-1">{t('adjustments')}</div>
            <ul className="text-xs text-ink2 tabular-nums">
              {m.adjustments.map((a, i) => <li key={i}>{a.field}: {mmss(a.from)} → {mmss(a.to)}</li>)}
            </ul>
          </section>
        )}
      </div>

      <div className="border-t border-line p-4 space-y-3">
        {canEdit && (
          <>
            <div className="flex flex-wrap gap-2">
              <button className="btn-ghost" disabled={!!busy} onClick={() => patch({ start_utt: m.start_utt - 1 })}>{t('startsAt')} {t('minusUtt')}</button>
              <button className="btn-ghost" disabled={!!busy} onClick={() => patch({ start_utt: m.start_utt + 1 })}>{t('startsAt')} {t('plusUtt')}</button>
              <button className="btn-ghost" disabled={!!busy} onClick={() => patch({ end_utt: m.end_utt - 1 })}>{t('endsAt')} {t('minusUtt')}</button>
              <button className="btn-ghost" disabled={!!busy} onClick={() => patch({ end_utt: m.end_utt + 1 })}>{t('endsAt')} {t('plusUtt')}</button>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-ink2">{t('editor')}</label>
              <input value={editor} onChange={(e) => onEditor(e.target.value)} className="flex-1 !py-1" />
            </div>
            {rejecting ? (
              <div className="space-y-2">
                <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t('reason')} className="w-full" />
                <div className="flex gap-2">
                  <button className="btn-danger" disabled={!!busy} onClick={reject}>{t('reject')}</button>
                  <button className="btn-ghost" onClick={() => setRejecting(false)}>✕</button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {hasSuggestion && (
                  <button className="btn-ghost border-amber text-amber" disabled={!!busy} onClick={extend}>
                    ↔ {t('extendToInclude')} <span className="kbd">E</span>
                  </button>
                )}
                <button className="btn-primary" disabled={!!busy} onClick={approve}>✓ {t('approve')} <span className="kbd !bg-white/20 !text-white !border-white/30">A</span></button>
                <button className="btn-danger" disabled={!!busy} onClick={() => setRejecting(true)}>{t('reject')}</button>
              </div>
            )}
            <p className="text-[11px] text-ink2">{t('renderGate')}</p>
          </>
        )}
        {m.status === 'approved' && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm text-teal">✓ {t('statusApproved')} · {m.review?.by}</span>
            {m.clip_id && <Link to={`/c/${m.clip_id}`} className="btn-primary">{t('openExport')} →</Link>}
          </div>
        )}
        {m.status === 'rejected' && <p className="text-sm text-ink2">{t('statusRejected')} · {m.review?.reason}</p>}
        {err && <p className="text-xs text-red">{err}</p>}
      </div>
    </aside>
  )
}
