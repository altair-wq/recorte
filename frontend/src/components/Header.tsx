import { Link } from 'react-router-dom'
import { useLang } from '../hooks/useLang'

export default function Header({ right }: { right?: React.ReactNode }) {
  const { lang, setLang, t } = useLang()
  return (
    <header className="flex items-center justify-between px-6 h-14 border-b border-line bg-paper sticky top-0 z-20">
      <Link to="/" className="flex items-baseline gap-3">
        <span className="font-serif text-2xl font-medium tracking-tight">{t('appName')}</span>
        <span className="text-xs text-ink2 hidden sm:inline">{t('tagline')}</span>
      </Link>
      <div className="flex items-center gap-3">
        {right}
        <div className="flex border border-line rounded-md overflow-hidden text-xs">
          {(['es', 'en'] as const).map((l) => (
            <button key={l} onClick={() => setLang(l)}
              className={`px-2 py-1 uppercase ${lang === l ? 'bg-ink text-paper' : 'bg-white text-ink2 hover:bg-paper2'}`}>
              {l}
            </button>
          ))}
        </div>
      </div>
    </header>
  )
}
