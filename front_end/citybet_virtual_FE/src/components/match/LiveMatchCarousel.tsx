import type { LiveMatch } from '../../types'
import { isFallbackBroadcast } from '../../utils/liveVideo'

interface LiveMatchCarouselProps {
  matches: LiveMatch[]
  activeIndex: number
  onIndexChange: (index: number) => void
}

export function LiveMatchCarousel({
  matches,
  activeIndex,
  onIndexChange,
}: LiveMatchCarouselProps) {
  if (matches.length <= 1) return null

  const prev = () => onIndexChange((activeIndex - 1 + matches.length) % matches.length)
  const next = () => onIndexChange((activeIndex + 1) % matches.length)
  const allReplays = matches.every((m) => isFallbackBroadcast(m))

  return (
    <nav
      className="mb-3 shrink-0 rounded-xl border border-white/10 bg-black/20 p-2"
      aria-label="Live broadcasts"
    >
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={prev}
          className="rounded-lg border border-white/10 px-2.5 py-1.5 text-sm text-white/60 transition hover:bg-white/5 hover:text-white"
          aria-label="Previous broadcast"
        >
          ‹
        </button>

        <div className="flex min-w-0 flex-1 flex-col items-center gap-1.5">
          <div className="flex gap-1.5">
            {matches.map((m, i) => (
              <button
                key={m.id}
                type="button"
                onClick={() => onIndexChange(i)}
                className={`h-1.5 rounded-full transition-all ${
                  i === activeIndex ? 'w-7 bg-brand' : 'w-1.5 bg-white/20 hover:bg-white/35'
                }`}
                aria-label={`${m.league}: ${m.home} vs ${m.away}`}
                aria-current={i === activeIndex ? 'true' : undefined}
              />
            ))}
          </div>
          <p className="w-full truncate text-center text-[11px] text-white/70">
            <span className="font-semibold text-brand">{matches[activeIndex]?.league}</span>
            <span className="text-white/40"> · </span>
            {matches[activeIndex]?.home}
            <span className="text-white/40"> vs </span>
            {matches[activeIndex]?.away}
          </p>
        </div>

        <button
          type="button"
          onClick={next}
          className="rounded-lg border border-white/10 px-2.5 py-1.5 text-sm text-white/60 transition hover:bg-white/5 hover:text-white"
          aria-label="Next broadcast"
        >
          ›
        </button>
      </div>

      <p className="mt-1.5 text-center text-[10px] tabular-nums text-white/35">
        {activeIndex + 1} / {matches.length} {allReplays ? 'replays' : 'live'}
      </p>
    </nav>
  )
}
