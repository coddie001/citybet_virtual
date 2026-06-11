import type { ApiCountdown } from '../api/types'

export type LeagueId = 'ALL' | 'Premier League' | 'La Liga' | 'Serie A' | 'Bundesliga'

export type TabId = 'table' | 'fixtures' | 'results' | 'stats'

export type FormResult = 'W' | 'D' | 'L'

export interface LeagueMeta {
  id: LeagueId
  name: string
  seasonId: string
  gameweek: number
  totalGameweeks: number
}

export interface UpcomingMatch {
  id: string
  league: LeagueId
  home: string
  homeAbbr: string
  away: string
  awayAbbr: string
  imageUrl: string
  showAtMs: number
  gameweek: number
  status: 'upcoming' | 'preparing' | 'live' | 'completed'
  hasVideo?: boolean
  isNext?: boolean
  /** Backend carousel identity and ordering. */
  carouselId?: string
  carouselStep?: number
  scheduledStartAtMs?: number
  countdown?: ApiCountdown
}

export interface TableRow {
  rank: number
  club: string
  mp: number
  w: number
  d: number
  l: number
  gf: number
  ga: number
  pts: number
  last5: FormResult[]
}

export interface FixtureItem {
  id: string
  league: LeagueId
  gameweek: number
  home: string
  away: string
  date: string
  time: string
  status: 'upcoming' | 'preparing' | 'live' | 'completed'
  imageUrl?: string
  hasVideo?: boolean
  showAtMs?: number
  scheduledStartAtMs?: number
  matchSync?: MatchSyncPayload
}

export interface ResultItem {
  id: string
  league: LeagueId
  gameweek: number
  home: string
  away: string
  score: string
  date: string
}

export interface ScorerRow {
  rank: number
  player: string
  club: string
  goals: number
  appearances: number
  faceUrl?: string
}

export interface MatchGoalEvent {
  side: 'home' | 'away'
  step: number
  videoSec: number
  homeScore: number
  awayScore: number
}

export interface MatchSyncFinalStats {
  homeGoals: number
  awayGoals: number
  score: string
  possession: { homePct: number; awayPct: number }
  corners: number
  freeKicks: number
  shotsHome: number
  shotsAway: number
  foulsHome: number
  foulsAway: number
  cornersHome: number
  cornersAway: number
}

export interface MatchSyncPayload {
  videoDurationSec: number
  totalSteps: number
  goalEvents: MatchGoalEvent[]
  finalStats: MatchSyncFinalStats
}

export interface LiveMatch {
  id: string
  league: LeagueId
  seasonId?: string
  home: string
  away: string
  homeScore: number
  awayScore: number
  status: 'live' | 'completed'
  showAtMs?: number
  virtualClockMs?: number
  scheduledStartAtMs?: number
  hasVideo?: boolean
  source?: string
  isOnAir?: boolean
  /** True when this is a replay match shown because no live broadcast is available. */
  isFallback?: boolean
  possession: [number, number]
  shots: [number, number]
  fouls: [number, number]
  corners: [number, number]
  videoUrl?: string
  matchSync?: MatchSyncPayload
}
