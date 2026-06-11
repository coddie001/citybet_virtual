import type { UpcomingMatch } from '../../types'

interface MatchCardProps {
  match: UpcomingMatch
  countdown?: string
  countdownLabel?: string
  showCountdown?: boolean
  showLive?: boolean
  showUpNext?: boolean
  preloadVideoUrl?: string
  onWatchLive?: () => void
}

export function MatchCard({
  match,
  countdown,
  countdownLabel = 'Game starts',
  showCountdown,
  showLive,
  showUpNext,
  preloadVideoUrl,
  onWatchLive,
}: MatchCardProps) {
  return (
    <article
      className={`group flex w-[clamp(140px,13vw,210px)] shrink-0 flex-col gap-2${onWatchLive ? ' cursor-pointer' : ''}`}
      onClick={onWatchLive}
      onKeyDown={
        onWatchLive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') onWatchLive()
            }
          : undefined
      }
      role={onWatchLive ? 'button' : undefined}
      tabIndex={onWatchLive ? 0 : undefined}
    >
      <div className="relative aspect-[5/7] overflow-hidden rounded-xl border border-white/5 shadow-md transition-transform duration-300 group-hover:scale-[1.01]">
        <img
          src={match.imageUrl}
          alt={`${match.home} vs ${match.away}`}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
        {showCountdown && countdown && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 backdrop-blur-[2px]">
            <span className="text-fluid-xs font-medium uppercase tracking-widest text-white/70">
              {countdownLabel}
            </span>
            <span className="mt-1 font-mono text-fluid-3xl font-bold tabular-nums text-white">
              {countdown}
            </span>
          </div>
        )}
        {showUpNext && !showLive && !showCountdown && (
          <span className="absolute left-3 top-3 rounded-full bg-white/90 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-black">
            Up Next
          </span>
        )}
        {showLive && !showCountdown && (
          <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-brand/90 px-2.5 py-1 text-[10px] font-bold uppercase text-black">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-black" />
            Live
          </span>
        )}
        {preloadVideoUrl && (
          <video
            preload="auto"
            muted
            playsInline
            src={preloadVideoUrl}
            className="pointer-events-none absolute h-0 w-0 opacity-0"
            aria-hidden
          />
        )}
      </div>
      <p className="text-center text-fluid-sm font-semibold tracking-wide text-white/90">
        {match.homeAbbr} <span className="text-white/40">vs</span> {match.awayAbbr}
      </p>
    </article>
  )
}
