import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { AppShell } from '../components/layout/AppShell'
import { Header } from '../components/layout/Header'
import { Footer } from '../components/layout/Footer'
import { MainContentWell, MainSection } from '../components/layout/MainContentWell'
import { PromoBanner } from '../components/layout/PromoBanner'
import { UpcomingGamesCarousel } from '../components/carousel/UpcomingGamesCarousel'
import { DataPanel } from '../components/table/DataPanel'
import { LiveDrawer } from '../components/match/LiveDrawer'
import { LIVE_DRAWER_WIDTH } from '../components/match/liveDrawerLayout'
import { useLeague } from '../context/LeagueContext'
import { useFilteredData } from '../hooks/useFilteredData'
import { usePlatformData } from '../context/PlatformDataContext'
import { isBroadcastOnAir } from '../utils/liveVideo'
import type { LeagueId, LiveMatch } from '../types'

const MAX_LIVE_DRAWER_MATCHES = 8

function kickoffSortKey(m: LiveMatch): number {
  return m.scheduledStartAtMs ?? m.showAtMs ?? 0
}

export function HomePage() {
  const { selectedLeague } = useLeague()
  const { error, liveMatches: platformLive } = usePlatformData()
  useFilteredData(selectedLeague)
  const [liveOpen, setLiveOpen] = useState(false)
  const [focusMatchId, setFocusMatchId] = useState<string | undefined>()
  const liveDismissedRef = useRef(false)

  /** Stay on-air until backend marks completed (10-min window) — not when video ends.
   *  Genuinely live games first (kick-off order), then replays newest-first, so the
   *  panel shows the last 8 completed games that have a saved video. */
  const liveMatches = useMemo(() => {
    const onAir = platformLive.filter(isBroadcastOnAir)
    const live = onAir
      .filter((m) => !m.isFallback)
      .sort((a, b) => kickoffSortKey(a) - kickoffSortKey(b))
    const replays = onAir
      .filter((m) => m.isFallback)
      .sort((a, b) => kickoffSortKey(b) - kickoffSortKey(a))
    return [...live, ...replays].slice(0, MAX_LIVE_DRAWER_MATCHES)
  }, [platformLive])

  useEffect(() => {
    if (liveMatches.length === 0) {
      setLiveOpen(false)
      return
    }
    if (liveDismissedRef.current) return
    setLiveOpen(true)
    setFocusMatchId((prev) => {
      if (prev && liveMatches.some((m) => m.id === prev)) return prev
      return liveMatches[0]?.id
    })
  }, [liveMatches])

  const handleWatchLive = useCallback(
    (league: LeagueId, matchId?: string) => {
      const candidates = platformLive.filter(isBroadcastOnAir)
      const hit =
        (matchId && candidates.find((m) => m.id === matchId && isBroadcastOnAir(m))) ||
        (league !== 'ALL' &&
          candidates.find((m) => m.league === league && isBroadcastOnAir(m)))
      if (!hit || !isBroadcastOnAir(hit)) return
      liveDismissedRef.current = false
      setFocusMatchId(hit.id)
      setLiveOpen(true)
    },
    [platformLive],
  )

  const handleLiveOpenChange = useCallback((open: boolean) => {
    setLiveOpen(open)
    if (!open) liveDismissedRef.current = true
  }, [])

  return (
    <AppShell header={<Header />} footer={<Footer />}>
      <div className="flex flex-1">
        <main
          className="min-w-0 flex-1 transition-[margin] duration-300 ease-out max-lg:!mr-0"
          style={
            liveOpen ? ({ marginRight: LIVE_DRAWER_WIDTH } as CSSProperties) : undefined
          }
        >
          <MainContentWell>
            {error && (
              <MainSection>
                <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-fluid-sm text-red-200">
                  {error}
                </p>
              </MainSection>
            )}
            {/* Carousel: always rendered — shows skeletons until data arrives */}
            <MainSection>
              <UpcomingGamesCarousel onWatchLive={handleWatchLive} />
            </MainSection>
            {/* DataPanel: always rendered — shows skeleton table until details load */}
            <MainSection className="!p-0">
              <DataPanel embedded onWatchLive={handleWatchLive} />
            </MainSection>
            <MainSection className="!py-0 !pb-6 sm:!pb-8">
              <PromoBanner />
            </MainSection>
          </MainContentWell>
        </main>

        <LiveDrawer
          matches={liveMatches}
          open={liveOpen}
          onOpenChange={handleLiveOpenChange}
          focusLeague={selectedLeague}
          focusMatchId={focusMatchId}
        />
      </div>
    </AppShell>
  )
}
