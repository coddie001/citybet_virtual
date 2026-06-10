import type {
  ApiFixture,
  ApiFixtureCard,
  ApiLeague,
  ApiLiveCard,
  ApiMatchSyncPayload,
  ApiResult,
  ApiScorer,
  ApiTableRow,
} from './types'
import type {
  FixtureItem,
  FormResult,
  LeagueId,
  LeagueMeta,
  LiveMatch,
  MatchSyncPayload,
  ResultItem,
  ScorerRow,
  TableRow,
  UpcomingMatch,
} from '../types'

const LEAGUE_IDS: LeagueId[] = ['Premier League', 'La Liga', 'Serie A', 'Bundesliga']

export function isKnownLeague(name: string): name is Exclude<LeagueId, 'ALL'> {
  return LEAGUE_IDS.includes(name as LeagueId)
}

export function teamAbbr(name: string): string {
  const clean = name.replace(/[^a-zA-Z\s]/g, '').trim()
  const words = clean.split(/\s+/).filter(Boolean)
  if (words.length >= 2) {
    return (words[0].slice(0, 1) + words[1].slice(0, 2)).toUpperCase()
  }
  return clean.slice(0, 3).toUpperCase()
}

export const DEFAULT_FIXTURE_IMAGE = '/static/team-fix-imgs/default_image.webp'

/** Normalize fixture image URLs for the Vite dev server. */
export function resolveImageUrl(url: string | null | undefined): string {
  if (!url) return DEFAULT_FIXTURE_IMAGE
  const stripped = url
    .replace(/^https?:\/\/localhost:8000/, '')
    .replace(/^https?:\/\/127\.0\.0\.1:8000/, '')
  if (stripped.startsWith('/static/')) return stripped
  if (stripped.startsWith('/img/')) return stripped
  return stripped || DEFAULT_FIXTURE_IMAGE
}

function mapFormResults(values: string[] | undefined): FormResult[] {
  return (values ?? []).map((v) => (v === 'W' || v === 'L' ? v : 'D'))
}

export function mapLeague(api: ApiLeague): LeagueMeta | null {
  if (!isKnownLeague(api.league_name)) return null
  return {
    id: api.league_name,
    name: api.league_name,
    seasonId: api.season_id,
    gameweek: api.current_gwk,
    totalGameweeks: api.cum_gwk,
  }
}

function mapFixtureStatus(
  status: string,
  hasVideo: boolean,
): 'upcoming' | 'preparing' | 'live' | 'completed' {
  if (status === 'completed') return 'completed'
  if (status === 'live' && hasVideo) return 'live'
  if (status === 'preparing' || (status === 'live' && !hasVideo)) return 'preparing'
  return 'upcoming'
}

export function mapFixtureCard(
  f: ApiFixtureCard,
  league: Exclude<LeagueId, 'ALL'>,
): UpcomingMatch | null {
  if (!f.home_team || !f.away_team) return null
  const hasVideo = f.has_video === true
  return {
    id: f.match_id,
    league,
    home: f.home_team.name,
    homeAbbr: teamAbbr(f.home_team.name),
    away: f.away_team.name,
    awayAbbr: teamAbbr(f.away_team.name),
    imageUrl: resolveImageUrl(f.fixture_image_url),
    showAtMs: f.show_at_ms,
    gameweek: f.gameweek,
    status: mapFixtureStatus(f.status, hasVideo),
    hasVideo,
  }
}

export function mapUpcoming(f: ApiFixture, league: Exclude<LeagueId, 'ALL'>): UpcomingMatch {
  const hasVideo = f.has_video === true
  const status = mapFixtureStatus(f.status, hasVideo)
  return {
    id: f.match_id,
    league,
    home: f.home_team.name,
    homeAbbr: teamAbbr(f.home_team.name),
    away: f.away_team.name,
    awayAbbr: teamAbbr(f.away_team.name),
    imageUrl: resolveImageUrl(f.fixture_image_url),
    showAtMs: f.show_at_ms,
    gameweek: f.gameweek,
    status,
    hasVideo,
  }
}

export function mapFixture(f: ApiFixture, league: Exclude<LeagueId, 'ALL'>): FixtureItem {
  const hasVideo = f.has_video === true
  return {
    id: f.match_id,
    league,
    gameweek: f.gameweek,
    home: f.home_team.name,
    away: f.away_team.name,
    date: f.game_date,
    time: f.game_time?.slice(0, 5) ?? '',
    status: mapFixtureStatus(f.status, hasVideo),
    imageUrl: resolveImageUrl(f.fixture_image_url),
    hasVideo,
    showAtMs: f.show_at_ms,
  }
}

export function mapResult(r: ApiResult, league: Exclude<LeagueId, 'ALL'>): ResultItem {
  return {
    id: r.match_id,
    league,
    gameweek: r.gameweek,
    home: r.home_team,
    away: r.away_team,
    score: r.score,
    date: r.game_date,
  }
}

export function mapTableRow(row: ApiTableRow): TableRow {
  return {
    rank: row.rank,
    club: row.team_name,
    mp: row.played,
    w: row.wins,
    d: row.draws,
    l: row.losses,
    gf: row.goals_scored,
    ga: row.goals_conceded,
    pts: row.points,
    last5: mapFormResults(row.last_5),
  }
}

export function mapScorer(s: ApiScorer): ScorerRow {
  return {
    rank: s.rank,
    player: s.player_name,
    club: s.team_name,
    goals: s.goals,
    appearances: s.appearances,
    faceUrl: s.player_face_url ?? undefined,
  }
}

function mapMatchSync(sync: ApiMatchSyncPayload | null | undefined): MatchSyncPayload | undefined {
  if (!sync) return undefined
  const final = sync.final_stats
  return {
    videoDurationSec: sync.video_duration_sec,
    totalSteps: sync.total_steps,
    goalEvents: (sync.goal_events ?? []).map((e) => ({
      side: e.side,
      step: e.step,
      videoSec: e.video_sec,
      homeScore: e.home_score,
      awayScore: e.away_score,
    })),
    finalStats: {
      homeGoals: final.home_goals,
      awayGoals: final.away_goals,
      score: final.score,
      possession: { homePct: final.possession.home_pct, awayPct: final.possession.away_pct },
      corners: final.corners,
      freeKicks: final.free_kicks,
      shotsHome: final.shots_home,
      shotsAway: final.shots_away,
      foulsHome: final.fouls_home,
      foulsAway: final.fouls_away,
      cornersHome: final.corners_home,
      cornersAway: final.corners_away,
    },
  }
}

/** Live stream row from a fixtures-API row (DB status is source of truth). */
export function mapFixtureToLiveMatch(f: FixtureItem): LiveMatch | null {
  if (f.status !== 'live' || f.hasVideo !== true) return null
  return {
    id: f.id,
    league: f.league,
    home: f.home,
    away: f.away,
    homeScore: 0,
    awayScore: 0,
    status: 'live',
    source: 'live_status',
    isOnAir: true,
    hasVideo: true,
    showAtMs: f.showAtMs,
    possession: [50, 50],
    shots: [0, 0],
    fouls: [0, 0],
    corners: [0, 0],
  }
}

export function mergeLiveFromFixtures(
  fromCards: LiveMatch[],
  fixtures: FixtureItem[],
): LiveMatch[] {
  const byId = new Map(fromCards.map((m) => [m.id, m]))
  for (const f of fixtures) {
    if (f.status !== 'live' || f.hasVideo !== true) continue
    const existing = byId.get(f.id)
    if (existing) {
      byId.set(f.id, {
        ...existing,
        home: f.home,
        away: f.away,
        league: f.league,
        showAtMs: f.showAtMs ?? existing.showAtMs,
        hasVideo: true,
        isOnAir: true,
        matchSync: existing.matchSync,
        homeScore: existing.homeScore,
        awayScore: existing.awayScore,
        possession: existing.possession,
        shots: existing.shots,
        fouls: existing.fouls,
        corners: existing.corners,
      })
    } else {
      const mapped = mapFixtureToLiveMatch(f)
      if (mapped) byId.set(f.id, mapped)
    }
  }
  return [...byId.values()]
}

export function mapLiveCard(card: ApiLiveCard): LiveMatch | null {
  const fixture = card.fixture
  if (!fixture || !isKnownLeague(card.league_name)) return null
  if (!fixture.home_team || !fixture.away_team) return null

  const matchSync = mapMatchSync(fixture.match_sync)
  const [homeScore, awayScore] = matchSync
    ? [matchSync.finalStats.homeGoals, matchSync.finalStats.awayGoals]
    : parseScore(fixture.score)
  // Stream drawer: only when DB live and video file is ready.
  const isStreamLive = card.source === 'live_status' || fixture.status === 'live'
  if (!isStreamLive || !fixture.has_video) return null

  const final = matchSync?.finalStats

  return {
    id: fixture.match_id,
    league: card.league_name,
    seasonId: card.season_id,
    home: fixture.home_team.name,
    away: fixture.away_team.name,
    homeScore,
    awayScore,
    status: 'live',
    showAtMs: fixture.show_at_ms,
    virtualClockMs: card.virtual_clock_ms,
    hasVideo: fixture.has_video,
    source: card.source,
    isOnAir: true,
    possession: final
      ? [Math.round(final.possession.homePct), Math.round(final.possession.awayPct)]
      : [50, 50],
    shots: final ? [final.shotsHome, final.shotsAway] : [0, 0],
    fouls: final ? [final.foulsHome, final.foulsAway] : [0, 0],
    corners: final ? [final.cornersHome, final.cornersAway] : [0, 0],
    matchSync,
  }
}

function parseScore(score: string | null): [number, number] {
  if (!score) return [0, 0]
  const parts = score.split('-').map((s) => parseInt(s.trim(), 10))
  if (parts.length !== 2 || parts.some(Number.isNaN)) return [0, 0]
  return [parts[0], parts[1]]
}
