import type { FixtureItem, LeagueId } from '../../types'

interface FixturesListProps {
  fixtures: FixtureItem[]
  onWatchLive?: (league: LeagueId, matchId?: string) => void
}

export function FixturesList({ fixtures, onWatchLive }: FixturesListProps) {
  return (
    <div className="crossfade-enter divide-y divide-white/5">
      {fixtures.map((f) => {
        const onAir = f.status === 'live' && f.hasVideo === true
        const isPreparing = f.status === 'preparing' || (f.status === 'live' && !onAir)
        const clickable = onAir && Boolean(onWatchLive)

        return (
          <div
            key={f.id}
            className={`flex flex-wrap items-center gap-4 py-4 transition-colors sm:flex-nowrap ${
              clickable
                ? 'cursor-pointer hover:bg-brand/5'
                : 'hover:bg-white/[0.02]'
            }`}
            onClick={clickable ? () => onWatchLive!(f.league, f.id) : undefined}
            onKeyDown={
              clickable
                ? (e) => {
                    if (e.key === 'Enter' || e.key === ' ') onWatchLive!(f.league, f.id)
                  }
                : undefined
            }
            role={clickable ? 'button' : undefined}
            tabIndex={clickable ? 0 : undefined}
          >
            {f.imageUrl && (
              <img
                src={f.imageUrl}
                alt=""
                className="h-14 w-20 shrink-0 rounded-lg object-cover"
              />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-fluid-sm font-semibold text-white">
                {f.home} <span className="text-white/40">vs</span> {f.away}
              </p>
              <p className="mt-0.5 text-fluid-xs text-white/40">
                GW{f.gameweek} · {f.date} · {f.time}
                {onAir && (
                  <span className="ml-2 text-brand">· Watch live</span>
                )}
                {isPreparing && (
                  <span className="ml-2 text-white/40">· Preparing</span>
                )}
              </p>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-fluid-xs font-semibold uppercase ${
                onAir
                  ? 'bg-brand/20 text-brand'
                  : isPreparing
                    ? 'bg-white/10 text-white/50'
                  : f.status === 'completed'
                    ? 'bg-white/10 text-white/60'
                    : 'bg-white/5 text-white/50'
              }`}
            >
              {onAir ? 'live' : isPreparing ? 'preparing' : f.status}
            </span>
          </div>
        )
      })}
    </div>
  )
}
