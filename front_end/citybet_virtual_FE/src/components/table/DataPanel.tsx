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

/** Skeleton row for the league table */
function SkeletonTableRow({ cols }: { cols: number }) {
  return (
    <tr className="border-b border-white/5">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="py-4 px-2">
          <span
            className="inline-block h-3 animate-pulse rounded bg-white/[0.07]"
            style={{ width: i === 0 ? '7rem' : '1.5rem' }}
          />
        </td>
      ))}
    </tr>
  )
}

/** Skeleton version of the league table */
function SkeletonTable() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-fluid-sm">
        <thead>
          <tr className="border-b border-white/10 text-left text-fluid-xs uppercase tracking-wider text-white/40">
            <th className="pb-4 pr-4 font-medium">Club</th>
            <th className="pb-4 px-2 text-center font-medium">MP</th>
            <th className="pb-4 px-2 text-center font-medium">W</th>
            <th className="pb-4 px-2 text-center font-medium">D</th>
            <th className="pb-4 px-2 text-center font-medium">L</th>
            <th className="hidden pb-4 px-2 text-center font-medium sm:table-cell">GF</th>
            <th className="hidden pb-4 px-2 text-center font-medium md:table-cell">GA</th>
            <th className="pb-4 px-2 text-center font-medium">Pts</th>
            <th className="pb-4 pl-4 text-center font-medium">Last 5</th>
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 10 }).map((_, i) => (
            <SkeletonTableRow key={i} cols={9} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Skeleton for list-style tabs (fixtures / results / stats) — same pulse style as the table. */
function SkeletonList({ rows = 8 }: { rows?: number }) {
  return (
    <div className="flex flex-col">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center justify-between gap-4 border-b border-white/5 py-4">
          <span className="inline-block h-3 w-28 animate-pulse rounded bg-white/[0.07]" />
          <span className="inline-block h-3 w-12 animate-pulse rounded bg-white/[0.07]" />
          <span className="inline-block h-3 w-28 animate-pulse rounded bg-white/[0.07]" />
        </div>
      ))}
    </div>
  )
}

export function DataPanel({ embedded = false, onWatchLive }: DataPanelProps) {
  const { selectedLeague, activeTab, isAllLeagues } = useLeague()
  const { leagues, loaded } = usePlatformData()
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

  // Each tab has its own readiness — skeleton stays until THAT tab's data for
  // the active league has arrived (or cached data is already present).
  const hasData =
    activeTab === 'table'
      ? tableRows.length > 0
      : activeTab === 'fixtures'
        ? leagueFixtures.length > 0
        : activeTab === 'results'
          ? leagueResults.length > 0
          : scorerRows.length > 0
  const tabLoaded = loaded[activeTab].includes(activeLeague)
  const showSkeleton = !hasData && !tabLoaded
  const headerSkeleton = leagues.length === 0

  return (
    <section className={wrapperClass}>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-baseline gap-3">
          {headerSkeleton ? (
            <>
              <span className="inline-block h-6 w-32 animate-pulse rounded bg-white/[0.07]" />
              <span className="inline-block h-4 w-12 animate-pulse rounded bg-white/[0.07]" />
            </>
          ) : (
            <>
              <h2 className="text-fluid-lg font-semibold text-white">
                {isAllLeagues ? activeLeague : selectedLeague}
              </h2>
              <span className="text-fluid-sm text-white/50">
                GW <span className="font-semibold text-white">{gameweek}</span>
              </span>
            </>
          )}
        </div>
        <TabSwitcher />
      </div>

      <div className="relative min-h-[280px]">
        {/* Table/fixture skeleton while initial data is loading */}
        {showSkeleton ? (
          activeTab === 'table' ? <SkeletonTable /> : <SkeletonList />
        ) : (
          <>
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
          </>
        )}
      </div>
    </section>
  )
}
