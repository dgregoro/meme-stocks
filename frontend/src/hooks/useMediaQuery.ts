import { useState, useEffect } from 'react'

/**
 * Returns true when the media query matches (e.g. narrow viewport).
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia(query).matches
  })

  useEffect(() => {
    if (!window.matchMedia) return
    const m = window.matchMedia(query)
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches)
    m.addEventListener('change', handler)
    const id = requestAnimationFrame(() => setMatches(m.matches))
    return () => {
      cancelAnimationFrame(id)
      m.removeEventListener('change', handler)
    }
  }, [query])

  return matches
}
