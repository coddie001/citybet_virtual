import { useEffect, useRef, useState } from 'react'
import type { ApiCountdown } from '../api/types'
import { COUNTDOWN_WINDOW_MS, virtualMsToRealMs } from '../constants/virtualClock'

const WINDOW_MS = COUNTDOWN_WINDOW_MS

/**
 * Smooth 1-second countdown anchored to API ms_until_kickoff.
 * Once the window opens, local deadline ticks through 03:00→00:00 even if
 * poll responses briefly drop in_countdown_window (5s live poll).
 */
export function useSmoothCountdown(countdown: ApiCountdown | null | undefined) {
  const anchorRef = useRef({ matchId: '', deadline: 0 })
  const [remainingMs, setRemainingMs] = useState(0)
  useEffect(() => {
    if (!countdown?.next_match_id || !countdown.in_countdown_window) {
      anchorRef.current = { matchId: '', deadline: 0 }
      setRemainingMs(0)
      return
    }

    const { next_match_id, ms_until_kickoff, in_countdown_window, is_kickoff } = countdown

    if (next_match_id !== anchorRef.current.matchId) {
      anchorRef.current = { matchId: next_match_id, deadline: 0 }
    }

    if (is_kickoff) {
      setRemainingMs(0)
      return
    }

    const now = Date.now()
    const realUntil = countdown?.countdown_real_ms
      ? ms_until_kickoff
      : virtualMsToRealMs(ms_until_kickoff)
    const apiInWindow =
      in_countdown_window && ms_until_kickoff > 0 && ms_until_kickoff <= WINDOW_MS
    const anchorActive =
      anchorRef.current.deadline > now &&
      anchorRef.current.matchId === next_match_id

    if (apiInWindow) {
      if (!anchorRef.current.deadline || anchorRef.current.matchId !== next_match_id) {
        anchorRef.current = { matchId: next_match_id, deadline: now + realUntil }
      } else {
        const expected = anchorRef.current.deadline - now
        if (Math.abs(expected - realUntil) > 1500) {
          anchorRef.current.deadline = now + realUntil
        }
      }
    } else if (!anchorActive) {
      setRemainingMs(0)
      return
    }

    const tick = () => setRemainingMs(Math.max(0, anchorRef.current.deadline - Date.now()))
    tick()
    const id = window.setInterval(tick, 200)
    return () => window.clearInterval(id)
  }, [
    countdown?.next_match_id,
    countdown?.ms_until_kickoff,
    countdown?.in_countdown_window,
    countdown?.is_kickoff,
    countdown?.countdown_real_ms,
  ])

  const inWindow =
    Boolean(countdown?.in_countdown_window) &&
    remainingMs > 0 &&
    remainingMs <= WINDOW_MS &&
    !countdown?.is_kickoff
  // Trust backend kickoff flag only — local wasInWindow caused sticky LIVE badges
  const isKickoff = Boolean(countdown?.is_kickoff)

  const totalSec = inWindow ? Math.max(0, Math.floor((remainingMs + 999) / 1000)) : 0
  const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
  const ss = String(totalSec % 60).padStart(2, '0')

  return {
    nextMatchId: countdown?.next_match_id,
    inWindow,
    isKickoff,
    formatted: inWindow ? `${mm}:${ss}` : '00:00',
  }
}
