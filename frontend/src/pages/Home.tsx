import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Health, type Source, type SourceStatus } from '../api'
import Header from '../components/Header'
import { useJob } from '../hooks/useJob'
import { useLang } from '../hooks/useLang'
import { mmss } from '../lib/time'

const ORDER: SourceStatus[] = ['queued', 'downloading', 'transcribing', 'finding_moments', 'ready']

export default function Home() {
  const { t } = useLang()
  const nav = useNavigate()
  const [url, setUrl] = useState('')
  const [health, setHealth] = useState<Health | null>(null)
  const [recent, setRecent] = useState<Source[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    api.listSources().then(setRecent).catch(() => {})
  }, [])

  const fetcher = useCallback(() => api.source(jobId!), [jobId])
  const { value: job } = useJob<Source>(jobId ? fetcher : null, (s) => s.status === 'ready' || s.status === 'error')

  useEffect(() => {
    if (job?.status === 'ready') nav(`/s/${job.id}`)
  }, [job, nav])

  async function start(body: { url?: string; demo?: boolean }) {
    setErr(null)
    try { const r = await api.createSource(body); setJobId(r.id) } catch (e) { setErr(e instanceof Error ? e.message : String(e)) }
  }
  async function upload(f: File) {
    setErr(null)
    try { const r = await api.uploadSource(f); setJobId(r.id) } catch (e) { setErr(e instanceof Error ? e.message : String(e)) }
  }

  const stepIdx = job ? ORDER.indexOf(job.status) : -1
  const steps = [
    { k: 'stepIngest', done: stepIdx >= 2, active: stepIdx === 1 },
    { k: 'stepTranscribe', done: stepIdx >= 3, active: stepIdx === 2 },
    { k: 'stepMoments', done: stepIdx >= 4, active: stepIdx === 3 },
  ] as const

  return (
    <div className="min-h-full flex flex-col">
      <Header />
      <main className="flex-1 max-w-3xl w-full mx-auto px-6 py-16">
        <h1 className="font-serif text-5xl leading-[1.05] tracking-tight">{t('tagline')}</h1>
        <p className="mt-4 text-ink2 max-w-xl">
          Video largo → momentos candidatos con puntaje de integridad → aprobación editorial → clip 9:16 con manifiesto de procedencia.
        </p>

        <form className="mt-10 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (url.trim()) void start({ url: url.trim() }) }}>
          <input className="flex-1 !py-3 text-base" placeholder={t('pasteUrl')} value={url} onChange={(e) => setUrl(e.target.value)} disabled={!!jobId} />
          <button className="btn-primary !px-5" disabled={!!jobId || !url.trim()}>{t('start')} →</button>
        </form>
        <div className="mt-3 flex items-center gap-4 text-sm text-ink2">
          <label className="cursor-pointer underline">
            {t('orUpload')}
            <input type="file" accept="video/*,audio/*" className="hidden" disabled={!!jobId} onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f) }} />
          </label>
          {(health?.fixtures || health?.demo_mode) && (
            <button className="btn-ghost" disabled={!!jobId} onClick={() => start({ demo: true })} title={t('demoHint')}>
              ▶ {t('demoSource')}
            </button>
          )}
        </div>
        {err && <p className="mt-3 text-sm text-red">{err}</p>}

        {job && (
          <div className="card mt-8 p-5">
            <div className="flex items-center justify-between">
              <div className="font-medium">{job.title || job.url || job.id}</div>
              <span className={`pill ${job.status === 'error' ? 'bg-redsoft text-red border-red/30' : 'bg-paper2 border-line text-ink2'}`}>
                {job.status === 'queued' ? t('statusQueued') : job.status === 'downloading' ? t('statusDownloading') : job.status === 'transcribing' ? t('statusTranscribing') : job.status === 'finding_moments' ? t('statusFinding') : job.status === 'ready' ? t('statusReady') : t('statusError')}
              </span>
            </div>
            <ol className="mt-4 flex gap-6">
              {steps.map((s) => (
                <li key={s.k} className={`flex items-center gap-2 text-sm ${s.done ? 'text-teal' : s.active ? 'text-ink' : 'text-ink2/60'}`}>
                  <span className={`w-5 h-5 rounded-full grid place-items-center text-[11px] border ${s.done ? 'bg-teal border-teal text-white' : s.active ? 'border-ink animate-pulse' : 'border-line'}`}>{s.done ? '✓' : ''}</span>
                  {t(s.k)}
                </li>
              ))}
            </ol>
            {job.error && <p className="mt-3 text-sm text-red">{job.error}</p>}
          </div>
        )}

        {recent.length > 0 && !job && (
          <section className="mt-12">
            <div className="text-[11px] uppercase tracking-wider text-ink2 mb-2">{t('recent')}</div>
            <ul className="divide-y divide-line card">
              {recent.slice(0, 6).map((s) => (
                <li key={s.id}>
                  <button className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-paper2 disabled:opacity-50" disabled={s.status !== 'ready'} onClick={() => nav(`/s/${s.id}`)}>
                    <span className="truncate">{s.title || s.url || s.id}</span>
                    <span className="text-xs text-ink2 tabular-nums shrink-0 ml-3">{mmss(s.duration)} · {s.moment_count} {t('moments').toLowerCase()} · {s.status}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {health && (
          <p className="mt-10 text-[11px] text-ink2">
            LLM {health.llm ? '●' : '○'} · ASR {health.asr ? '●' : '○'} · captions {health.captions ? '●' : '○'} · fixtures {health.fixtures ? '●' : '○'}{health.demo_mode ? ' · DEMO_MODE' : ''}
          </p>
        )}
      </main>
    </div>
  )
}
