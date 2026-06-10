import type { LeagueId } from '../types'

/** Stable display order for all-league views. */
export const LEAGUE_DISPLAY_ORDER: Exclude<LeagueId, 'ALL'>[] = [
  'Premier League',
  'La Liga',
  'Serie A',
  'Bundesliga',
]

export function leagueSortIndex(league: LeagueId): number {
  const idx = LEAGUE_DISPLAY_ORDER.indexOf(league as Exclude<LeagueId, 'ALL'>)
  return idx >= 0 ? idx : 99
}
