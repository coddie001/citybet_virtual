import type { FormResult } from '../../types'

export function FormDots({ results }: { results: FormResult[] }) {
  return (
    <div className="flex items-center justify-center gap-1.5">
      {results.map((r, i) => (
        <span
          key={i}
          className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
            r === 'W'
              ? 'bg-brand text-black'
              : r === 'D'
                ? 'bg-white/20 text-white'
                : 'bg-loss text-white'
          }`}
          title={r === 'W' ? 'Win' : r === 'D' ? 'Draw' : 'Loss'}
        >
          {r === 'W' ? '✓' : r === 'D' ? '–' : '✕'}
        </span>
      ))}
    </div>
  )
}
