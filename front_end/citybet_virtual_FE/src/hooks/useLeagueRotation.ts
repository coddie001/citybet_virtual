import { useEffect, useState } from 'react'
import type { LeagueId } from '../types'
import { leagueKeys, usePlatformData } from '../context/PlatformDataContext'

export function useLeagueRotation(enabled: boolean, intervalMs = 8000) {
  const { leagues } = usePlatformData()
  const leagueIds = leagueKeys(leagues)
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (!enabled || leagueIds.length === 0) return
    const id = window.setInterval(() => {
      setIndex((i) => (i + 1) % leagueIds.length)
    }, intervalMs)
    return () => window.clearInterval(id)
  }, [enabled, intervalMs, leagueIds.length])

  const currentLeague = (leagueIds[index] ?? leagueIds[0] ?? 'Premier League') as Exclude<
    LeagueId,
    'ALL'
  >

  return { currentLeague, index }
}
