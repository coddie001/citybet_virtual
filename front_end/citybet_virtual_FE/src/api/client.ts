/**
 * API client — Vite proxies /api → http://localhost:8000
 */

import type {
  ApiCountdown,
  ApiFixture,
  ApiLeague,
  ApiLiveCard,
  ApiScorersResponse,
  ApiSeason,
  ApiTableResponse,
  ApiTableRow,
} from './types'

const BASE = '/api'
/** Single poll cadence — carousel, table, fixtures, results, stats. */
export const LIVE_POLL_INTERVAL_MS = 5_000
import {
  COUNTDOWN_WINDOW_MS,
  FIXTURE_INTERVAL_MS,
  VIRTUAL_CLOCK_SPEED,
} from '../constants/virtualClock'

const CLOCK_SPEED = VIRTUAL_CLOCK_SPEED

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  }
  const res = await fetch(url.pathname + url.search)
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

async function getOptional<T>(path: string, params?: Record<string, string>): Promise<T | null> {
  try {
    return await get<T>(path, params)
  } catch {
    return null
  }
}

function leagueNameFromTournament(tournamentName: string): string {
  return tournamentName.replace(/\s+\d+$/, '').trim()
}

function seasonsToLeagues(seasons: ApiSeason[]): ApiLeague[] {
  return seasons.map((s) => ({
    league_name: leagueNameFromTournament(s.tournament_name),
    season_id: s.season_id,
    tournament_name: s.tournament_name,
    season_status: s.season_status,
    current_gwk: s.current_gwk,
    cum_gwk: s.cum_gwk,
    team_count: s.cum_teams,
  }))
}

function virtualClockForSeason(season: ApiSeason, spanMs: number): number {
  if (!season.created_at || spanMs <= 0) return 0
  const created = new Date(season.created_at).getTime()
  const elapsed = Date.now() - created
  const raw = Math.max(0, Math.floor(elapsed * CLOCK_SPEED))
  return raw % spanMs
}

function fixtureAtClock(fixtures: ApiFixture[], clock: number): ApiFixture | null {
  if (fixtures.length === 0) return null
  const sorted = [...fixtures].sort((a, b) => a.show_at_ms - b.show_at_ms)
  let current = sorted[0]
  for (const f of sorted) {
    if (f.show_at_ms <= clock) current = f
    else break
  }
  return current
}

function nextCountdownFixture(fixtures: ApiFixture[], clock: number): ApiFixture | null {
  const upcoming = [...fixtures]
    .filter((f) => f.status === 'upcoming')
    .sort((a, b) => a.show_at_ms - b.show_at_ms)
  if (upcoming.length === 0) return null

  const inWindow = upcoming.find((f) => {
    const ms = f.show_at_ms - clock
    return ms > 0 && ms <= COUNTDOWN_WINDOW_MS
  })
  if (inWindow) return inWindow

  const next = upcoming.find((f) => f.show_at_ms > clock)
  return next ?? upcoming[0]
}

const VIRTUAL_SPEED = Number(import.meta.env.VITE_VIRTUAL_CLOCK_SPEED ?? 60)

function buildCountdown(fixture: ApiFixture, clock: number): ApiCountdown {
  const untilVirtual = fixture.show_at_ms - clock
  const untilReal = Math.max(0, untilVirtual) / VIRTUAL_SPEED
  const in_countdown_window = untilReal > 0 && untilReal <= COUNTDOWN_WINDOW_MS
  const countdown_seconds = in_countdown_window
    ? Math.min(180, Math.ceil(untilReal / 1000))
    : 0
  const totalSec = in_countdown_window ? countdown_seconds : 0
  const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
  const ss = String(totalSec % 60).padStart(2, '0')

  return {
    next_match_id: fixture.match_id,
    show_at_ms: fixture.show_at_ms,
    virtual_clock_ms: clock,
    ms_until_kickoff: in_countdown_window ? Math.round(untilReal) : 0,
    in_countdown_window,
    countdown_seconds,
    is_kickoff: false,
    formatted: in_countdown_window ? `${mm}:${ss}` : '00:00',
    countdown_real_ms: true,
  }
}

function buildLiveCardsFromFixtures(
  leagues: ApiLeague[],
  seasons: ApiSeason[],
  fixturesBySeason: Record<string, ApiFixture[]>,
): ApiLiveCard[] {
  const seasonMap = Object.fromEntries(seasons.map((s) => [s.season_id, s]))

  return leagues.map((league) => {
    const season = seasonMap[league.season_id]
    const fixtures = fixturesBySeason[league.season_id] ?? []
    const maxShow = fixtures.reduce((m, f) => Math.max(m, f.show_at_ms), 0)
    const span = maxShow + FIXTURE_INTERVAL_MS
    const clock = season ? virtualClockForSeason(season, span) : 0

    const liveStatus = fixtures.find((f) => f.status === 'live')
    const scheduled = fixtureAtClock(fixtures, clock)
    const fixture = liveStatus ?? scheduled

    let source = 'none'
    if (liveStatus) source = 'live_status'
    else if (fixture?.status === 'completed') source = 'virtual_completed'
    else if (fixture?.status === 'upcoming') source = 'virtual_upcoming'
    else if (fixture) source = 'virtual'

    const countdownFixture =
      nextCountdownFixture(fixtures, clock) ??
      fixtures.find(
        (f) =>
          f.status === 'live' &&
          !f.has_video &&
          f.show_at_ms - clock > 0 &&
          f.show_at_ms - clock <= COUNTDOWN_WINDOW_MS,
      )

    return {
      league_name: league.league_name,
      season_id: league.season_id,
      virtual_clock_ms: clock,
      source,
      countdown: countdownFixture ? buildCountdown(countdownFixture, clock) : undefined,
      fixture: fixture
        ? {
            match_id: fixture.match_id,
            season_id: fixture.season_id,
            gameweek: fixture.gameweek,
            show_at_ms: fixture.show_at_ms,
            virtual_clock_ms: clock,
            next_show_at_ms: null,
            status: fixture.status,
            score: fixture.score,
            fixture_image_url: fixture.fixture_image_url,
            home_team: fixture.home_team,
            away_team: fixture.away_team,
            has_video: fixture.has_video ?? false,
            video_endpoint: `/video/${fixture.match_id}`,
          }
        : null,
    }
  })
}

async function fetchLeagues(): Promise<ApiLeague[]> {
  const direct = await getOptional<ApiLeague[]>('/leagues')
  if (direct) return direct
  const seasons = await get<ApiSeason[]>('/seasons', { status: 'active' })
  return seasonsToLeagues(seasons)
}

async function fetchSeasons(): Promise<ApiSeason[]> {
  return get<ApiSeason[]>('/seasons', { status: 'active' })
}

async function fetchTable(seasonId: string): Promise<ApiTableResponse> {
  const modern = await getOptional<ApiTableResponse>(`/seasons/${seasonId}/table`)
  if (modern && Array.isArray(modern.table)) return modern

  const legacy = await get<ApiTableRow[]>(`/seasons/${seasonId}/table`)
  return {
    season_id: seasonId,
    tournament_name: '',
    current_gwk: 0,
    table: legacy,
  }
}

export const api = {
  leagues: fetchLeagues,
  seasons: fetchSeasons,

  fixtures: (opts?: {
    seasonId?: string
    status?: string
    limit?: number
    minShowAtMs?: number
    minGameweek?: number
  }) =>
    get<{ total: number; fixtures: ApiFixture[] }>('/fixtures', {
      ...(opts?.seasonId ? { season_id: opts.seasonId } : {}),
      ...(opts?.status ? { status: opts.status } : {}),
      ...(opts?.limit ? { limit: String(opts.limit) } : {}),
      ...(opts?.minShowAtMs != null ? { min_show_at_ms: String(opts.minShowAtMs) } : {}),
      ...(opts?.minGameweek != null ? { min_gameweek: String(opts.minGameweek) } : {}),
    }),

  table: fetchTable,

  results: (opts?: { seasonId?: string; limit?: number }) =>
    get<{ total: number; results: import('./types').ApiResult[] }>('/results', {
      ...(opts?.seasonId ? { season_id: opts.seasonId } : {}),
      ...(opts?.limit ? { limit: String(opts.limit) } : {}),
    }),

  topScorers: async (seasonId: string): Promise<ApiScorersResponse> => {
    const data = await getOptional<ApiScorersResponse>('/stats/top-scorers', {
      season_id: seasonId,
    })
    return (
      data ?? {
        season_id: seasonId,
        tournament_name: '',
        scorers: [],
      }
    )
  },

  liveAll: async (): Promise<ApiLiveCard[]> => {
    const direct = await getOptional<ApiLiveCard[]>('/live/all')
    if (direct) return direct

    const [leagues, seasons] = await Promise.all([fetchLeagues(), fetchSeasons()])
    const fixturesBySeason: Record<string, ApiFixture[]> = {}
    await Promise.all(
      leagues.map(async (league) => {
        const { fixtures } = await api.fixtures({ seasonId: league.season_id, limit: 200 })
        fixturesBySeason[league.season_id] = fixtures
      }),
    )
    return buildLiveCardsFromFixtures(leagues, seasons, fixturesBySeason)
  },

  videoUrl: (matchId: string) => `${BASE}/video/${matchId}`,

  videoDirectUrl: (matchId: string) => `${BASE}/video/${matchId}`,

  /** Single canonical stream — API handles Range chunks from videos/. */
  videoSources: (matchId: string) => [`${BASE}/video/${matchId}`],

  /** Lightweight probe — range request + moov-at-start check for streamability. */
  async probeVideo(matchId: string): Promise<string | null> {
    const { isVideoDebugEnabled, logVideoDebug, probeVideoUrl } = await import(
      '../utils/videoPlaybackDebug'
    )
    const sources = [`${BASE}/video/${matchId}`, `/videos/${matchId}_full.mp4`]
    for (const url of sources) {
      try {
        const probe = await probeVideoUrl(matchId, url)
        if (isVideoDebugEnabled()) {
          logVideoDebug(matchId, 'url-probe', { source: 'probeVideo', probe }, url)
        }
        if (probe.ok) return url
      } catch {
        // try next source
      }
    }
    return null
  },
}
