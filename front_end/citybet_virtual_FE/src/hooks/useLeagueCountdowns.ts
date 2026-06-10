import { useMemo } from 'react'
import type { ApiCountdown } from '../api/types'
import type { LeagueId } from '../types'
import { useSmoothCountdown } from './useSmoothCountdown'

type LeagueKey = Exclude<LeagueId, 'ALL'>
type Ticked = ReturnType<typeof useSmoothCountdown>

/** Smooth countdown per league — hooks must be called unconditionally. */
export function useLeagueCountdowns(
  countdownByLeague: Partial<Record<LeagueId, ApiCountdown>>,
): Record<LeagueKey, Ticked> {
  const premier = useSmoothCountdown(countdownByLeague['Premier League'])
  const laliga = useSmoothCountdown(countdownByLeague['La Liga'])
  const serieA = useSmoothCountdown(countdownByLeague['Serie A'])
  const bundesliga = useSmoothCountdown(countdownByLeague['Bundesliga'])

  return useMemo(
    () => ({
      'Premier League': premier,
      'La Liga': laliga,
      'Serie A': serieA,
      Bundesliga: bundesliga,
    }),
    [premier, laliga, serieA, bundesliga],
  )
}

export type LeagueCountdownTick = Ticked
