import { useMemo } from 'react'
import { useLeague } from '../../context/LeagueContext'
import { getSyncedGameweek, usePlatformData } from '../../context/PlatformDataContext'
import { CarouselMatchCard } from './CarouselMatchCard'
import type { LeagueId, UpcomingMatch } from '../../types'

interface UpcomingGamesCarouselProps {
  onWatchLive?: (league: LeagueId, matchId?: string) => void
}

function gameweekFloor(leagues: { id: LeagueId; gameweek: number }[], league: LeagueId): number {
  return leagues.find((l) => l.id === league)?.gameweek ?? 1
}

/** Legacy fallback filter when backend carousel is unavailable. */
function filterLegacyQueue(
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

/** Backend `/carousel` already orders by carousel_step — preserve that order. */
function orderCarouselQueue(queue: UpcomingMatch[]): UpcomingMatch[] {
  if (queue.some((m) => m.carouselStep != null)) {
    return [...queue].sort((a, b) => (a.carouselStep ?? 0) - (b.carouselStep ?? 0))
  }
  return [...queue].sort(
    (a, b) =>
      (a.scheduledStartAtMs ?? a.showAtMs) - (b.scheduledStartAtMs ?? b.showAtMs),
  )
}

export function UpcomingGamesCarousel({ onWatchLive }: UpcomingGamesCarouselProps) {
  const { selectedLeague, isAllLeagues } = useLeague()
  const { leagues, upcoming: queue, fixtures, results } = usePlatformData()

  const displayGameweek = isAllLeagues
    ? leagues.length > 0
      ? Math.min(...leagues.map((l) => l.gameweek))
      : 1
    : getSyncedGameweek(leagues, fixtures, results, selectedLeague)

  const visibleQueue = useMemo(() => {
    const backendDriven = queue.some((m) => m.carouselStep != null)
    const filtered = backendDriven ? queue : filterLegacyQueue(queue, leagues)
    return orderCarouselQueue(filtered)
  }, [queue, leagues])

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
              key={match.carouselId ?? match.id}
              match={match}
              onWatchLive={onWatchLive}
            />
          ))}
        </div>
      )}
    </section>
  )
}
