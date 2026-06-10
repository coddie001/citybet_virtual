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
import { leagueSortIndex } from '../constants/leagues'
import { useLeague } from '../context/LeagueContext'
import { useFilteredData } from '../hooks/useFilteredData'
import { usePlatformData } from '../context/PlatformDataContext'
import { isBroadcastOnAir } from '../utils/liveVideo'
import type { LeagueId, LiveMatch } from '../types'

const MAX_LIVE_DRAWER_MATCHES = 4

export function HomePage() {
  const { selectedLeague } = useLeague()
  const { carouselReady, error, liveMatches: platformLive } = usePlatformData()
  useFilteredData(selectedLeague)
  const [liveOpen, setLiveOpen] = useState(false)
  const [focusMatchId, setFocusMatchId] = useState<string | undefined>()
  const [finishedIds, setFinishedIds] = useState<Set<string>>(() => new Set())
  const liveDismissedRef = useRef(false)

  /** Global broadcast drawer — all leagues, video-ready only (not filtered by selected tab). */
  const liveMatches = useMemo(() => {
    const active = platformLive.filter(
      (m) => isBroadcastOnAir(m) && !finishedIds.has(m.id),
    )
    const byLeague = new Map<string, LiveMatch>()
    for (const m of active.sort(
      (a, b) => leagueSortIndex(a.league) - leagueSortIndex(b.league),
    )) {
      if (!byLeague.has(m.league)) byLeague.set(m.league, m)
    }
    return [...byLeague.values()].slice(0, MAX_LIVE_DRAWER_MATCHES)
  }, [platformLive, finishedIds])

  useEffect(() => {
    setFinishedIds((prev) => {
      const onAir = new Set(platformLive.filter(isBroadcastOnAir).map((m) => m.id))
      const pruned = new Set([...prev].filter((id) => onAir.has(id)))
      return pruned.size === prev.size ? prev : pruned
    })
  }, [platformLive])

  useEffect(() => {
    if (liveMatches.length === 0) return
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

  const handleMatchEnded = useCallback((matchId: string) => {
    setFinishedIds((prev) => new Set(prev).add(matchId))
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
            {!carouselReady ? (
              <MainSection>
                <p className="text-center text-fluid-sm text-white/50">Loading platform data…</p>
              </MainSection>
            ) : (
              <>
                <MainSection>
                  <UpcomingGamesCarousel onWatchLive={handleWatchLive} />
                </MainSection>
                <MainSection className="!p-0">
                  <DataPanel embedded onWatchLive={handleWatchLive} />
                </MainSection>
              </>
            )}
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
          onMatchEnded={handleMatchEnded}
        />
      </div>
    </AppShell>
  )
}
