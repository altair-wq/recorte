import type { Clip } from '../api'
import { useLang } from '../hooks/useLang'
import { span } from '../lib/time'

export default function ProvenanceCard({ clip }: { clip: Clip }) {
  const { t } = useLang()
  const m = clip.moment
  if (!m) return null
  const qr = `/api/clips/${clip.id}/qr.png`
  return (
    <div className="card p-5">
      <div className="h-1 w-12 bg-teal mb-3" />
      <h2 className="font-serif text-2xl leading-tight">{m.headline}</h2>
      {m.speaker && <div className="text-ink2 mt-1">{m.speaker}</div>}
      <dl className="grid grid-cols-[110px_1fr] gap-x-4 gap-y-2 mt-4 text-sm">
        <dt className="text-[11px] uppercase tracking-wider text-teal pt-0.5">{t('source')}</dt><dd>{clip.source?.title}</dd>
        <dt className="text-[11px] uppercase tracking-wider text-teal pt-0.5">{t('span')}</dt><dd className="tabular-nums">{span(m.start, m.end)}</dd>
        <dt className="text-[11px] uppercase tracking-wider text-teal pt-0.5">{t('approvedBy')}</dt><dd>{m.review?.by}</dd>
        <dt className="text-[11px] uppercase tracking-wider text-teal pt-0.5">{t('integrity')}</dt><dd>{m.integrity.score} / 100</dd>
      </dl>
      <div className="flex items-center gap-4 mt-5 pt-4 border-t border-line">
        <img src={qr} alt="QR" width={96} height={96} className="rounded bg-white border border-line" />
        <div className="text-sm">
          <div className="font-medium">{t('verifiableClip')}</div>
          <a className="text-teal underline break-all" href={clip.verify_url} target="_blank" rel="noreferrer">{clip.verify_url}</a>
        </div>
      </div>
    </div>
  )
}
