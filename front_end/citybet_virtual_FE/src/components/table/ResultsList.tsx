import { useState } from 'react'
import { api } from '../../api/client'
import type { ResultItem } from '../../types'

function parseScore(score: string | undefined): [number, number] {
  const parts = (score ?? '0-0').split('-')
  const home = parseInt(parts[0]?.trim() ?? '0', 10)
  const away = parseInt(parts[1]?.trim() ?? '0', 10)
  return [Number.isNaN(home) ? 0 : home, Number.isNaN(away) ? 0 : away]
}

export function ResultsList({ results }: { results: ResultItem[] }) {
  const [replayId, setReplayId] = useState<string | null>(null)

  if (results.length === 0) {
    return (
      <p className="py-8 text-center text-fluid-sm text-white/40">
        No completed results for this league yet.
      </p>
    )
  }

  return (
    <div className="divide-y divide-white/5">
      {results.map((r) => {
        const [homeG, awayG] = parseScore(r.score)
        const isReplaying = replayId === r.id
        return (
          <div key={r.id} className="py-5">
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 sm:gap-6">
              <p className="truncate text-right text-fluid-sm font-medium text-white">{r.home}</p>
              <div className="flex min-w-[5rem] flex-col items-center">
                <span className="font-mono text-fluid-lg font-bold tabular-nums text-white">
                  {homeG} – {awayG}
                </span>
                <span className="text-fluid-xs text-white/40">GW{r.gameweek}</span>
              </div>
              <p className="truncate text-left text-fluid-sm font-medium text-white">{r.away}</p>
            </div>
            <div className="mt-3 flex justify-center">
              <button
                type="button"
                onClick={() => setReplayId(isReplaying ? null : r.id)}
                className="rounded-lg border border-white/10 px-4 py-1.5 text-fluid-xs font-medium text-brand transition hover:border-brand/40 hover:bg-brand/10"
              >
                {isReplaying ? 'Close replay' : 'Watch replay'}
              </button>
            </div>
            {isReplaying && (
              <div className="mt-3 overflow-hidden rounded-lg border border-white/10 bg-black">
                <video
                  key={r.id}
                  src={api.videoUrl(r.id)}
                  controls
                  playsInline
                  preload="auto"
                  className="aspect-video w-full object-contain"
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
