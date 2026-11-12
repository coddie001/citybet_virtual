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
  loadPlatformCache,
  patchPlatformCache,
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

export const CAROUSEL_LIMIT = 6
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
  /** Per-league readiness for each lazily-loaded panel (table/fixtures/results/stats). */
  loaded: Record<PanelKind, LeagueKey[]>
  refresh: () => void
}

export type PanelKind = 'table' | 'fixtures' | 'results' | 'stats'

const emptyLoaded = (): Record<PanelKind, LeagueKey[]> => ({
  table: [],
  fixtures: [],
  results: [],
  stats: [],
})

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
  const [loaded, setLoaded] = useState(emptyLoaded)
  const fingerprintRef = useRef('')
  const leaguesRef = useRef<LeagueMeta[]>([])

  const pollCountRef = useRef(0)

  const fetchAll = useCallback(async () => {
    try {
      // ── PHASE 1: Table & League Meta FIRST (<100ms) ───────────────
      const leagueRows = await api.leagues()
      const mappedLeagues = leagueRows.map(mapLeague).filter((l): l is LeagueMeta => l !== null)
      if (mappedLeagues.length === 0) {
        throw new Error('No recognised leagues in API response')
      }
      leaguesRef.current = mappedLeagues
      setLeagues(mappedLeagues)

      setError(null)

      // ── PHASE 2: everything in parallel — each piece renders as soon as it lands ─
      // Carousel: fast /carousel endpoint, independent of tables and /live/all.
      const carouselPromise = api
        .carousel()
        .then((res) =>
          res.mode === 'wall_clock'
            ? res.items.map(mapCarouselItem).filter((m): m is UpcomingMatch => m !== null)
            : null,
        )
        .catch(() => null)
        .then((items) => {
          if (items && items.length > 0) {
            setUpcoming(items)
            setCarouselReady(true)
          }
          return items
        })

      // Fixtures / results / stats: separate per-league calls, started now,
      // each committing its own slice + readiness flag the moment it resolves.
      const fixturesAcc: FixtureItem[] = []
      const resultsAcc: ResultItem[] = []
      const markLoaded = (kind: PanelKind, key: LeagueKey) =>
        setLoaded((prev) =>
          prev[kind].includes(key) ? prev : { ...prev, [kind]: [...prev[kind], key] },
        )
      const startDetails = () => Promise.allSettled(
        mappedLeagues.flatMap((league) => {
          const key = league.id as LeagueKey
          return [
            Promise.all([
              api.fixtures({
                seasonId: league.seasonId,
                status: 'upcoming',
                minGameweek: league.gameweek,
                limit: FIXTURES_LIMIT,
              }),
              api.fixtures({ seasonId: league.seasonId, status: 'preparing', limit: 12 }),
              api.fixtures({ seasonId: league.seasonId, status: 'live', limit: 8 }),
            ])
              .then(([up, prep, live]) => {
                const seen = new Set<string>()
                const rows: FixtureItem[] = []
                for (const f of [...live.fixtures, ...prep.fixtures, ...up.fixtures]) {
                  if (seen.has(f.match_id)) continue
                  seen.add(f.match_id)
                  rows.push(mapFixture(f, key))
                }
                fixturesAcc.push(...rows)
                setFixtures((prev) => [...prev.filter((f) => f.league !== key), ...rows])
              })
              .finally(() => markLoaded('fixtures', key)),
            api
              .results({ seasonId: league.seasonId, limit: RESULTS_LIMIT })
              .then((res) => {
                const rows = res.results.map((r) => mapResult(r, key))
                resultsAcc.push(...rows)
                setResults((prev) => [...prev.filter((r) => r.league !== key), ...rows])
              })
              .finally(() => markLoaded('results', key)),
            api
              .topScorers(league.seasonId)
              .then((top) =>
                setScorers((prev) => ({ ...prev, [key]: top.scorers.map(mapScorer) })),
              )
              .finally(() => markLoaded('stats', key)),
          ]
        }),
      )

      // Tables: each league renders independently.
      const tablesPromise = Promise.allSettled(
        mappedLeagues.map(async (league) => {
          const key = league.id as LeagueKey
          try {
            const tbl = await api.table(league.seasonId)
            setTables((prev) => ({ ...prev, [key]: tbl.table.map(mapTableRow) }))
          } finally {
            markLoaded('table', key)
          }
        }),
      )

      // Tables first: wait for them before firing the heavier requests so they
      // don't compete for the browser's ~6 connections / backend workers.
      await tablesPromise
      const detailsPromise = startDetails()

      const liveCards = await api.liveAll()
      const clock = liveCards.reduce((max, c) => Math.max(max, c.virtual_clock_ms), 0)
      const liveFromCards = liveCards.map(mapLiveCard).filter((m): m is LiveMatch => m !== null)

      setVirtualClockMs(clock)
      setCountdownByLeague(parseCountdowns(liveCards))
      setClocksByLeague(parseClocksFromLiveCards(liveCards))
      setLiveMatches(liveFromCards)

      // Legacy fallback only if /carousel gave nothing usable.
      let carouselUpcoming = await carouselPromise
      if (!carouselUpcoming || carouselUpcoming.length === 0) {
        carouselUpcoming = await loadCarouselQueue(mappedLeagues, liveCards)
        setUpcoming(carouselUpcoming)
      }
      setCarouselReady(true)
      await detailsPromise

      // Merge live broadcasts once fixtures are in; then cache.
      void (async () => {
        try {
          const globalLive = await loadGlobalLiveBroadcasts(mappedLeagues)
          setLiveMatches(
            sortLiveBroadcasts(mergeLiveFromFixtures([...globalLive, ...liveFromCards], fixturesAcc)),
          )
          setDetailsReady(true)
          patchPlatformCache({
            leagues: mappedLeagues,
            virtualClockMs: clock,
            upcoming: carouselUpcoming ?? [],
            fixtures: fixturesAcc,
            results: resultsAcc,
          })
        } catch {
          setDetailsReady(true)
        }
      })()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load platform data')
    }
  }, [])

  const refreshLiveAndPanels = useCallback(async () => {
    try {
      // Lightweight 5s poll: only fetch live cards and carousel to update clock/score/countdowns
      const liveCards = await api.liveAll()
      const mappedLeagues = leaguesRef.current

      const clock = liveCards.reduce((max, c) => Math.max(max, c.virtual_clock_ms), 0)
      const liveFromCards = liveCards.map(mapLiveCard).filter((m): m is LiveMatch => m !== null)

      setVirtualClockMs(clock)
      setCountdownByLeague(parseCountdowns(liveCards))
      setClocksByLeague(parseClocksFromLiveCards(liveCards))
      setLiveMatches((prev) => (prev.length === 0 ? liveFromCards : prev))

      pollCountRef.current += 1

      // Heavy 24-endpoint details refresh runs only every 30s (every 6th cycle)
      if (pollCountRef.current % 6 === 0 && mappedLeagues.length > 0) {
        const [refreshed, details, globalLive] = await Promise.all([
          loadCarouselQueue(mappedLeagues, liveCards),
          loadDetailsForLeagues(mappedLeagues),
          loadGlobalLiveBroadcasts(mappedLeagues),
        ])

        const live = sortLiveBroadcasts(
          mergeLiveFromFixtures([...globalLive, ...liveFromCards], details.fixturesAcc),
        )
        setLiveMatches(live)
        setUpcoming(refreshed)
        setFixtures(details.fixturesAcc)
        setResults(details.resultsAcc)
        setTables(details.tablesAcc)
        setScorers(details.scorersAcc)
      }
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
      loaded,
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
      loaded,
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
