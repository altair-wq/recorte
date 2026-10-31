import { useEffect, useRef, useState } from 'react'

/** Poll `fetcher` every 1.5 s until `done(value)` is true. */
export function useJob<T>(fetcher: (() => Promise<T>) | null, done: (v: T) => boolean, intervalMs = 1500) {
  const [value, setValue] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const doneRef = useRef(done)
  doneRef.current = done

  useEffect(() => {
    if (!fetcher) return
    let alive = true
    let timer: number | undefined
    const tick = async () => {
      try {
        const v = await fetcherRef.current!()
        if (!alive) return
        setValue(v)
        setError(null)
        if (doneRef.current(v)) return
      } catch (e) {
        if (!alive) return
        setError(e instanceof Error ? e.message : String(e))
      }
      timer = window.setTimeout(tick, intervalMs)
    }
    void tick()
    return () => {
      alive = false
      if (timer) window.clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher !== null, intervalMs])

  return { value, error, setValue }
}
