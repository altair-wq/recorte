import { useState } from 'react'
import { api, type ChatMessage } from '../api'
import { useLang } from '../hooks/useLang'

type Props = { sourceId: string; onCreated: (ids: string[]) => void; onSeek: (t: number) => void }

function renderWithTimestamps(text: string, onSeek: (t: number) => void) {
  const parts = text.split(/(\[\d{1,2}:\d{2}\])/g)
  return parts.map((p, i) => {
    const m = /^\[(\d{1,2}):(\d{2})\]$/.exec(p)
    if (m) {
      const t = Number(m[1]) * 60 + Number(m[2])
      return <button key={i} className="text-teal underline tabular-nums" onClick={() => onSeek(t)}>{p}</button>
    }
    return <span key={i}>{p}</span>
  })
}

export default function AgentChat({ sourceId, onCreated, onSeek }: Props) {
  const { t, lang } = useLang()
  const [open, setOpen] = useState(true)
  const [msgs, setMsgs] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)

  async function send(text: string) {
    const q = text.trim()
    if (!q || busy) return
    const next = [...msgs, { role: 'user' as const, content: q }]
    setMsgs(next); setInput(''); setBusy(true)
    try {
      const r = await api.chat(sourceId, next, lang)
      setMsgs([...next, { role: 'assistant', content: r.reply }])
      if (r.created_moment_ids.length) onCreated(r.created_moment_ids)
    } catch (e) {
      setMsgs([...next, { role: 'assistant', content: `⚠ ${e instanceof Error ? e.message : String(e)}` }])
    } finally { setBusy(false) }
  }

  return (
    <div className="card flex flex-col">
      <button className="flex items-center justify-between px-4 py-2 text-sm font-medium" onClick={() => setOpen(!open)}>
        <span>✦ {t('chatTitle')}</span><span className="text-ink2">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="border-t border-line flex flex-col max-h-[40vh]">
          <div className="flex-1 overflow-y-auto p-3 space-y-2 text-sm">
            {msgs.length === 0 && (
              <div className="flex flex-wrap gap-1.5">
                {(['suggested1', 'suggested2', 'suggested3'] as const).map((k) => (
                  <button key={k} className="pill bg-white border-line hover:bg-paper2" onClick={() => send(t(k))}>{t(k)}</button>
                ))}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`whitespace-pre-wrap leading-relaxed ${m.role === 'user' ? 'text-ink font-medium' : 'text-ink2 pl-3 border-l-2 border-tealsoft'}`}>
                {m.role === 'assistant' ? renderWithTimestamps(m.content, onSeek) : m.content}
              </div>
            ))}
            {busy && <div className="text-ink2 text-xs animate-pulse">…</div>}
          </div>
          <form className="flex gap-2 p-3 border-t border-line" onSubmit={(e) => { e.preventDefault(); void send(input) }}>
            <input className="flex-1" value={input} onChange={(e) => setInput(e.target.value)} placeholder={t('chatPlaceholder')} />
            <button className="btn-primary" disabled={busy || !input.trim()}>{t('chatSend')}</button>
          </form>
        </div>
      )}
    </div>
  )
}
