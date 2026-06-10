/**
 * Persist platform API payloads in localStorage so repeat visits load instantly.
 * Background refresh updates only when fingerprint changes.
 */

import type {
  FixtureItem,
  LeagueMeta,
  LiveMatch,
  ResultItem,
  ScorerRow,
  TableRow,
  UpcomingMatch,
} from '../types'

const STORAGE_KEY = 'citybet_platform_cache'
const CACHE_VERSION = 28

type LeagueKey = 'Premier League' | 'La Liga' | 'Serie A' | 'Bundesliga'

export interface PlatformCacheSnapshot {
  version: number
  savedAt: number
  fingerprint: string
  leagues: LeagueMeta[]
  virtualClockMs: number
  liveMatches: LiveMatch[]
  upcoming: UpcomingMatch[]
  fixtures: FixtureItem[]
  results: ResultItem[]
  tables: Record<LeagueKey, TableRow[]>
  scorers: Record<LeagueKey, ScorerRow[]>
}

function emptyTables(): Record<LeagueKey, TableRow[]> {
  return {
    'Premier League': [],
    'La Liga': [],
    'Serie A': [],
    'Bundesliga': [],
  }
}

function emptyScorers(): Record<LeagueKey, ScorerRow[]> {
  return {
    'Premier League': [],
    'La Liga': [],
    'Serie A': [],
    'Bundesliga': [],
  }
}

export function buildFingerprint(parts: {
  leagues: LeagueMeta[]
  upcoming: UpcomingMatch[]
  liveMatches: LiveMatch[]
  results: ResultItem[]
  tables?: Record<string, TableRow[]>
  scorers?: Record<string, ScorerRow[]>
}): string {
  const leagueSig = parts.leagues.map((l) => `${l.id}:${l.gameweek}`).join('|')
  const upSig = parts.upcoming
    .slice(0, 16)
    .map((u) => `${u.id}:${u.status}:${u.gameweek}:${u.hasVideo ?? ''}`)
    .join('|')
  const liveSig = parts.liveMatches
    .map((m) => `${m.id}:${m.status}:${m.hasVideo ?? ''}:${m.homeScore}-${m.awayScore}`)
    .join('|')
  const resSig = parts.results
    .slice(0, 12)
    .map((r) => `${r.id}:${r.score}:${r.gameweek}`)
    .join('|')
  const tblSig = parts.tables
    ? Object.entries(parts.tables)
        .map(([k, rows]) => {
          const top = rows.slice(0, 3).map((r) => `${r.mp}:${r.pts}`).join(',')
          return `${k}:${rows.length}:${top}`
        })
        .join('|')
    : ''
  const scSig = parts.scorers
    ? Object.entries(parts.scorers)
        .map(([k, rows]) => `${k}:${rows[0]?.goals ?? 0}:${rows.length}`)
        .join('|')
    : ''
  return `${leagueSig}#${upSig}#${liveSig}#${resSig}#${tblSig}#${scSig}`
}

export function loadPlatformCache(): PlatformCacheSnapshot | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw) as PlatformCacheSnapshot
    if (data.version !== CACHE_VERSION) return null
    return {
      ...data,
      tables: data.tables ?? emptyTables(),
      scorers: data.scorers ?? emptyScorers(),
      fixtures: data.fixtures ?? [],
      results: data.results ?? [],
    }
  } catch {
    return null
  }
}

export function savePlatformCache(snapshot: Omit<PlatformCacheSnapshot, 'version' | 'savedAt'>): void {
  try {
    const payload: PlatformCacheSnapshot = {
      version: CACHE_VERSION,
      savedAt: Date.now(),
      ...snapshot,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Quota or private browsing — ignore
  }
}

export function clearPlatformCache(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

export function patchPlatformCache(
  patch: Partial<Omit<PlatformCacheSnapshot, 'version' | 'savedAt'>>,
): void {
  const existing = loadPlatformCache()
  if (!existing) return
  savePlatformCache({
    fingerprint: patch.fingerprint ?? existing.fingerprint,
    leagues: patch.leagues ?? existing.leagues,
    virtualClockMs: patch.virtualClockMs ?? existing.virtualClockMs,
    liveMatches: patch.liveMatches ?? existing.liveMatches,
    upcoming: patch.upcoming ?? existing.upcoming,
    fixtures: patch.fixtures ?? existing.fixtures,
    results: patch.results ?? existing.results,
    tables: patch.tables ?? existing.tables,
    scorers: patch.scorers ?? existing.scorers,
  })
}
