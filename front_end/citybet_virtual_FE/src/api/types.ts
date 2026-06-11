/** Raw API response shapes from the FastAPI backend. */

export interface ApiSeason {
  season_id: string
  tournament_name: string
  season_status: string
  current_gwk: number
  cum_gwk: number
  cum_teams: number
  created_at?: string
}

export interface ApiCountdown {
  next_match_id: string
  show_at_ms: number
  virtual_clock_ms?: number
  scheduled_start_at_ms?: number | null
  ms_until_kickoff: number
  in_countdown_window: boolean
  countdown_seconds: number
  is_kickoff: boolean
  formatted: string
  /** Backend sends real milliseconds when true (3-min processing countdown). */
  countdown_real_ms?: boolean
}

export interface ApiCarouselItem {
  carousel_id: string
  carousel_step: number
  match_id: string
  season_id: string
  league_name: string
  gameweek: number
  show_at_ms: number
  scheduled_start_at_ms: number | null
  status: string
  has_video: boolean
  is_next?: boolean
  fixture_image_url: string | null
  home_team: { id: string; name: string } | null
  away_team: { id: string; name: string } | null
  countdown: ApiCountdown
}

export interface ApiCarouselResponse {
  mode: 'wall_clock' | 'legacy'
  server_time_ms: number
  queue_interval_sec?: number
  items: ApiCarouselItem[]
  total: number
}

export interface ApiLeague {
  league_name: string
  season_id: string
  tournament_name: string
  season_status: string
  current_gwk: number
  cum_gwk: number
  team_count: number
}

export interface ApiFixture {
  match_id: string
  season_id: string
  gameweek: number
  game_date: string
  game_time: string
  show_at_ms: number
  fixture_image_url: string | null
  status: string
  settled: boolean
  score: string | null
  home_team: { id: string; name: string }
  away_team: { id: string; name: string }
  odds_1x2?: Record<string, number>
  predictions?: unknown
  outcome?: unknown
  has_video?: boolean
  scheduled_start_at_ms?: number | null
  match_sync?: ApiMatchSyncPayload | null
}

export interface ApiTableRow {
  rank: number
  team_id: string
  team_name: string
  league_name: string
  team_rating: number | null
  points: number
  played: number
  wins: number
  draws: number
  losses: number
  goals_scored: number
  goals_conceded: number
  goal_diff: number
  last_5?: string[]
}

export interface ApiTableResponse {
  season_id: string
  tournament_name: string
  current_gwk: number
  table: ApiTableRow[]
}

export interface ApiResult {
  match_id: string
  season_id: string
  gameweek: number
  game_date: string
  show_at_ms: number
  fixture_image_url: string | null
  home_team: string
  away_team: string
  score: string
  outcome: unknown
  video_url: string | null
  video_endpoint: string
  gfr_stats: unknown
}

export interface ApiScorer {
  rank: number
  player_id: string
  player_name: string
  team_id: string
  team_name: string
  role: string | null
  goals: number
  assists: number
  appearances: number
  player_face_url: string | null
}

export interface ApiScorersResponse {
  season_id: string
  tournament_name: string
  scorers: ApiScorer[]
}

export interface ApiMatchGoalEvent {
  side: 'home' | 'away'
  step: number
  video_sec: number
  home_score: number
  away_score: number
}

export interface ApiMatchSyncPayload {
  video_duration_sec: number
  total_steps: number
  goal_events: ApiMatchGoalEvent[]
  final_stats: {
    home_goals: number
    away_goals: number
    score: string
    possession: { home_pct: number; away_pct: number }
    corners: number
    free_kicks: number
    shots_home: number
    shots_away: number
    fouls_home: number
    fouls_away: number
    corners_home: number
    corners_away: number
  }
}

export interface ApiFixtureCard {
  match_id: string
  season_id: string
  gameweek: number
  show_at_ms: number
  virtual_clock_ms: number
  next_show_at_ms: number | null
  status: string
  score: string | null
  fixture_image_url: string | null
  home_team: { id: string; name: string } | null
  away_team: { id: string; name: string } | null
  has_video: boolean
  video_endpoint: string
  scheduled_start_at_ms?: number | null
  match_sync?: ApiMatchSyncPayload | null
}

export interface ApiLiveCard {
  league_name: string
  season_id: string
  virtual_clock_ms: number
  source: string
  fixture: ApiFixtureCard | null
  countdown?: ApiCountdown | null
}
