export function mmss(t: number): string {
  const s = Math.max(0, Math.round(t))
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export function span(a: number, b: number): string {
  return `${mmss(a)}–${mmss(b)}`
}

export function dur(a: number, b: number): string {
  return `${Math.round(b - a)} s`
}
