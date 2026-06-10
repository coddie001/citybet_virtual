import { useLeague } from '../../context/LeagueContext'
import type { LeagueId } from '../../types'

export function LeagueDropdown() {
  const { selectedLeague, setSelectedLeague, leagueOptions } = useLeague()

  return (
    <div className="relative">
      <select
        value={selectedLeague}
        onChange={(e) => setSelectedLeague(e.target.value as LeagueId)}
        className="appearance-none rounded-xl border border-white/10 bg-surface-raised px-5 py-2.5 pr-10 text-fluid-sm font-medium text-white shadow-lg transition-colors hover:border-brand/30 focus:border-brand/50 focus:outline-none focus:ring-2 focus:ring-brand/20"
        aria-label="Select league"
      >
        {leagueOptions.map((opt) => (
          <option key={opt.id} value={opt.id} className="bg-surface-raised">
            {opt.label}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-white/50">
        ▾
      </span>
    </div>
  )
}
