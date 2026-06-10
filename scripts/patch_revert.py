#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# coordinator
p = ROOT / "workers/platform_coordinator.py"
t = p.read_text()
t = t.replace("STUCK_LIVE_WITHOUT_VIDEO_SEC = 45 * 60", "STUCK_LIVE_WITHOUT_VIDEO_SEC = 10 * 60")
t = t.replace(
    "if elapsed >= STUCK_LIVE_WITHOUT_VIDEO_SEC and steps < 100:",
    "if elapsed >= STUCK_LIVE_WITHOUT_VIDEO_SEC:",
)
t = t.replace(
    '"Re-queued stuck live fixture %s (no video after %ds).",',
    '"Re-queued stuck live fixture %s (no video after %ds, steps=%d).",',
)
t = t.replace(
    "                        f.match_id,\n                        int(elapsed),\n                    )",
    "                        f.match_id,\n                        int(elapsed),\n                        steps,\n                    )",
    1,
)
p.write_text(t)

# carousel
p2 = ROOT / "front_end/citybet_virtual_FE/src/components/carousel/UpcomingGamesCarousel.tsx"
t2 = p2.read_text()
t2 = t2.replace(
    "showCountdown={preparing || (cd.showWindow && !onAir && cd.isNext)}",
    "showCountdown={(preparing && cd.isNext) || (cd.showWindow && !onAir && cd.isNext)}",
)
t2 = t2.replace(
    "countdown={preparing ? '00:00' : cd.formatted}",
    "countdown={preparing && cd.isNext && !cd.showWindow ? '00:00' : cd.formatted}",
)
p2.write_text(t2)

# revert LiveMatchPanel
panel = ROOT / "front_end/citybet_virtual_FE/src/components/match/LiveMatchPanel.tsx"
panel.write_text(
    """import { isBroadcastOnAir } from '../../utils/liveVideo'
import type { LiveMatch } from '../../types'
import { LiveVideoTile } from './LiveVideoTile'

interface LiveMatchPanelProps {
  matches: LiveMatch[]
  multiMode: boolean
  matchIndex: number
  onMatchIndexChange: (index: number) => void
  onMatchEnded?: (matchId: string) => void
}

export function LiveMatchPanel({
  matches,
  multiMode,
  matchIndex,
  onMatchIndexChange,
  onMatchEnded,
}: LiveMatchPanelProps) {
  const displayMatches = matches.filter((m) => isBroadcastOnAir(m))

  if (displayMatches.length === 0) {
    return (
      <div className="flex h-full min-h-0 flex-col items-center justify-center p-6 text-center">
        <p className="text-fluid-sm text-white/40">
          No live broadcast right now — a match joins when its video is ready
        </p>
      </div>
    )
  }

  if (displayMatches.length > 1) {
    return (
      <div className="flex h-full min-h-0 flex-col gap-3 p-3 sm:p-4">
        <p className="shrink-0 text-fluid-xs font-semibold uppercase tracking-wider text-brand">
          Live broadcasts ({displayMatches.length})
        </p>
        <div className="grid min-h-0 flex-1 auto-rows-fr grid-cols-1 gap-3 sm:grid-cols-2">
          {displayMatches.map((m) => (
            <LiveVideoTile key={m.id} match={m} onEnded={onMatchEnded} />
          ))}
        </div>
      </div>
    )
  }

  const match = displayMatches[matchIndex] ?? displayMatches[0]
  const canNavigate = multiMode && displayMatches.length > 1

  return (
    <div className="flex h-full min-h-0 flex-col p-3 sm:p-4">
      {canNavigate && (
        <div className="mb-3 flex shrink-0 items-center justify-center gap-3">
          <button
            type="button"
            onClick={() =>
              onMatchIndexChange((matchIndex - 1 + displayMatches.length) % displayMatches.length)
            }
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-white/60 transition hover:bg-white/5 hover:text-white"
            aria-label="Previous match"
          >
            ‹
          </button>
          <div className="flex gap-1.5">
            {displayMatches.map((m, i) => (
              <button
                key={m.id}
                type="button"
                onClick={() => onMatchIndexChange(i)}
                className={`h-1.5 rounded-full transition-all ${
                  i === matchIndex ? 'w-6 bg-brand' : 'w-1.5 bg-white/20'
                }`}
                aria-label={`Match ${i + 1}`}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() =>
              onMatchIndexChange((matchIndex + 1) % displayMatches.length)
            }
            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-white/60 transition hover:bg-white/5 hover:text-white"
            aria-label="Next match"
          >
            ›
          </button>
        </div>
      )}
      <LiveVideoTile match={match} onEnded={onMatchEnded} />
    </div>
  )
}
"""
)

uvs = ROOT / "front_end/citybet_virtual_FE/src/hooks/useVideoStream.ts"
if uvs.is_file():
    uvs.unlink()

cache = ROOT / "front_end/citybet_virtual_FE/src/api/platformCache.ts"
ct = cache.read_text()
ct = ct.replace("const CACHE_VERSION = 20", "const CACHE_VERSION = 21")
cache.write_text(ct)

(ROOT / "scripts/reset_stuck_live.py").write_text(
    """#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.db import SessionLocal, Fixture, GfrDump
from utils.virtual_schedule import match_has_video

if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = 0
        for f in db.query(Fixture).filter(Fixture.status == "live").all():
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            if match_has_video(dump, f.match_id):
                continue
            pred = dict(f.predictions or {})
            for k in ("_broadcast_started_at", "_live_started_at", "_live_stuck_at"):
                pred.pop(k, None)
            f.predictions = pred
            f.status = "upcoming"
            n += 1
            print("re-queued", f.match_id)
        if n:
            db.commit()
        print("done:", n)
    finally:
        db.close()
"""
)

print("patch_revert done")
