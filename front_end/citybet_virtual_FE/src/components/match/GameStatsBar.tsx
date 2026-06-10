import type { SyncedMatchState } from '../../hooks/useVideoSyncedMatchState'

interface StatRowProps {
  label: string
  home: number | string
  away: number | string
}

function StatRow({ label, home, away }: StatRowProps) {
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 py-2">
      <span className="text-right font-mono text-fluid-sm font-semibold tabular-nums text-white">
        {home}
      </span>
      <span className="min-w-[5.5rem] text-center text-fluid-xs uppercase tracking-wider text-white/40">
        {label}
      </span>
      <span className="text-left font-mono text-fluid-sm font-semibold tabular-nums text-white">
        {away}
      </span>
    </div>
  )
}

export function GameStatsBar({ synced }: { synced: SyncedMatchState }) {
  return (
    <div className="space-y-1 border-t border-white/10 pt-4">
      <h3 className="mb-3 text-fluid-sm font-semibold text-white">Game Stats</h3>
      <StatRow label="Goals" home={synced.homeScore} away={synced.awayScore} />
      <StatRow label="Possession" home={`${synced.possession[0]}%`} away={`${synced.possession[1]}%`} />
      <StatRow label="Shots" home={synced.shots[0]} away={synced.shots[1]} />
      <StatRow label="Fouls" home={synced.fouls[0]} away={synced.fouls[1]} />
      <StatRow label="Corners" home={synced.corners[0]} away={synced.corners[1]} />
    </div>
  )
}
