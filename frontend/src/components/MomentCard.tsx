import type { Moment } from '../api'
import { useLang } from '../hooks/useLang'
import { span, dur } from '../lib/time'
import IntegrityBadge from './IntegrityBadge'

export default function MomentCard({ m, selected, highlight, onClick }: { m: Moment; selected: boolean; highlight?: boolean; onClick: () => void }) {
  const { t } = useLang()
  const flag = m.integrity.flags[0]
  const pill = m.status === 'approved' ? 'bg-tealsoft text-teal border-teal/30' : m.status === 'rejected' ? 'bg-paper2 text-ink2 border-line' : 'bg-white text-ink2 border-line'
  const label = m.status === 'approved' ? t('statusApproved') : m.status === 'rejected' ? t('statusRejected') : t('candidate')
  return (
    <button type="button" onClick={onClick}
      className={`card w-full text-left p-3 transition-shadow hover:shadow-sm ${selected ? 'border-ink shadow-sm' : ''} ${highlight ? 'ring-2 ring-teal' : ''} ${m.status === 'rejected' ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-serif text-[17px] leading-snug font-medium">{m.headline}</h3>
        <IntegrityBadge score={m.integrity.score} label={false} />
      </div>
      <div className="mt-1 text-xs text-ink2 flex flex-wrap items-center gap-x-2 tabular-nums">
        <span>{m.speaker ?? '—'}</span><span>·</span><span>{span(m.start, m.end)}</span><span>·</span><span>{dur(m.start, m.end)}</span>
        {m.origin === 'chat' && <><span>·</span><span className="text-teal">{t('fromChat')}</span></>}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        {flag ? (
          <span className="text-xs text-amber truncate" title={flag.evidence}>⚑ {t(`flag_${flag.type}`)}: «{flag.evidence}»</span>
        ) : (
          <span className="text-xs text-teal">✓ {t('noFlags')}</span>
        )}
        <span className={`pill shrink-0 ${pill}`}>{label}</span>
      </div>
    </button>
  )
}
