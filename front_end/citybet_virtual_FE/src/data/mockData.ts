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

const IMG = (path: string) => `/img/${path}`

export const LEAGUES: LeagueMeta[] = [
  { id: 'Premier League', name: 'Premier League', seasonId: 'pl-2026', gameweek: 10, totalGameweeks: 38 },
  { id: 'La Liga', name: 'La Liga', seasonId: 'laliga-2026', gameweek: 10, totalGameweeks: 38 },
  { id: 'Serie A', name: 'Serie A', seasonId: 'seriea-2026', gameweek: 10, totalGameweeks: 38 },
  { id: 'Bundesliga', name: 'Bundesliga', seasonId: 'bundesliga-2026', gameweek: 10, totalGameweeks: 34 },
]

const form = (results: ('W' | 'D' | 'L')[]) => results

export const TABLES: Record<Exclude<LeagueId, 'ALL'>, TableRow[]> = {
  'Premier League': [
    { rank: 1, club: 'Liverpool', mp: 10, w: 8, d: 1, l: 1, gf: 18, ga: 7, pts: 25, last5: form(['W', 'W', 'W', 'D', 'W']) },
    { rank: 2, club: 'Arsenal', mp: 10, w: 7, d: 2, l: 1, gf: 20, ga: 7, pts: 23, last5: form(['W', 'W', 'D', 'W', 'L']) },
    { rank: 3, club: 'Manchester City', mp: 10, w: 6, d: 2, l: 2, gf: 19, ga: 11, pts: 20, last5: form(['W', 'L', 'W', 'W', 'D']) },
    { rank: 4, club: 'Chelsea', mp: 10, w: 5, d: 3, l: 2, gf: 17, ga: 12, pts: 18, last5: form(['D', 'W', 'W', 'L', 'W']) },
    { rank: 5, club: 'Aston Villa', mp: 10, w: 5, d: 2, l: 3, gf: 14, ga: 13, pts: 17, last5: form(['W', 'L', 'W', 'D', 'W']) },
    { rank: 6, club: 'Tottenham Hotspur', mp: 10, w: 4, d: 3, l: 3, gf: 15, ga: 14, pts: 15, last5: form(['L', 'W', 'D', 'W', 'L']) },
    { rank: 7, club: 'Manchester United', mp: 10, w: 4, d: 2, l: 4, gf: 12, ga: 14, pts: 14, last5: form(['L', 'L', 'W', 'D', 'W']) },
    { rank: 8, club: 'Newcastle United', mp: 10, w: 3, d: 4, l: 3, gf: 11, ga: 11, pts: 13, last5: form(['D', 'D', 'L', 'W', 'D']) },
  ],
  'La Liga': [
    { rank: 1, club: 'Real Madrid', mp: 10, w: 8, d: 1, l: 1, gf: 22, ga: 8, pts: 25, last5: form(['W', 'W', 'W', 'W', 'D']) },
    { rank: 2, club: 'Barcelona', mp: 10, w: 7, d: 2, l: 1, gf: 21, ga: 9, pts: 23, last5: form(['W', 'D', 'W', 'W', 'W']) },
    { rank: 3, club: 'Atletico Madrid', mp: 10, w: 6, d: 3, l: 1, gf: 16, ga: 8, pts: 21, last5: form(['D', 'W', 'W', 'D', 'W']) },
    { rank: 4, club: 'Girona', mp: 10, w: 5, d: 2, l: 3, gf: 15, ga: 12, pts: 17, last5: form(['W', 'L', 'W', 'L', 'W']) },
  ],
  'Serie A': [
    { rank: 1, club: 'Inter Milan', mp: 10, w: 8, d: 1, l: 1, gf: 19, ga: 6, pts: 25, last5: form(['W', 'W', 'W', 'D', 'W']) },
    { rank: 2, club: 'AC Milan', mp: 10, w: 6, d: 3, l: 1, gf: 17, ga: 9, pts: 21, last5: form(['W', 'D', 'W', 'W', 'D']) },
    { rank: 3, club: 'Juventus', mp: 10, w: 5, d: 4, l: 1, gf: 14, ga: 8, pts: 19, last5: form(['D', 'W', 'D', 'W', 'D']) },
    { rank: 4, club: 'Napoli', mp: 10, w: 5, d: 2, l: 3, gf: 13, ga: 11, pts: 17, last5: form(['L', 'W', 'W', 'L', 'W']) },
  ],
  'Bundesliga': [
    { rank: 1, club: 'Bayern Munich', mp: 10, w: 8, d: 1, l: 1, gf: 24, ga: 7, pts: 25, last5: form(['W', 'W', 'W', 'D', 'W']) },
    { rank: 2, club: 'Bayer Leverkusen', mp: 10, w: 7, d: 2, l: 1, gf: 20, ga: 9, pts: 23, last5: form(['W', 'D', 'W', 'W', 'W']) },
    { rank: 3, club: 'Borussia Dortmund', mp: 10, w: 6, d: 2, l: 2, gf: 18, ga: 11, pts: 20, last5: form(['W', 'L', 'W', 'D', 'W']) },
    { rank: 4, club: 'RB Leipzig', mp: 10, w: 5, d: 3, l: 2, gf: 16, ga: 12, pts: 18, last5: form(['D', 'W', 'L', 'W', 'D']) },
  ],
}

export const UPCOMING: UpcomingMatch[] = [
  { id: 'm1', league: 'Premier League', home: 'Manchester City', homeAbbr: 'MCI', away: 'Sunderland', awayAbbr: 'SUN', imageUrl: IMG('fixture_imgs/HIdxJdRXgAAVkvJ.jpg'), showAtMs: 0, gameweek: 10, status: 'upcoming', isNext: true },
  { id: 'm2', league: 'Premier League', home: 'Crystal Palace', homeAbbr: 'CRY', away: 'Liverpool', awayAbbr: 'LIV', imageUrl: IMG('fixture_imgs/P2024-04-14-Liverpool_Crystal_Palace-54-600x400.jpg'), showAtMs: 360000, gameweek: 10, status: 'upcoming' },
  { id: 'm3', league: 'Premier League', home: 'Aston Villa', homeAbbr: 'AVL', away: 'Manchester United', awayAbbr: 'MUN', imageUrl: IMG('fixture_imgs/2267.avif'), showAtMs: 720000, gameweek: 10, status: 'upcoming' },
  { id: 'm4', league: 'La Liga', home: 'Real Madrid', homeAbbr: 'RMA', away: 'Sevilla', awayAbbr: 'SEV', imageUrl: IMG('fixture_imgs/HIdxJdRXgAAVkvJ.jpg'), showAtMs: 1080000, gameweek: 10, status: 'upcoming' },
  { id: 'm5', league: 'Serie A', home: 'Inter Milan', homeAbbr: 'INT', away: 'Roma', awayAbbr: 'ROM', imageUrl: IMG('fixture_imgs/2267.avif'), showAtMs: 1440000, gameweek: 10, status: 'upcoming' },
  { id: 'm6', league: 'Bundesliga', home: 'Bayern Munich', homeAbbr: 'BAY', away: 'Dortmund', awayAbbr: 'BVB', imageUrl: IMG('fixture_imgs/HIdxJdRXgAAVkvJ.jpg'), showAtMs: 1800000, gameweek: 10, status: 'upcoming' },
]

export const FIXTURES: FixtureItem[] = UPCOMING.map((m, i) => ({
  id: m.id,
  league: m.league,
  gameweek: 10,
  home: m.home,
  away: m.away,
  date: '2026-06-08',
  time: `${12 + i}:30`,
  status: m.status,
  imageUrl: m.imageUrl,
}))

export const RESULTS: ResultItem[] = [
  { id: 'r1', league: 'Premier League', gameweek: 9, home: 'Arsenal', away: 'Fulham', score: '3-0', date: '2026-06-07' },
  { id: 'r2', league: 'Premier League', gameweek: 9, home: 'Liverpool', away: 'Everton', score: '2-1', date: '2026-06-07' },
  { id: 'r3', league: 'La Liga', gameweek: 9, home: 'Barcelona', away: 'Valencia', score: '1-1', date: '2026-06-07' },
  { id: 'r4', league: 'Serie A', gameweek: 9, home: 'Juventus', away: 'Lecce', score: '2-0', date: '2026-06-07' },
]

export const SCORERS: Record<Exclude<LeagueId, 'ALL'>, ScorerRow[]> = {
  'Premier League': [
    { rank: 1, player: 'Erling Haaland', club: 'Manchester City', goals: 12, appearances: 10 },
    { rank: 2, player: 'Mohamed Salah', club: 'Liverpool', goals: 9, appearances: 10 },
    { rank: 3, player: 'Bukayo Saka', club: 'Arsenal', goals: 7, appearances: 10 },
  ],
  'La Liga': [
    { rank: 1, player: 'Robert Lewandowski', club: 'Barcelona', goals: 11, appearances: 10 },
    { rank: 2, player: 'Kylian Mbappé', club: 'Real Madrid', goals: 10, appearances: 10 },
  ],
  'Serie A': [
    { rank: 1, player: 'Lautaro Martínez', club: 'Inter Milan', goals: 10, appearances: 10 },
    { rank: 2, player: 'Dusan Vlahovic', club: 'Juventus', goals: 8, appearances: 10 },
  ],
  'Bundesliga': [
    { rank: 1, player: 'Harry Kane', club: 'Bayern Munich', goals: 13, appearances: 10 },
    { rank: 2, player: 'Serhou Guirassy', club: 'Borussia Dortmund', goals: 9, appearances: 10 },
  ],
}

export const LIVE_MATCHES: LiveMatch[] = [
  {
    id: 'live1',
    league: 'Premier League',
    home: 'Arsenal',
    away: 'Fulham',
    homeScore: 3,
    awayScore: 0,
    status: 'live',
    possession: [58, 42],
    shots: [14, 6],
    fouls: [8, 11],
    corners: [7, 2],
  },
  {
    id: 'live2',
    league: 'La Liga',
    home: 'Real Madrid',
    away: 'Getafe',
    homeScore: 1,
    awayScore: 1,
    status: 'live',
    possession: [62, 38],
    shots: [11, 5],
    fouls: [6, 9],
    corners: [5, 3],
  },
  {
    id: 'live3',
    league: 'Serie A',
    home: 'Napoli',
    away: 'Lazio',
    homeScore: 2,
    awayScore: 1,
    status: 'live',
    possession: [51, 49],
    shots: [9, 8],
    fouls: [10, 10],
    corners: [4, 4],
  },
  {
    id: 'live4',
    league: 'Bundesliga',
    home: 'Bayern Munich',
    away: 'Freiburg',
    homeScore: 2,
    awayScore: 0,
    status: 'live',
    possession: [65, 35],
    shots: [16, 4],
    fouls: [5, 12],
    corners: [8, 1],
  },
  {
    id: 'live5',
    league: 'Premier League',
    home: 'Chelsea',
    away: 'Brighton',
    homeScore: 0,
    awayScore: 0,
    status: 'live',
    possession: [47, 53],
    shots: [5, 6],
    fouls: [7, 6],
    corners: [3, 4],
  },
]

export const COUNTDOWN_SECONDS = 180 // 3 minutes

export function getGameweekForLeague(league: LeagueId): number {
  if (league === 'ALL') return 10
  return LEAGUES.find((l) => l.id === league)?.gameweek ?? 10
}
