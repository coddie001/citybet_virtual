/** Simplified top-down pitch with player markers (mock positions). */
const HOME_POSITIONS = [
  { n: 1, x: 8, y: 50 },
  { n: 2, x: 22, y: 18 },
  { n: 3, x: 22, y: 38 },
  { n: 4, x: 22, y: 62 },
  { n: 5, x: 22, y: 82 },
  { n: 6, x: 38, y: 28 },
  { n: 7, x: 38, y: 50 },
  { n: 8, x: 38, y: 72 },
  { n: 9, x: 55, y: 22 },
  { n: 10, x: 55, y: 50 },
  { n: 11, x: 55, y: 78 },
]

export function PitchView() {
  return (
    <div className="relative aspect-[16/10] w-full overflow-hidden rounded-xl border border-brand/20 bg-gradient-to-b from-emerald-800 to-emerald-900">
      {/* Pitch lines */}
      <div className="absolute inset-[4%] rounded-lg border-2 border-white/25" />
      <div className="absolute left-[4%] right-[4%] top-1/2 h-0.5 -translate-y-1/2 bg-white/25" />
      <div className="absolute left-1/2 top-[4%] h-[92%] w-24 -translate-x-1/2 rounded-full border-2 border-white/25" />
      <div className="absolute left-[4%] top-1/2 h-16 w-16 -translate-y-1/2 rounded-full border-2 border-white/20" />
      <div className="absolute right-[4%] top-1/2 h-16 w-16 -translate-y-1/2 rounded-full border-2 border-white/20" />

      {HOME_POSITIONS.map((p) => (
        <div
          key={p.n}
          className="absolute flex h-7 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-loss text-[10px] font-bold text-white shadow-lg sm:h-8 sm:w-8"
          style={{ left: `${p.x}%`, top: `${p.y}%` }}
        >
          {p.n}
        </div>
      ))}
    </div>
  )
}
