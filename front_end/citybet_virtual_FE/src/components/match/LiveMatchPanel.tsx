import { isBroadcastOnAir } from '../../utils/liveVideo'
import type { LiveMatch } from '../../types'
import { LiveVideoTile } from './LiveVideoTile'

interface LiveMatchPanelProps {
  matches: LiveMatch[]
  matchIndex: number
  onMatchIndexChange: (index: number) => void
  onMatchEnded?: (matchId: string) => void
}

export function LiveMatchPanel({
  matches,
  matchIndex,
  onMatchIndexChange,
  onMatchEnded,
}: LiveMatchPanelProps) {
  const displayMatches = matches.filter((m) => isBroadcastOnAir(m))

  if (displayMatches.length === 0) {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center p-6 text-center">
        <p className="text-fluid-sm text-white/40">
          No live broadcast right now — a match joins when its video is ready
        </p>
      </div>
    )
  }

  const safeIndex =
    matchIndex >= 0 && matchIndex < displayMatches.length ? matchIndex : 0
  const match = displayMatches[safeIndex] ?? displayMatches[0]
  const canNavigate = displayMatches.length > 1

  return (
    <div className="flex h-full min-h-0 flex-col p-3 sm:p-4">
      {canNavigate && (
        <div className="mb-3 flex shrink-0 items-center justify-center gap-3">
          <button
            type="button"
            onClick={() =>
              onMatchIndexChange((safeIndex - 1 + displayMatches.length) % displayMatches.length)
            }
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-white/60 transition hover:bg-white/5 hover:text-white"
            aria-label="Previous match"
          >
            ‹
          </button>
          <div className="flex gap-1.5">
            {displayMatches.map((m, i) => (
              <button
                key={m.id}
                type="button"
                onClick={() => onMatchIndexChange(i)}
                className={`h-1.5 rounded-full transition-all ${
                  i === safeIndex ? 'w-6 bg-brand' : 'w-1.5 bg-white/20'
                }`}
                aria-label={`Match ${i + 1}`}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() =>
              onMatchIndexChange((safeIndex + 1) % displayMatches.length)
            }
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-white/60 transition hover:bg-white/5 hover:text-white"
            aria-label="Next match"
          >
            ›
          </button>
        </div>
      )}
      <LiveVideoTile match={match} onEnded={onMatchEnded} expanded />
    </div>
  )
}
