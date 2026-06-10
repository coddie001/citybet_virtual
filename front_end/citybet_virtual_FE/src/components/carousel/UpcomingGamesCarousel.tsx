import { useMemo } from 'react'
import { useFilteredData } from '../../hooks/useFilteredData'
import { useLeague } from '../../context/LeagueContext'
import { getSyncedGameweek, usePlatformData } from '../../context/PlatformDataContext'
import { CarouselMatchCard } from './CarouselMatchCard'
import type { LeagueId, UpcomingMatch } from '../../types'

interface UpcomingGamesCarouselProps {
  onWatchLive?: (league: LeagueId, matchId?: string) => void
}

function sortByKickoff<T extends { showAtMs: number }>(items: T[]): T[] {
  return [...items].sort((a, b) => a.showAtMs - b.showAtMs)
}

function gameweekFloor(leagues: { id: LeagueId; gameweek: number }[], league: LeagueId): number {
  return leagues.find((l) => l.id === league)?.gameweek ?? 1
}

function filterCarouselQueue(
  queue: UpcomingMatch[],
  leagues: { id: LeagueId; gameweek: number }[],
): UpcomingMatch[] {
  return queue.filter(
    (match) =>
      match.status === 'live' ||
      match.status === 'preparing' ||
      (match.status !== 'completed' &&
        match.gameweek >= gameweekFloor(leagues, match.league)),
  )
}

export function UpcomingGamesCarousel({ onWatchLive }: UpcomingGamesCarouselProps) {
  const { selectedLeague, isAllLeagues } = useLeague()
  const {
    leagues,
    countdownByLeague,
    clocksByLeague,
    fixtures,
    results,
  } = usePlatformData()
  const { upcoming: queue } = useFilteredData(selectedLeague)

  /** Carousel is independent of table league rotation — never use useLeagueRotation here. */
  const displayGameweek = isAllLeagues
    ? leagues.length > 0
      ? Math.min(...leagues.map((l) => l.gameweek))
      : 1
    : getSyncedGameweek(leagues, fixtures, results, selectedLeague)

  const visibleQueue = useMemo(
    () => sortByKickoff(filterCarouselQueue(queue, leagues)),
    [queue, leagues],
  )

  const clockForMatch = (league: LeagueId): number | undefined => {
    if (league !== 'ALL' && clocksByLeague[league] != null) {
      return clocksByLeague[league]
    }
    return undefined
  }

  return (
    <section className="animate-slide-up">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-fluid-lg font-semibold text-white">Upcoming Games</h2>
        <span className="text-fluid-sm text-white/50">
          Gameweek <span className="font-semibold text-white">{displayGameweek}</span>
        </span>
      </div>

      {visibleQueue.length === 0 ? (
        <p className="text-fluid-sm text-white/40">No upcoming fixtures for this league.</p>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2 sm:gap-5">
          {visibleQueue.map((match) => (
            <CarouselMatchCard
              key={match.id}
              match={match}
              virtualClockMs={clockForMatch(match.league)}
              apiCountdown={
                countdownByLeague[match.league]?.next_match_id === match.id
                  ? countdownByLeague[match.league]
                  : null
              }
              onWatchLive={onWatchLive}
            />
          ))}
        </div>
      )}
    </section>
  )
}
