import type { ScorerRow } from '../../types'

export function StatsPanel({ scorers, title }: { scorers: ScorerRow[]; title?: string }) {
  return (
    <div className="crossfade-enter">
      {title && (
        <p className="mb-4 text-fluid-xs font-medium uppercase tracking-widest text-brand/80">
          {title} — Top Scorers
        </p>
      )}
      <div className="space-y-1">
        <div className="grid grid-cols-[2rem_1fr_1fr_4rem_4rem] gap-2 border-b border-white/10 pb-3 text-fluid-xs uppercase tracking-wider text-white/40">
          <span>#</span>
          <span>Player</span>
          <span>Club</span>
          <span className="text-center">G</span>
          <span className="text-center">Apps</span>
        </div>
        {scorers.map((s) => (
          <div
            key={s.rank}
            className="grid grid-cols-[2rem_1fr_1fr_4rem_4rem] items-center gap-2 rounded-lg py-3 transition-colors hover:bg-white/[0.03]"
          >
            <span className="text-fluid-sm font-bold text-white/50">{s.rank}</span>
            <span className="truncate text-fluid-sm font-semibold text-white">{s.player}</span>
            <span className="truncate text-fluid-sm text-white/60">{s.club}</span>
            <span className="text-center text-fluid-sm font-bold text-brand">{s.goals}</span>
            <span className="text-center text-fluid-sm text-white/50">{s.appearances}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
