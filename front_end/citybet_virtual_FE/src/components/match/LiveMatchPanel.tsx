import { isBroadcastOnAir, isFallbackBroadcast } from '../../utils/liveVideo'
import type { LiveMatch } from '../../types'
import { LiveMatchCarousel } from './LiveMatchCarousel'
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

  // Check if all displayed matches are replays (no genuine live broadcast)
  const allFallback = displayMatches.every((m) => isFallbackBroadcast(m))

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3 sm:p-4">
      {allFallback && (
        <div className="flex shrink-0 items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2">
          <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
          <p className="text-[11px] font-medium text-amber-300">
            Live stream returning shortly — playing match replays
          </p>
        </div>
      )}
      <LiveMatchCarousel
        matches={displayMatches}
        activeIndex={safeIndex}
        onIndexChange={onMatchIndexChange}
      />
      <LiveVideoTile key={match.id} match={match} onEnded={onMatchEnded} expanded />
    </div>
  )
}

