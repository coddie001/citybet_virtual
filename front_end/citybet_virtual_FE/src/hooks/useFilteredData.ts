import { useMemo } from 'react'
import type { LeagueId } from '../types'
import { filterByLeague, usePlatformData } from '../context/PlatformDataContext'

export function useFilteredData(league: LeagueId) {
  const { upcoming, fixtures, results, liveMatches, tables, scorers } = usePlatformData()

  return useMemo(
    () => ({
      upcoming: filterByLeague(upcoming, league),
      fixtures: filterByLeague(fixtures, league),
      results: filterByLeague(results, league),
      liveMatches:
        league === 'ALL'
          ? liveMatches
          : liveMatches.filter((m) => m.league === league),
      tables,
      scorers,
    }),
    [league, upcoming, fixtures, results, liveMatches, tables, scorers],
  )
}
