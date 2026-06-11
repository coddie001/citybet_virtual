import type { CommentaryKind } from '../../hooks/useMatchCommentary'

const kindStyles: Record<CommentaryKind, string> = {
  kickoff: 'border-brand/30 bg-brand/5',
  goal: 'border-brand/50 bg-brand/10',
  chance: 'border-white/15 bg-white/[0.03]',
  half: 'border-white/20 bg-white/[0.04]',
  fulltime: 'border-white/25 bg-white/[0.05]',
  info: 'border-white/10 bg-white/[0.02]',
}

interface LiveCommentaryStripProps {
  line: string
  kind: CommentaryKind
}

export function LiveCommentaryStrip({ line, kind }: LiveCommentaryStripProps) {
  return (
    <section
      className={`shrink-0 rounded-lg border px-3 py-2.5 transition-colors ${kindStyles[kind]}`}
      aria-live="polite"
    >
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-white/40">
        Match commentary
      </p>
      <p className="text-fluid-sm leading-snug text-white/90">{line}</p>
    </section>
  )
}
