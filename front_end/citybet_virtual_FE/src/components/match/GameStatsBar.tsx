import type { SyncedMatchState } from '../../hooks/useVideoSyncedMatchState'

interface StatRowProps {
  label: string
  home: number | string
  away: number | string
}

function StatRow({ label, home, away }: StatRowProps) {
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 py-1.5">
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

function PossessionBar({ homePct, awayPct }: { homePct: number; awayPct: number }) {
  return (
    <div className="mb-4">
      <div className="mb-2 flex justify-between text-fluid-xs font-medium text-white/50">
        <span>{homePct}%</span>
        <span className="uppercase tracking-wider">Possession</span>
        <span>{awayPct}%</span>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-white/10">
        <div
          className="bg-brand transition-all duration-500 ease-out"
          style={{ width: `${homePct}%` }}
        />
        <div
          className="bg-white/25 transition-all duration-500 ease-out"
          style={{ width: `${awayPct}%` }}
        />
      </div>
    </div>
  )
}

export function GameStatsBar({ synced }: { synced: SyncedMatchState }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
      <h3 className="mb-3 text-fluid-sm font-semibold text-white">Live stats</h3>
      <PossessionBar homePct={synced.possession[0]} awayPct={synced.possession[1]} />
      <StatRow label="Goals" home={synced.homeScore} away={synced.awayScore} />
      <StatRow label="Shots" home={synced.shots[0]} away={synced.shots[1]} />
      <StatRow label="Fouls" home={synced.fouls[0]} away={synced.fouls[1]} />
      <StatRow label="Corners" home={synced.corners[0]} away={synced.corners[1]} />
    </div>
  )
}
