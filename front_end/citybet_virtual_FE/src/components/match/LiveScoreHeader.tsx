import { useEffect, useRef, useState } from 'react'

interface LiveScoreHeaderProps {
  league: string
  home: string
  away: string
  homeScore: number
  awayScore: number
  matchMinute: number
  /** When true, shows a Replay badge instead of Live indicator. */
  isReplay?: boolean
}

export function LiveScoreHeader({
  league,
  home,
  away,
  homeScore,
  awayScore,
  matchMinute,
  isReplay = false,
}: LiveScoreHeaderProps) {
  const prevScore = useRef(`${homeScore}-${awayScore}`)
  const [pulse, setPulse] = useState(false)

  useEffect(() => {
    const next = `${homeScore}-${awayScore}`
    if (next !== prevScore.current) {
      prevScore.current = next
      setPulse(true)
      const t = window.setTimeout(() => setPulse(false), 700)
      return () => window.clearTimeout(t)
    }
  }, [homeScore, awayScore])

  return (
    <header className="shrink-0 rounded-xl border border-white/10 bg-gradient-to-b from-white/[0.06] to-transparent px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="truncate text-fluid-xs font-semibold uppercase tracking-wider text-brand">
          {league}
        </p>
        <div className="flex items-center gap-2">
          {!isReplay && (
            <span className="font-mono text-fluid-xs tabular-nums text-white/50">{matchMinute}'</span>
          )}
          {isReplay ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/20 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-400">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              Replay
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-brand/20 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-brand">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand" />
              </span>
              Live
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <p className="truncate text-right text-fluid-sm font-semibold text-white sm:text-fluid-base">
          {home}
        </p>
        <div
          className={`min-w-[5.5rem] rounded-lg border border-white/10 bg-black/40 px-4 py-2 text-center transition-transform duration-300 ${
            pulse ? 'scale-110 border-brand/40 shadow-[0_0_24px_rgba(34,197,94,0.25)]' : ''
          }`}
        >
          <span className="font-mono text-fluid-xl font-bold tabular-nums text-white sm:text-2xl">
            {homeScore}
            <span className="mx-2 text-white/30">–</span>
            {awayScore}
          </span>
        </div>
        <p className="truncate text-left text-fluid-sm font-semibold text-white sm:text-fluid-base">
          {away}
        </p>
      </div>
    </header>
  )
}
