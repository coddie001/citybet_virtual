import type { TableRow } from '../../types'
import { FormDots } from '../ui/FormDots'

export function LeagueTable({ rows, leagueLabel }: { rows: TableRow[]; leagueLabel?: string }) {
  return (
    <div className="crossfade-enter">
      {leagueLabel && (
        <p className="mb-3 text-fluid-xs font-medium uppercase tracking-widest text-brand/80">
          {leagueLabel}
        </p>
      )}
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
            {rows.map((row) => (
              <tr
                key={row.club}
                className="border-b border-white/5 transition-colors hover:bg-white/[0.03]"
              >
                <td className="py-4 pr-4 font-semibold text-white">{row.club}</td>
                <td className="py-4 px-2 text-center text-white/70">{row.mp}</td>
                <td className="py-4 px-2 text-center text-white/70">{row.w}</td>
                <td className="py-4 px-2 text-center text-white/70">{row.d}</td>
                <td className="py-4 px-2 text-center text-white/70">{row.l}</td>
                <td className="hidden py-4 px-2 text-center text-white/70 sm:table-cell">{row.gf}</td>
                <td className="hidden py-4 px-2 text-center text-white/70 md:table-cell">{row.ga}</td>
                <td className="py-4 px-2 text-center font-bold text-white">{row.pts}</td>
                <td className="py-4 pl-4">
                  <FormDots results={row.last5} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
