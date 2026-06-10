import { useMemo } from 'react'
import { isBroadcastVideoReady } from '../utils/liveVideo'
import { COUNTDOWN_WINDOW_MS } from './useKickoffCountdown'
import type { LiveMatch } from '../types'

/** Load video when has_video is true; live matches poll until ready. */
export function useShouldLoadVideo(match: LiveMatch | null, virtualMs: number): boolean {
  return useMemo(() => {
    if (!match) return false

    const isLive = match.status === 'live' || match.source === 'live_status'
    if (isLive) return isBroadcastVideoReady(match)

    if (!match.hasVideo) return false
    const showAt = match.showAtMs ?? 0
    const untilKickoff = showAt - virtualMs
    return untilKickoff >= 0 && untilKickoff <= COUNTDOWN_WINDOW_MS
  }, [match, virtualMs])
}
