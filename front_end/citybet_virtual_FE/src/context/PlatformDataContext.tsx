import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { api, LIVE_POLL_INTERVAL_MS } from '../api/client'
import type { ApiCountdown } from '../api/types'
import {
  buildFingerprint,
  loadPlatformCache,
  patchPlatformCache,
  savePlatformCache,
} from '../api/platformCache'
import type { ApiLiveCard } from '../api/types'
import {
  isKnownLeague,
  mapCarouselItem,
  mapFixture,
  mapFixtureCard,
  mapFixtureToLiveMatch,
  mapLeague,
  mapLiveCard,
  mergeLiveFromFixtures,
  mapResult,
  mapScorer,
  mapTableRow,
  mapUpcoming,
} from '../api/mappers'
import type {
  FixtureItem,
  LeagueId,
  LeagueMeta,
  LiveMatch,
  ResultItem,
  ScorerRow,
  TableRow,
  UpcomingMatch,
} from '../types'

type LeagueKey = Exclude<LeagueId, 'ALL'>

const CAROUSEL_LIMIT = 6
const FIXTURES_LIMIT = 40
const RESULTS_LIMIT = 50

interface PlatformDataValue {
  carouselReady: boolean
  detailsReady: boolean
  error: string | null
  leagues: LeagueMeta[]
  virtualClockMs: number
  clocksByLeague: Partial<Record<LeagueKey, number>>
  countdownByLeague: Partial<Record<LeagueId, ApiCountdown>>
  liveMatches: LiveMatch[]
  upcoming: UpcomingMatch[]
  fixtures: FixtureItem[]
  results: ResultItem[]
  tables: Record<LeagueKey, TableRow[]>
  scorers: Record<LeagueKey, ScorerRow[]>
  refresh: () => void
}

const emptyTables = (): Record<LeagueKey, TableRow[]> => ({
  'Premier League': [],
  'La Liga': [],
  'Serie A': [],
  'Bundesliga': [],
})

const emptyScorers = (): Record<LeagueKey, ScorerRow[]> => ({
  'Premier League': [],
  'La Liga': [],
  'Serie A': [],
  'Bundesliga': [],
})

const PlatformDataContext = createContext<PlatformDataValue | null>(null)

function parseCountdowns(
  liveCards: Awaited<ReturnType<typeof api.liveAll>>,
): Partial<Record<LeagueId, ApiCountdown>> {
  const map: Partial<Record<LeagueId, ApiCountdown>> = {}
  for (const card of liveCards) {
    if (isKnownLeague(card.league_name) && card.countdown) {
      map[card.league_name] = card.countdown
    }
  }
  return map
}

function parseClocksFromLiveCards(
  liveCards: Awaited<ReturnType<typeof api.liveAll>>,
): Partial<Record<LeagueKey, number>> {
  const map: Partial<Record<LeagueKey, number>> = {}
  for (const card of liveCards) {
    if (isKnownLeague(card.league_name) && card.virtual_clock_ms != null) {
      map[card.league_name] = card.virtual_clock_ms
    }
  }
  return map
}

async function loadDetailsForLeagues(mappedLeagues: LeagueMeta[]) {
  const tablesAcc = emptyTables()
  const scorersAcc = emptyScorers()
  const fixturesAcc: FixtureItem[] = []
  const resultsAcc: ResultItem[] = []

  await Promise.all(
    mappedLeagues.map(async (league) => {
      const key = league.id as LeagueKey
      const minGw = league.gameweek
      const [fxUpcoming, fxPreparing, fxLive, res, tbl, top] = await Promise.all([
        api.fixtures({
          seasonId: league.seasonId,
          status: 'upcoming',
          minGameweek: minGw,
          limit: FIXTURES_LIMIT,
        }),
        api.fixtures({ seasonId: league.seasonId, status: 'preparing', limit: 12 }),
        api.fixtures({ seasonId: league.seasonId, status: 'live', limit: 8 }),
        api.results({ seasonId: league.seasonId, limit: RESULTS_LIMIT }),
        api.table(league.seasonId),
        api.topScorers(league.seasonId),
      ])

      const seen = new Set<string>()
      for (const f of [...fxLive.fixtures, ...fxPreparing.fixtures, ...fxUpcoming.fixtures]) {
        if (seen.has(f.match_id)) continue
        seen.add(f.match_id)
        fixturesAcc.push(mapFixture(f, key))
      }
      resultsAcc.push(...res.results.map((r) => mapResult(r, key)))
      tablesAcc[key] = tbl.table.map(mapTableRow)
      scorersAcc[key] = top.scorers.map(mapScorer)
    }),
  )

  return { fixturesAcc, resultsAcc, tablesAcc, scorersAcc }
}

/** All on-air broadcasts globally — supports multiple live streams at once. */
async function loadGlobalLiveBroadcasts(mappedLeagues: LeagueMeta[]): Promise<LiveMatch[]> {
  const seasonToLeague = Object.fromEntries(
    mappedLeagues.map((l) => [l.seasonId, l.id as LeagueKey]),
  )
  try {
    const res = await api.fixtures({ status: 'live', limit: 32 })
    const matches: LiveMatch[] = []
    for (const f of res.fixtures) {
      const league = seasonToLeague[f.season_id]
      if (!league || !isKnownLeague(league)) continue
      const mapped = mapFixtureToLiveMatch(mapFixture(f, league))
      if (mapped) matches.push(mapped)
    }
    return matches
  } catch {
    return []
  }
}

function sortLiveBroadcasts(matches: LiveMatch[]): LiveMatch[] {
  return [...matches].sort(
    (a, b) =>
      (a.scheduledStartAtMs ?? a.showAtMs ?? 0) - (b.scheduledStartAtMs ?? b.showAtMs ?? 0),
  )
}

function pinCountdownCarouselCards(
  acc: UpcomingMatch[],
  liveCards: ApiLiveCard[],
  leagues: LeagueMeta[],
): UpcomingMatch[] {
  const seen = new Set(acc.map((m) => m.id))
  const minGwByLeague = Object.fromEntries(leagues.map((l) => [l.id, l.gameweek]))

  for (const card of liveCards) {
    const league = card.league_name
    if (!isKnownLeague(league)) continue

    const cd = card.countdown
    if (!cd?.next_match_id || seen.has(cd.next_match_id)) continue

    const existing = acc.find((m) => m.id === cd.next_match_id)
    if (existing) {
      seen.add(existing.id)
      continue
    }

    const fixture =
      card.fixture?.match_id === cd.next_match_id ? card.fixture : null
    if (!fixture) continue

    const floorGw = minGwByLeague[league] ?? 1
    if (fixture.gameweek < floorGw) continue

    const mapped = mapFixtureCard(fixture, league)
    if (mapped) {
      acc.push(mapped)
      seen.add(mapped.id)
    }
  }

  acc.sort((a, b) => a.showAtMs - b.showAtMs)
  return acc
}

/** Carousel queue — backend `/carousel` (wall-clock) with legacy per-league fallback. */
async function loadCarouselQueue(
  mappedLeagues: LeagueMeta[],
  liveCards: ApiLiveCard[] = [],
) {
  try {
    const res = await api.carousel()
    if (res.mode === 'wall_clock') {
      return res.items
        .map(mapCarouselItem)
        .filter((m): m is UpcomingMatch => m !== null)
    }
  } catch {
    // fall through to legacy loader
  }

  const acc: UpcomingMatch[] = []
  await Promise.all(
    mappedLeagues.map(async (league) => {
      const key = league.id as LeagueKey
      const minGw = league.gameweek
      const [fxUpcoming, fxPreparing, fxLive] = await Promise.all([
        api.fixtures({
          seasonId: league.seasonId,
          status: 'upcoming',
          minGameweek: minGw,
          limit: CAROUSEL_LIMIT,
        }),
        api.fixtures({ seasonId: league.seasonId, status: 'preparing', limit: 8 }),
        api.fixtures({ seasonId: league.seasonId, status: 'live', limit: 4 }),
      ])
      const seen = new Set<string>()
      for (const f of [...fxLive.fixtures, ...fxPreparing.fixtures, ...fxUpcoming.fixtures]) {
        if (seen.has(f.match_id)) continue
        seen.add(f.match_id)
        acc.push(mapUpcoming(f, key))
      }
    }),
  )

  const pinned = pinCountdownCarouselCards(acc, liveCards, mappedLeagues)
  return pinned
    .filter((m) => m.status !== 'completed')
    .sort((a, b) => a.showAtMs - b.showAtMs)
}

export function PlatformDataProvider({ children }: { children: ReactNode }) {
  const [carouselReady, setCarouselReady] = useState(false)
  const [detailsReady, setDetailsReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [leagues, setLeagues] = useState<LeagueMeta[]>([])
  const [virtualClockMs, setVirtualClockMs] = useState(0)
  const [countdownByLeague, setCountdownByLeague] = useState<
    Partial<Record<LeagueId, ApiCountdown>>
  >({})
  const [clocksByLeague, setClocksByLeague] = useState<
    Partial<Record<LeagueKey, number>>
  >({})
  const [liveMatches, setLiveMatches] = useState<LiveMatch[]>([])
  const [upcoming, setUpcoming] = useState<UpcomingMatch[]>([])
  const [fixtures, setFixtures] = useState<FixtureItem[]>([])
  const [results, setResults] = useState<ResultItem[]>([])
  const [tables, setTables] = useState(emptyTables)
  const [scorers, setScorers] = useState(emptyScorers)
  const fingerprintRef = useRef('')
  const leaguesRef = useRef<LeagueMeta[]>([])

  const fetchAll = useCallback(async () => {
    try {
      const [leagueRows, liveCards] = await Promise.all([api.leagues(), api.liveAll()])
      const mappedLeagues = leagueRows.map(mapLeague).filter((l): l is LeagueMeta => l !== null)
      if (mappedLeagues.length === 0) {
        throw new Error('No recognised leagues in API response')
      }
      leaguesRef.current = mappedLeagues

      const clock = liveCards.reduce((max, c) => Math.max(max, c.virtual_clock_ms), 0)
      const carouselUpcoming = await loadCarouselQueue(mappedLeagues, liveCards)

      setLeagues(mappedLeagues)
      setVirtualClockMs(clock)
      setCountdownByLeague(parseCountdowns(liveCards))
      setClocksByLeague(parseClocksFromLiveCards(liveCards))
      setUpcoming(carouselUpcoming)
      setCarouselReady(true)
      setError(null)

      const details = await loadDetailsForLeagues(mappedLeagues)
      const globalLive = await loadGlobalLiveBroadcasts(mappedLeagues)
      const live = sortLiveBroadcasts(
        mergeLiveFromFixtures(
          [...globalLive, ...liveCards.map(mapLiveCard).filter((m): m is LiveMatch => m !== null)],
          details.fixturesAcc,
        ),
      )

      setLiveMatches(live)
      setUpcoming(carouselUpcoming)
      setFixtures(details.fixturesAcc)
      setResults(details.resultsAcc)
      setTables(details.tablesAcc)
      setScorers(details.scorersAcc)
      setDetailsReady(true)

      patchPlatformCache({
        leagues: mappedLeagues,
        virtualClockMs: clock,
        liveMatches: live,
        upcoming: carouselUpcoming,
        fixtures: details.fixturesAcc,
        results: details.resultsAcc,
        tables: details.tablesAcc,
        scorers: details.scorersAcc,
      })

      const fingerprint = buildFingerprint({
        leagues: mappedLeagues,
        upcoming: carouselUpcoming,
        liveMatches: live,
        results: details.resultsAcc,
        tables: details.tablesAcc,
        scorers: details.scorersAcc,
      })
      if (fingerprint !== fingerprintRef.current) {
        fingerprintRef.current = fingerprint
        savePlatformCache({
          fingerprint,
          leagues: mappedLeagues,
          virtualClockMs: clock,
          liveMatches: live,
          upcoming: carouselUpcoming,
          fixtures: details.fixturesAcc,
          results: details.resultsAcc,
          tables: details.tablesAcc,
          scorers: details.scorersAcc,
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load platform data')
    }
  }, [])

  const refreshLiveAndPanels = useCallback(async () => {
    try {
      const [leagueRows, liveCards] = await Promise.all([api.leagues(), api.liveAll()])
      const mappedLeagues = leagueRows.map(mapLeague).filter((l): l is LeagueMeta => l !== null)
      const activeLeagues =
        mappedLeagues.length > 0 ? mappedLeagues : leaguesRef.current
      if (mappedLeagues.length > 0) {
        leaguesRef.current = mappedLeagues
        setLeagues(mappedLeagues)
      }

      const clock = liveCards.reduce((max, c) => Math.max(max, c.virtual_clock_ms), 0)
      const liveFromCards = liveCards.map(mapLiveCard).filter((m): m is LiveMatch => m !== null)

      if (activeLeagues.length === 0) {
        setVirtualClockMs(clock)
        setCountdownByLeague(parseCountdowns(liveCards))
        setClocksByLeague(parseClocksFromLiveCards(liveCards))
        setLiveMatches(liveFromCards)
        return
      }

      const [refreshed, details, globalLive] = await Promise.all([
        loadCarouselQueue(activeLeagues, liveCards),
        loadDetailsForLeagues(activeLeagues),
        loadGlobalLiveBroadcasts(activeLeagues),
      ])

      const live = sortLiveBroadcasts(
        mergeLiveFromFixtures([...globalLive, ...liveFromCards], details.fixturesAcc),
      )
      setVirtualClockMs(clock)
      setCountdownByLeague(parseCountdowns(liveCards))
      setClocksByLeague(parseClocksFromLiveCards(liveCards))
      setLiveMatches(live)

      setUpcoming(refreshed)
      setCarouselReady(true)
      setFixtures(details.fixturesAcc)
      setResults(details.resultsAcc)
      setTables(details.tablesAcc)
      setScorers(details.scorersAcc)
      setDetailsReady(true)

      const fingerprint = buildFingerprint({
        leagues: activeLeagues,
        upcoming: refreshed,
        liveMatches: live,
        results: details.resultsAcc,
        tables: details.tablesAcc,
        scorers: details.scorersAcc,
      })
      fingerprintRef.current = fingerprint
      savePlatformCache({
        fingerprint,
        leagues: activeLeagues,
        virtualClockMs: clock,
        liveMatches: live,
        upcoming: refreshed,
        fixtures: details.fixturesAcc,
        results: details.resultsAcc,
        tables: details.tablesAcc,
        scorers: details.scorersAcc,
      })
    } catch {
      // Keep cached state on poll failure
    }
  }, [])

  useEffect(() => {
    const cached = loadPlatformCache()
    if (cached) {
      fingerprintRef.current = cached.fingerprint
      leaguesRef.current = cached.leagues
      setLeagues(cached.leagues)
      setVirtualClockMs(cached.virtualClockMs)
      setLiveMatches(cached.liveMatches)
      setUpcoming(cached.upcoming)
      setFixtures(cached.fixtures)
      setResults(cached.results)
      setTables(cached.tables)
      setScorers(cached.scorers)
      setCarouselReady(true)
    }

    void fetchAll()
    const pollId = window.setInterval(refreshLiveAndPanels, LIVE_POLL_INTERVAL_MS)
    return () => {
      window.clearInterval(pollId)
    }
  }, [fetchAll, refreshLiveAndPanels])

  const value = useMemo(
    () => ({
      carouselReady,
      detailsReady,
      error,
      leagues,
      virtualClockMs,
      clocksByLeague,
      countdownByLeague,
      liveMatches,
      upcoming,
      fixtures,
      results,
      tables,
      scorers,
      refresh: fetchAll,
    }),
    [
      carouselReady,
      detailsReady,
      error,
      leagues,
      virtualClockMs,
      clocksByLeague,
      countdownByLeague,
      liveMatches,
      upcoming,
      fixtures,
      results,
      tables,
      scorers,
      fetchAll,
    ],
  )

  return <PlatformDataContext.Provider value={value}>{children}</PlatformDataContext.Provider>
}

export function usePlatformData() {
  const ctx = useContext(PlatformDataContext)
  if (!ctx) throw new Error('usePlatformData must be used within PlatformDataProvider')
  return ctx
}

export function getApiClockForSelection(
  selectedLeague: LeagueId,
  clocksByLeague: Partial<Record<LeagueKey, number>>,
  fallback: number,
  upcoming: { league: LeagueId }[],
): number {
  if (selectedLeague !== 'ALL') {
    return clocksByLeague[selectedLeague as LeagueKey] ?? fallback
  }
  const leagueList = [...new Set(upcoming.map((u) => u.league).filter((l) => l !== 'ALL'))]
  if (leagueList.length === 0) return fallback
  return Math.max(
    ...leagueList.map((l) => clocksByLeague[l as LeagueKey] ?? 0),
    fallback,
  )
}

export function getGameweekForLeague(leagues: LeagueMeta[], league: LeagueId): number {
  if (league === 'ALL') {
    if (leagues.length === 0) return 1
    return Math.min(...leagues.map((l) => l.gameweek))
  }
  return leagues.find((l) => l.id === league)?.gameweek ?? 1
}

/** Gameweek label — API leagues (sim progress) is the source of truth. */
export function getSyncedGameweek(
  leagues: LeagueMeta[],
  _fixtures: FixtureItem[],
  _results: ResultItem[],
  league: LeagueId,
  focusLeague?: Exclude<LeagueId, 'ALL'>,
): number {
  if (league === 'ALL') {
    if (focusLeague) {
      return leagues.find((l) => l.id === focusLeague)?.gameweek ?? 1
    }
    if (leagues.length === 0) return 1
    return Math.max(...leagues.map((l) => l.gameweek))
  }
  return leagues.find((l) => l.id === league)?.gameweek ?? 1
}

export function filterByLeague<T extends { league: LeagueId }>(items: T[], league: LeagueId): T[] {
  if (league === 'ALL') return items
  return items.filter((i) => i.league === league)
}

export function leagueKeys(leagues: LeagueMeta[]): LeagueKey[] {
  return leagues.map((l) => l.id as LeagueKey).filter(isKnownLeague)
}
