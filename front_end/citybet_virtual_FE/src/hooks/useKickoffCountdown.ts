import { useMemo } from 'react'

export const COUNTDOWN_WINDOW_MS = 3 * 60 * 1000 // 3 minutes before kickoff
const KICKOFF_GRACE_MS = 60_000

/** Normalize ms-until-kickoff across looping virtual season timelines. */
export function normalizeUntilKickoff(showAtMs: number, virtualMs: number, spanMs = 0): number {
  let until = showAtMs - virtualMs
  if (spanMs > 0) {
    while (until < -spanMs / 2) until += spanMs
    while (until > spanMs / 2) until -= spanMs
  }
  return until
}

export function useKickoffCountdown(showAtMs: number, virtualMs: number, spanMs = 0) {
  return useMemo(() => {
    const untilKickoffMs = normalizeUntilKickoff(showAtMs, virtualMs, spanMs)
    const inWindow = untilKickoffMs > 0 && untilKickoffMs <= COUNTDOWN_WINDOW_MS
    const seconds = inWindow
      ? Math.min(180, Math.max(1, Math.ceil(untilKickoffMs / 1000)))
      : 0
    const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
    const ss = String(seconds % 60).padStart(2, '0')
    return {
      inWindow,
      seconds,
      formatted: inWindow ? `${mm}:${ss}` : '00:00',
      isKickoff: untilKickoffMs <= 0 && untilKickoffMs > -KICKOFF_GRACE_MS,
      untilKickoffMs,
    }
  }, [showAtMs, virtualMs, spanMs])
}
