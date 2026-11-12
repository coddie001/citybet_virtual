import { useMemo } from 'react'
import { CAROUSEL_LIMIT } from '../../context/PlatformDataContext'
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

/** Number of cards rendered eagerly (and as skeletons) for a fast first paint. */
const EAGER_CARDS = 4 // retained for eager prop usage

/** Skeleton cards — same structure/sizing as MatchCard so there's no layout shift. */
function CarouselSkeleton({ count = EAGER_CARDS }: { count?: number }) {
  return (
    <div className="flex gap-4 overflow-x-hidden pb-2 sm:gap-5" aria-busy="true">
      {Array.from({ length: count }).map((_, i) => (
        <article key={i} className="flex w-[clamp(140px,13vw,210px)] shrink-0 flex-col gap-2">
          <div className="relative aspect-[5/7] animate-pulse overflow-hidden rounded-xl border border-white/5 bg-white/[0.07] shadow-md">
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent" />
          </div>
          <div className="mx-auto h-4 w-2/3 animate-pulse rounded bg-white/[0.07]" />
        </article>
      ))}
    </div>
  )
}

export function UpcomingGamesCarousel({ onWatchLive }: UpcomingGamesCarouselProps) {
  const { selectedLeague, isAllLeagues } = useLeague()
  const { leagues, upcoming: queue, fixtures, results, carouselReady } = usePlatformData()

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
        {/* Title always visible */}
        <h2 className="text-fluid-lg font-semibold text-white">Upcoming Games</h2>
        <span className="text-fluid-sm text-white/50">
          {carouselReady ? (
            <>
              Gameweek <span className="font-semibold text-white">{displayGameweek}</span>
            </>
          ) : (
            <span className="inline-block h-4 w-20 animate-pulse rounded bg-white/[0.07] align-middle" />
          )}
        </span>
      </div>

      {/* Show skeletons until real cards exist — never an empty-state message */}
      {!carouselReady || visibleQueue.length === 0 ? (
        <CarouselSkeleton count={CAROUSEL_LIMIT} />
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2 sm:gap-5">
          {visibleQueue.map((match, i) => (
            <CarouselMatchCard
              key={match.carouselId ?? match.id}
              match={match}
              eager={i < EAGER_CARDS}
              onWatchLive={onWatchLive}
            />
          ))}
        </div>
      )}
    </section>
  )
}
