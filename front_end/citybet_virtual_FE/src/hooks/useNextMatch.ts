import { useMemo } from 'react'
import { COUNTDOWN_WINDOW_MS, normalizeUntilKickoff } from './useKickoffCountdown'
import type { UpcomingMatch } from '../types'

/** Next fixture in countdown window, else next by virtual timeline. */
export function useNextMatch(upcoming: UpcomingMatch[], virtualMs: number, spanMs = 0) {
  return useMemo(() => {
    const sorted = [...upcoming]
      .filter((m) => m.status === 'upcoming')
      .sort((a, b) => a.showAtMs - b.showAtMs)

    if (sorted.length === 0) return null

    const until = (showAtMs: number) => normalizeUntilKickoff(showAtMs, virtualMs, spanMs)

    const inCountdown = sorted.find((m) => {
      const u = until(m.showAtMs)
      return u > 0 && u <= COUNTDOWN_WINDOW_MS
    })
    if (inCountdown) return inCountdown

    const next = sorted.find((m) => until(m.showAtMs) > 0)
    return next ?? sorted[0]
  }, [upcoming, virtualMs, spanMs])
}
