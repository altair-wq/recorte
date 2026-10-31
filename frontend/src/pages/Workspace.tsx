import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Moment, type Source, type Transcript } from '../api'
import AgentChat from '../components/AgentChat'
import Header from '../components/Header'
import MomentCard from '../components/MomentCard'
import ReviewDrawer from '../components/ReviewDrawer'
import Timeline from '../components/Timeline'
import VideoPlayer from '../components/VideoPlayer'
import { useLang } from '../hooks/useLang'

type Filter = 'all' | 'candidate' | 'approved'

export default function Workspace() {
  const { sourceId = '' } = useParams()
  const { t } = useLang()
  const [source, setSource] = useState<Source | null>(null)
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [moments, setMoments] = useState<Moment[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [current, setCurrent] = useState(0)
  const [highlight, setHighlight] = useState<Set<string>>(new Set())
  const [editor, setEditorState] = useState(() => { try { return localStorage.getItem('recorte.editor') || 'editor@demo' } catch { return 'editor@demo' } })
  const [renderingClip, setRenderingClip] = useState<string | null>(null)
  const [readyClip, setReadyClip] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)

  const setEditor = (s: string) => { setEditorState(s); try { localStorage.setItem('recorte.editor', s) } catch { /* ignore */ } }

  useEffect(() => {
    api.source(sourceId).then(setSource).catch(() => {})
    api.transcript(sourceId).then(setTranscript).catch(() => {})
    api.moments(sourceId).then(setMoments).catch(() => {})
  }, [sourceId])

  // poll the clip while rendering so the UI can announce "ready"
  useEffect(() => {
    if (!renderingClip) return
    const id = window.setInterval(async () => {
      try {
        const c = await api.clip(renderingClip)
        if (c.status !== 'rendering') { setRenderingClip(null); if (c.status === 'ready') setReadyClip(c.id) }
      } catch { /* ignore */ }
    }, 1500)
    return () => window.clearInterval(id)
  }, [renderingClip])

  const seek = useCallback((time: number) => {
    const v = videoRef.current
    if (v) { v.currentTime = time; void v.play().catch(() => {}) }
    setCurrent(time)
  }, [])

  const visible = useMemo(() => moments.filter((m) => filter === 'all' ? true : m.status === filter), [moments, filter])
  const selected = moments.find((m) => m.id === selectedId) ?? null

  const upsert = (m: Moment) => setMoments((ms) => ms.some((x) => x.id === m.id) ? ms.map((x) => (x.id === m.id ? m : x)) : [...ms, m].sort((a, b) => a.start - b.start))

  const onCreated = async (ids: string[]) => {
    const ms = await api.moments(sourceId)
    setMoments(ms)
    setHighlight(new Set(ids))
    setSelectedId(null)
    const first = ms.find((x) => x.id === ids[0])
    if (first) seek(first.start)
    window.setTimeout(() => setHighlight(new Set()), 8000)
  }

  // keyboard: J/K prev/next, Space play/pause, Esc close
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const idx = visible.findIndex((m) => m.id === selectedId)
      if (e.key === 'j' || e.key === 'k') {
        e.preventDefault()
        const next = visible[Math.min(visible.length - 1, Math.max(0, idx + (e.key === 'j' ? 1 : -1)))]
        if (next) { setSelectedId(next.id); seek(next.start) }
      }
      if (e.key === ' ') {
        e.preventDefault()
        const v = videoRef.current
        if (v) { if (v.paused) void v.play(); else v.pause() }
      }
      if (e.key === 'Escape') setSelectedId(null)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [visible, selectedId, seek])

  const counts = { all: moments.length, candidate: moments.filter((m) => m.status === 'candidate').length, approved: moments.filter((m) => m.status === 'approved').length }

  return (
    <div className="h-full flex flex-col">
      <Header right={<span className="text-xs text-ink2 hidden lg:inline">{t('shortcuts')}</span>} />
      <div className="flex-1 grid grid-cols-[60fr_40fr] gap-4 p-4 min-h-0">
        {/* left: player, timeline, chat */}
        <div className="flex flex-col gap-3 min-h-0">
          <div className="flex items-baseline justify-between gap-3">
            <h1 className="font-serif text-xl leading-tight truncate">{source?.title ?? '…'}</h1>
            <span className="text-xs text-ink2 shrink-0">{source?.channel}</span>
          </div>
          <div className="max-h-[46vh] mx-auto w-full" style={{ aspectRatio: '16/9' }}>
            <VideoPlayer ref={videoRef} src={source?.file_url ?? null} poster={source?.poster_url} onTime={setCurrent} />
          </div>
          <Timeline duration={source?.duration ?? 0} moments={moments} current={current} selectedId={selectedId}
            onSeek={seek} onSelect={(m) => setSelectedId(m.id)} />
          {(renderingClip || readyClip) && (
            <div className="card px-4 py-2 text-sm flex items-center justify-between">
              {renderingClip ? <span className="animate-pulse">{t('rendering')}</span> : <span className="text-teal">✓ {t('clipReady')}</span>}
              <Link to={`/c/${renderingClip ?? readyClip}`} className="btn-primary !py-1">{t('openExport')} →</Link>
            </div>
          )}
          <div className="flex-1 min-h-0 flex flex-col justify-end">
            <AgentChat sourceId={sourceId} onCreated={onCreated} onSeek={seek} />
          </div>
        </div>

        {/* right: moment list or review drawer */}
        <div className="flex flex-col gap-3 min-h-0">
          {selected ? (
            <ReviewDrawer moment={selected} transcript={transcript} editor={editor} onEditor={setEditor}
              onUpdated={upsert}
              onApproved={(m, clipId) => { upsert(m); setReadyClip(null); setRenderingClip(clipId) }}
              onSeek={seek} onClose={() => setSelectedId(null)} />
          ) : (
            <>
              <div className="flex items-center justify-between">
                <h2 className="font-serif text-xl">{t('moments')}</h2>
                <div className="flex gap-1">
                  {(['all', 'candidate', 'approved'] as Filter[]).map((f) => (
                    <button key={f} onClick={() => setFilter(f)}
                      className={`pill ${filter === f ? 'bg-ink text-paper border-ink' : 'bg-white border-line text-ink2 hover:bg-paper2'}`}>
                      {f === 'all' ? t('all') : f === 'candidate' ? t('pending') : t('approved')} · {counts[f]}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-0">
                {visible.map((m) => (
                  <MomentCard key={m.id} m={m} selected={m.id === selectedId} highlight={highlight.has(m.id)}
                    onClick={() => { setSelectedId(m.id); seek(m.start) }} />
                ))}
                {visible.length === 0 && <div className="text-sm text-ink2 p-4">—</div>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
