import type { ApiCountdown } from '../api/types'
import { COUNTDOWN_WINDOW_MS, VIRTUAL_CLOCK_SPEED } from '../constants/virtualClock'

/** Build a per-match countdown from kickoff time + league virtual clock. */
export function isMatchInCountdownWindow(showAtMs: number, virtualClockMs: number): boolean {
  const windowVirtualMs = COUNTDOWN_WINDOW_MS * VIRTUAL_CLOCK_SPEED
  return (
    virtualClockMs >= showAtMs - windowVirtualMs &&
    virtualClockMs < showAtMs
  )
}

export function buildMatchCountdown(
  matchId: string,
  showAtMs: number,
  virtualClockMs: number,
): ApiCountdown | null {
  if (!isMatchInCountdownWindow(showAtMs, virtualClockMs)) {
    return null
  }

  const untilVirtual = showAtMs - virtualClockMs
  const untilReal = untilVirtual / VIRTUAL_CLOCK_SPEED

  const seconds = Math.min(180, Math.max(1, Math.ceil(untilReal / 1000)))
  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')

  return {
    next_match_id: matchId,
    show_at_ms: showAtMs,
    virtual_clock_ms: virtualClockMs,
    ms_until_kickoff: Math.round(untilReal),
    in_countdown_window: true,
    countdown_seconds: seconds,
    is_kickoff: false,
    formatted: `${mm}:${ss}`,
    countdown_real_ms: true,
  }
}
