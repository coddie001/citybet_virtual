import { useMemo } from 'react'
import type { LiveMatch } from '../types'

export type CommentaryKind = 'kickoff' | 'goal' | 'chance' | 'half' | 'fulltime' | 'info'

export interface CommentaryLine {
  id: string
  videoSec: number
  text: string
  kind: CommentaryKind
}

function matchMinute(videoSec: number, durationSec: number): number {
  if (durationSec <= 0) return 0
  return Math.min(90, Math.max(0, Math.round((videoSec / durationSec) * 90)))
}

function buildLines(match: LiveMatch, durationSec: number): CommentaryLine[] {
  const lines: CommentaryLine[] = [
    {
      id: 'kickoff',
      videoSec: 0,
      text: `Kick off — ${match.home} vs ${match.away}`,
      kind: 'kickoff',
    },
  ]

  if (durationSec > 0) {
    lines.push({
      id: 'half',
      videoSec: durationSec * 0.48,
      text: 'Half time — teams head to the dressing room',
      kind: 'half',
    })
    lines.push({
      id: 'second-half',
      videoSec: durationSec * 0.52,
      text: 'Second half underway',
      kind: 'info',
    })
  }

  const sync = match.matchSync
  if (sync) {
    for (const g of sync.goalEvents) {
      const team = g.side === 'home' ? match.home : match.away
      const min = matchMinute(g.videoSec, durationSec)
      lines.push({
        id: `goal-${g.step}-${g.videoSec}`,
        videoSec: g.videoSec,
        text: `GOAL! ${team} score — ${g.homeScore}-${g.awayScore} (${min}')`,
        kind: 'goal',
      })
    }
  }

  lines.push({
    id: 'fulltime',
    videoSec: Math.max(0, durationSec - 0.5),
    text: `Full time — ${match.home} ${match.homeScore}–${match.awayScore} ${match.away}`,
    kind: 'fulltime',
  })

  return lines.sort((a, b) => a.videoSec - b.videoSec)
}

export function useMatchCommentary(
  match: LiveMatch,
  videoTimeSec: number,
  videoEnded: boolean,
  liveScores?: { home: number; away: number },
) {
  return useMemo(() => {
    const duration = match.matchSync?.videoDurationSec ?? 0
    const lines = buildLines(match, duration)
    const minute = matchMinute(videoTimeSec, duration)
    const homeScore = liveScores?.home ?? match.homeScore
    const awayScore = liveScores?.away ?? match.awayScore

    const visible = lines.filter((l) => l.videoSec <= videoTimeSec + 0.15)
    const active = visible.length > 0 ? visible[visible.length - 1] : lines[0]
    const history = visible.slice(-4)

    if (videoEnded && duration > 0) {
      return {
        activeLine: `Full time — ${match.home} ${homeScore}–${awayScore} ${match.away}`,
        activeKind: 'fulltime' as CommentaryKind,
        history,
        matchMinute: 90,
      }
    }

    return {
      activeLine: active?.text ?? 'Live broadcast',
      activeKind: active?.kind ?? 'info',
      history,
      matchMinute: minute,
    }
  }, [match, videoTimeSec, videoEnded, liveScores?.home, liveScores?.away])
}
