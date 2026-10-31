import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Clip, type Health } from '../api'
import Header from '../components/Header'
import IntegrityBadge from '../components/IntegrityBadge'
import ProvenanceCard from '../components/ProvenanceCard'
import { useJob } from '../hooks/useJob'
import { useLang } from '../hooks/useLang'
import { mmss } from '../lib/time'

export default function Export() {
  const { clipId = '' } = useParams()
  const { t } = useLang()
  const fetcher = useCallback(() => api.clip(clipId), [clipId])
  const { value: clip } = useJob<Clip>(fetcher, (c) => c.status !== 'rendering')
  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null)
  const [copied, setCopied] = useState(false)
  const [health, setHealth] = useState<Health | null>(null)
  useEffect(() => { api.health().then(setHealth).catch(() => {}) }, [])

  useEffect(() => {
    if (clip?.status === 'ready') api.manifest(clip.id).then(setManifest).catch(() => {})
  }, [clip?.status, clip?.id])

  const m = clip?.moment ?? null
  const copy = async () => { try { await navigator.clipboard.writeText(clip!.verify_url); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { /* ignore */ } }

  const audit: { at: string; what: string }[] = []
  if (m) {
    audit.push({ at: '', what: `Momento ${m.id} propuesto por ${m.origin === 'chat' ? 'el asistente' : 'el agente'} · ${mmss(m.orig_start)}–${mmss(m.orig_end)}` })
    audit.push({ at: '', what: `Integridad ${m.integrity.score}/100 (${m.integrity.checked_with}) · ${m.integrity.flags.length} ${t('flags').toLowerCase()}` })
    for (const a of m.adjustments) audit.push({ at: a.at, what: `${a.by ?? ''} ajustó ${a.field}: ${mmss(a.from)} → ${mmss(a.to)}` })
    if (m.review) audit.push({ at: m.review.at, what: `${m.review.by} ${m.review.decision === 'approved' ? 'aprobó' : 'rechazó'}${m.review.reason ? ` · ${m.review.reason}` : ''}` })
    if (clip) audit.push({ at: clip.created_at, what: `Render ${clip.status} · ${clip.id}` })
  }

  return (
    <div className="min-h-full flex flex-col">
      <Header right={m && <Link to={`/s/${m.source_id}`} className="btn-ghost">← {t('backToWorkspace')}</Link>} />
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 grid grid-cols-[360px_1fr] gap-8">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-ink2 mb-2">{t('phonePreview')}</div>
          <div className="mx-auto w-[300px] rounded-[36px] border-[10px] border-ink bg-black shadow-xl overflow-hidden" style={{ aspectRatio: '9/16' }}>
            {clip?.status === 'ready' && clip.file_url ? (
              <video src={clip.file_url} poster={clip.thumb_url ?? undefined} controls autoPlay muted className="w-full h-full object-contain bg-black" />
            ) : (
              <div className="w-full h-full grid place-items-center text-paper text-sm">
                {clip?.status === 'error' ? <span className="text-red p-4 text-center">{clip.error}</span> : (
                  <span className="text-center px-4"><span className="animate-pulse">{t('rendering')}</span>{health?.hosted && <><br /><span className="text-xs text-paper2/70">{t('hostedRenderHint')}</span></>}</span>
                )}
              </div>
            )}
          </div>
          {clip?.status === 'ready' && (
            <div className="flex flex-wrap gap-2 mt-4 justify-center">
              <a className="btn-primary" href={clip.file_url ?? '#'} download={`recorte-${clip.id}.mp4`}>↓ {t('downloadClip')}</a>
              <a className="btn-ghost" href={clip.verify_url} target="_blank" rel="noreferrer">{t('viewVerification')} ↗</a>
              <button className="btn-ghost" onClick={copy}>{copied ? t('copied') : t('copyLink')}</button>
            </div>
          )}
        </div>

        <div className="space-y-5 min-w-0">
          {clip && m && (
            <>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-wider text-teal">{t('verifiableClip')}</div>
                  <h1 className="font-serif text-3xl leading-tight mt-1">{m.headline}</h1>
                  <p className="text-ink2 mt-1 text-sm">{m.speaker} · {mmss(m.start)}–{mmss(m.end)} · {clip.source?.title}</p>
                </div>
                <IntegrityBadge score={m.integrity.score} size="lg" />
              </div>
              <ProvenanceCard clip={clip} />
              <section className="card p-5">
                <div className="text-[11px] uppercase tracking-wider text-ink2 mb-2">{t('auditLog')}</div>
                <ol className="text-sm space-y-1.5">
                  {audit.map((a, i) => (
                    <li key={i} className="flex gap-3">
                      <span className="text-xs text-ink2 tabular-nums w-[150px] shrink-0">{a.at ? new Date(a.at).toLocaleString() : ''}</span>
                      <span>{a.what}</span>
                    </li>
                  ))}
                </ol>
              </section>
              <section className="card p-5">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[11px] uppercase tracking-wider text-ink2">{t('manifest')}</div>
                  {clip.manifest_url && <a className="text-xs text-teal underline" href={clip.manifest_url} target="_blank" rel="noreferrer">manifest.json ↗</a>}
                </div>
                <dl className="grid grid-cols-[130px_1fr] gap-x-4 gap-y-1 text-xs mb-3">
                  <dt className="text-ink2">{t('hashSource')}</dt><dd className="font-mono break-all">{(manifest as { source?: { sha256?: string } } | null)?.source?.sha256 ?? '…'}</dd>
                  <dt className="text-ink2">{t('hashClip')}</dt><dd className="font-mono break-all">{clip.sha256 || '…'}</dd>
                  <dt className="text-ink2">{t('models')}</dt><dd className="font-mono">{(manifest as { pipeline?: { asr?: string; llm?: string } } | null)?.pipeline?.asr} · {(manifest as { pipeline?: { llm?: string } } | null)?.pipeline?.llm}</dd>
                </dl>
                <pre className="text-[11px] leading-relaxed bg-paper2 rounded-md p-3 overflow-auto max-h-[360px]">{manifest ? JSON.stringify(manifest, null, 2) : '…'}</pre>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
