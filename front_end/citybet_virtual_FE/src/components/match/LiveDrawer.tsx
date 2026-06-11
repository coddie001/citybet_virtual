import { useEffect, useRef, useState } from 'react'
import type { LeagueId, LiveMatch } from '../../types'
import { LIVE_DRAWER_WIDTH } from './liveDrawerLayout'
import { LiveMatchPanel } from './LiveMatchPanel'

interface LiveDrawerProps {
  matches: LiveMatch[]
  open: boolean
  onOpenChange: (open: boolean) => void
  focusLeague?: LeagueId
  focusMatchId?: string
  onMatchEnded?: (matchId: string) => void
}

export function LiveDrawer({
  matches,
  open,
  onOpenChange,
  focusLeague,
  focusMatchId,
  onMatchEnded,
}: LiveDrawerProps) {
  const [index, setIndex] = useState(0)
  const userNavigatedRef = useRef(false)

  useEffect(() => {
    userNavigatedRef.current = false
  }, [focusMatchId])

  useEffect(() => {
    if (userNavigatedRef.current) return
    if (focusMatchId) {
      const idx = matches.findIndex((m) => m.id === focusMatchId)
      if (idx >= 0) setIndex(idx)
      return
    }
    if (focusLeague && focusLeague !== 'ALL') {
      const idx = matches.findIndex((m) => m.league === focusLeague)
      if (idx >= 0) setIndex(idx)
    }
  }, [focusMatchId, focusLeague, matches])

  useEffect(() => {
    setIndex((i) => {
      if (matches.length === 0) return 0
      return Math.min(Math.max(0, i), matches.length - 1)
    })
  }, [matches.length])

  const handleIndexChange = (next: number) => {
    userNavigatedRef.current = true
    setIndex(next)
  }

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => onOpenChange(true)}
          className="live-drawer-tab fixed right-0 top-1/2 z-50 flex -translate-y-1/2 flex-col items-center gap-2 rounded-l-xl border border-r-0 border-white/10 bg-surface-panel py-5 pl-2 pr-2.5 shadow-[-4px_0_24px_rgba(0,0,0,0.4)] transition-colors hover:border-brand/30 hover:bg-surface-panel/90"
          aria-label="Open live matches"
        >
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-brand" />
          </span>
          <span
            className="text-[10px] font-bold uppercase tracking-[0.2em] text-brand"
            style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
          >
            Live
          </span>
          <span className="text-sm text-white/50" aria-hidden>
            ‹
          </span>
        </button>
      )}

      {open && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px] lg:hidden"
          onClick={() => onOpenChange(false)}
          aria-label="Close live panel"
        />
      )}

      <aside
        className={`live-drawer fixed bottom-0 right-0 top-[var(--header-height)] z-50 flex transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ width: LIVE_DRAWER_WIDTH }}
        aria-hidden={!open}
      >
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          className="flex w-8 shrink-0 items-center justify-center border-r border-white/10 bg-surface-raised/90 text-white/50 transition-colors hover:bg-white/5 hover:text-white"
          aria-label="Close live panel"
        >
          ›
        </button>

        <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-y-auto border-l border-white/10 bg-surface-panel/95 backdrop-blur-md">
          <LiveMatchPanel
            matches={matches}
            matchIndex={index}
            onMatchIndexChange={handleIndexChange}
            onMatchEnded={onMatchEnded}
          />
        </div>
      </aside>
    </>
  )
}
