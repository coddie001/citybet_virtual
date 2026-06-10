import { useMemo } from 'react'
import type { ApiCountdown } from '../../api/types'
import { useSmoothCountdown } from '../../hooks/useSmoothCountdown'
import { buildMatchCountdown } from '../../utils/matchCountdown'
import { isBroadcastOnAir } from '../../utils/liveVideo'
import { MatchCard } from './MatchCard'
import type { LeagueId, UpcomingMatch } from '../../types'

interface CarouselMatchCardProps {
  match: UpcomingMatch
  virtualClockMs?: number
  apiCountdown?: ApiCountdown | null
  onWatchLive?: (league: LeagueId, matchId?: string) => void
}

/**
 * Each card owns its countdown state from kickoff timing.
 * In the 3-minute window → ticking overlay. Otherwise → static fixture image.
 */
export function CarouselMatchCard({
  match,
  virtualClockMs,
  apiCountdown,
  onWatchLive,
}: CarouselMatchCardProps) {
  const countdownInput = useMemo(() => {
    if (virtualClockMs == null) return null

    const apiMatchesCard =
      apiCountdown?.next_match_id === match.id &&
      apiCountdown.show_at_ms === match.showAtMs &&
      apiCountdown.in_countdown_window
    if (apiMatchesCard) return apiCountdown

    return buildMatchCountdown(match.id, match.showAtMs ?? 0, virtualClockMs)
  }, [match.id, match.showAtMs, virtualClockMs, apiCountdown])

  const ticked = useSmoothCountdown(countdownInput)
  const onAir = isBroadcastOnAir(match)
  const showCountdown = !onAir && ticked.inWindow

  return (
    <MatchCard
      match={match}
      showCountdown={showCountdown}
      showLive={onAir}
      countdown={ticked.formatted}
      onWatchLive={
        onWatchLive && onAir ? () => onWatchLive(match.league, match.id) : undefined
      }
    />
  )
}
