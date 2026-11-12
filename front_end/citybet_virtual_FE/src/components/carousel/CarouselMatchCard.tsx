import { useMemo } from 'react'
import { useSmoothCountdown } from '../../hooks/useSmoothCountdown'
import { isBroadcastOnAir } from '../../utils/liveVideo'
import { MatchCard } from './MatchCard'
import type { ApiCountdown } from '../../api/types'
import type { LeagueId, UpcomingMatch } from '../../types'

interface CarouselMatchCardProps {
  match: UpcomingMatch
  onWatchLive?: (league: LeagueId, matchId?: string) => void
  eager?: boolean
}

function buildScheduledCountdown(match: UpcomingMatch): ApiCountdown | null {
  const startMs = match.scheduledStartAtMs ?? match.countdown?.scheduled_start_at_ms ?? undefined
  if (!startMs) return null
  const msUntil = startMs - Date.now()
  if (msUntil <= 0) return null
  const seconds = Math.max(0, Math.ceil(msUntil / 1000))
  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  return {
    next_match_id: match.id,
    show_at_ms: match.showAtMs,
    scheduled_start_at_ms: startMs,
    ms_until_kickoff: msUntil,
    in_countdown_window: true,
    countdown_seconds: seconds,
    is_kickoff: false,
    formatted: `${mm}:${ss}`,
    countdown_real_ms: true,
  }
}

/** Countdown from backend `/carousel`; preparing rows always show MM:SS timer overlay. */
export function CarouselMatchCard({ match, onWatchLive, eager }: CarouselMatchCardProps) {
  const onAir = isBroadcastOnAir(match)
  const isPreparing = match.status === 'preparing'

  const countdownInput = useMemo(() => {
    if (onAir) return null
    if (match.countdown?.next_match_id === match.id && match.countdown.in_countdown_window) {
      return match.countdown
    }
    if (isPreparing) {
      return buildScheduledCountdown(match)
    }
    return null
  }, [onAir, isPreparing, match])

  const ticked = useSmoothCountdown(countdownInput)
  const showCountdown = !onAir && Boolean(countdownInput) && ticked.inWindow

  return (
    <MatchCard
      match={match}
      eager={eager}
      showCountdown={showCountdown}
      showLive={onAir}
      showUpNext={match.isNext === true && isPreparing}
      countdownLabel={isPreparing ? 'Starts in' : 'Game starts'}
      countdown={ticked.formatted}
      onWatchLive={
        onWatchLive && onAir ? () => onWatchLive(match.league, match.id) : undefined
      }
    />
  )
}
