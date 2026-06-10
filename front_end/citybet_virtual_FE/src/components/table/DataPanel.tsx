import { useMemo } from 'react'
import { useLeague } from '../../context/LeagueContext'
import { getSyncedGameweek, usePlatformData } from '../../context/PlatformDataContext'
import { useFilteredData } from '../../hooks/useFilteredData'
import { useLeagueRotation } from '../../hooks/useLeagueRotation'
import { TabSwitcher } from './TabSwitcher'
import { LeagueTable } from './LeagueTable'
import { FixturesList } from './FixturesList'
import { ResultsList } from './ResultsList'
import { StatsPanel } from './StatsPanel'
import type { LeagueId } from '../../types'

interface DataPanelProps {
  embedded?: boolean
  onWatchLive?: (league: LeagueId, matchId?: string) => void
}

export function DataPanel({ embedded = false, onWatchLive }: DataPanelProps) {
  const { selectedLeague, activeTab, isAllLeagues } = useLeague()
  const { leagues, detailsReady } = usePlatformData()
  const { fixtures, results, tables, scorers } = useFilteredData(selectedLeague)
  const { currentLeague } = useLeagueRotation(isAllLeagues)

  const activeLeague: Exclude<LeagueId, 'ALL'> = isAllLeagues
    ? currentLeague
    : (selectedLeague as Exclude<LeagueId, 'ALL'>)

  const gameweek = getSyncedGameweek(
    leagues,
    fixtures,
    results,
    selectedLeague,
    isAllLeagues ? currentLeague : undefined,
  )

  const leagueFixtures = useMemo(() => {
    const base = isAllLeagues ? fixtures.filter((f) => f.league === activeLeague) : fixtures
    return [...base]
      .filter((f) => {
        if (f.status === 'live' || f.status === 'preparing') return true
        return f.status !== 'completed' && f.gameweek === gameweek
      })
      .sort((a, b) => {
        if (a.status === 'live' && b.status !== 'live') return -1
        if (b.status === 'live' && a.status !== 'live') return 1
        if (a.status === 'preparing' && b.status === 'upcoming') return -1
        if (b.status === 'preparing' && a.status === 'upcoming') return 1
        const aCurrent = a.gameweek === gameweek ? 0 : 1
        const bCurrent = b.gameweek === gameweek ? 0 : 1
        if (aCurrent !== bCurrent) return aCurrent - bCurrent
        return a.gameweek - b.gameweek
      })
  }, [isAllLeagues, fixtures, activeLeague, gameweek])

  const leagueResults = useMemo(() => {
    if (!isAllLeagues) return results
    return results.filter((r) => r.league === activeLeague)
  }, [isAllLeagues, results, activeLeague])

  const wrapperClass = embedded
    ? 'px-5 py-6 sm:px-8 sm:py-7 lg:px-10 lg:py-8'
    : 'panel-green p-5 sm:p-8 lg:p-10'

  const tableRows = tables[activeLeague] ?? []
  const scorerRows = scorers[activeLeague] ?? []

  return (
    <section className={wrapperClass}>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-baseline gap-3">
          <h2 className="text-fluid-lg font-semibold text-white">
            {isAllLeagues ? activeLeague : selectedLeague}
          </h2>
          <span className="text-fluid-sm text-white/50">
            GW <span className="font-semibold text-white">{gameweek}</span>
          </span>
        </div>
        <TabSwitcher />
      </div>

      <div className="relative min-h-[280px]">
        {!detailsReady && (
          <p className="absolute inset-x-0 top-0 z-10 py-2 text-center text-fluid-xs text-white/40">
            Syncing league data…
          </p>
        )}
        {activeTab === 'table' && (
          <div key={`table-${activeLeague}-gw${gameweek}`} className="crossfade-enter">
            <LeagueTable rows={tableRows} />
          </div>
        )}
        {activeTab === 'fixtures' && (
          <div key={`fixtures-${activeLeague}-gw${gameweek}`} className="crossfade-enter">
            <FixturesList fixtures={leagueFixtures} onWatchLive={onWatchLive} />
          </div>
        )}
        {activeTab === 'results' && (
          <div key={`results-${activeLeague}-gw${gameweek}`} className="crossfade-enter">
            <ResultsList results={leagueResults} />
          </div>
        )}
        {activeTab === 'stats' && (
          <div key={`stats-${activeLeague}-gw${gameweek}`} className="crossfade-enter">
            <StatsPanel scorers={scorerRows} />
          </div>
        )}
      </div>
    </section>
  )
}
