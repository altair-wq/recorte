import { useState } from 'react'
import type { Moment } from '../api'
import { scoreTone } from './IntegrityBadge'
import { mmss } from '../lib/time'

const FILL = { green: 'bg-teal', amber: 'bg-amber', red: 'bg-red' }

type Props = {
  duration: number; moments: Moment[]; current: number; selectedId: string | null
  onSeek: (t: number) => void; onSelect: (m: Moment) => void
}

export default function Timeline({ duration, moments, current, selectedId, onSeek, onSelect }: Props) {
  const [hover, setHover] = useState<Moment | null>(null)
  const pct = (t: number) => `${Math.min(100, Math.max(0, (t / Math.max(duration, 1)) * 100))}%`
  return (
    <div className="select-none">
      <div className="relative h-12 bg-white border border-line rounded-card cursor-pointer"
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect()
          onSeek(((e.clientX - r.left) / r.width) * duration)
        }}>
        {moments.map((m) => {
          const tone = scoreTone(m.integrity.score)
          const sel = m.id === selectedId
          return (
            <button key={m.id} type="button"
              className={`absolute top-2 bottom-2 rounded-sm ${m.status === 'rejected' ? 'bg-line' : FILL[tone]} ${sel ? 'ring-2 ring-ink ring-offset-1' : 'opacity-80 hover:opacity-100'}`}
              style={{ left: pct(m.start), width: `calc(${pct(m.end - m.start)} - 1px)`, minWidth: 6 }}
              onClick={(e) => { e.stopPropagation(); onSelect(m); onSeek(m.start) }}
              onMouseEnter={() => setHover(m)} onMouseLeave={() => setHover(null)}>
              {m.status === 'approved' && (
                <span className="absolute inset-0 grid place-items-center text-white text-[11px] font-bold">✓</span>
              )}
            </button>
          )
        })}
        <div className="absolute top-0 bottom-0 w-px bg-ink pointer-events-none" style={{ left: pct(current) }}>
          <div className="absolute -top-1 -left-1 w-[9px] h-[9px] rounded-full bg-ink" />
        </div>
        {hover && (
          <div className="absolute -top-9 bg-ink text-paper text-xs px-2 py-1 rounded shadow pointer-events-none whitespace-nowrap max-w-xs truncate"
            style={{ left: pct(hover.start) }}>
            {mmss(hover.start)} · {hover.headline}
          </div>
        )}
      </div>
      <div className="flex justify-between text-[11px] text-ink2 mt-1 tabular-nums">
        <span>00:00</span><span>{mmss(current)}</span><span>{mmss(duration)}</span>
      </div>
    </div>
  )
}
