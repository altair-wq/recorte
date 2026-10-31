import { useLang } from '../hooks/useLang'

export function scoreTone(score: number): 'green' | 'amber' | 'red' {
  return score >= 80 ? 'green' : score >= 50 ? 'amber' : 'red'
}

const TONE = {
  green: 'bg-tealsoft text-teal border-teal/30',
  amber: 'bg-ambersoft text-amber border-amber/30',
  red: 'bg-redsoft text-red border-red/30',
}

export default function IntegrityBadge({ score, size = 'sm', label = true }: { score: number; size?: 'sm' | 'lg'; label?: boolean }) {
  const { t } = useLang()
  const tone = scoreTone(score)
  const text = tone === 'green' ? t('scoreHigh') : tone === 'amber' ? t('scoreMid') : t('scoreLow')
  if (size === 'lg') {
    return (
      <div className={`flex items-center gap-4 border rounded-card px-4 py-3 ${TONE[tone]}`}>
        <div className="text-4xl font-semibold tabular-nums leading-none">{score}</div>
        <div className="leading-tight">
          <div className="text-[11px] uppercase tracking-wider opacity-80">{t('integrity')}</div>
          <div className="text-sm font-medium">{text}</div>
        </div>
      </div>
    )
  }
  return (
    <span className={`pill ${TONE[tone]}`} title={text}>
      <span className="tabular-nums font-semibold">{score}</span>
      {label && <span className="ml-1 opacity-80 hidden xl:inline">· {text}</span>}
    </span>
  )
}
