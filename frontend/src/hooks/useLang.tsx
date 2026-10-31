import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { STRINGS, type Lang, type StringKey } from '../strings'

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (k: StringKey) => string }
const LangCtx = createContext<Ctx>({ lang: 'es', setLang: () => {}, t: (k) => STRINGS.es[k] })

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    try { return (localStorage.getItem('recorte.lang') as Lang) || 'es' } catch { return 'es' }
  })
  const setLang = useCallback((l: Lang) => {
    setLangState(l)
    try { localStorage.setItem('recorte.lang', l) } catch { /* ignore */ }
  }, [])
  const value = useMemo<Ctx>(() => ({ lang, setLang, t: (k) => STRINGS[lang][k] }), [lang, setLang])
  return <LangCtx.Provider value={value}>{children}</LangCtx.Provider>
}

export function useLang() {
  return useContext(LangCtx)
}
