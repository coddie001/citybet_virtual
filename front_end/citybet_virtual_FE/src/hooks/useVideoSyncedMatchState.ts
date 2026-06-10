import { useMemo } from 'react'
import type { LiveMatch, MatchSyncPayload } from '../types'

export interface SyncedMatchState {
  homeScore: number
  awayScore: number
  possession: [number, number]
  shots: [number, number]
  fouls: [number, number]
  corners: [number, number]
  isAtFullTime: boolean
}

function lerp(start: number, end: number, t: number): number {
  return Math.round(start + (end - start) * t)
}

/** Score at video time from goal_events (each event has videoSec + cumulative score). */
function scoreAtTime(sync: MatchSyncPayload, currentTimeSec: number): [number, number] {
  let home = 0
  let away = 0
  for (const event of sync.goalEvents) {
    if (currentTimeSec >= event.videoSec) {
      home = event.homeScore
      away = event.awayScore
    }
  }
  return [home, away]
}

function progress(currentTimeSec: number, durationSec: number): number {
  if (durationSec <= 0) return 0
  return Math.min(1, Math.max(0, currentTimeSec / durationSec))
}

const NEUTRAL: SyncedMatchState = {
  homeScore: 0,
  awayScore: 0,
  possession: [50, 50],
  shots: [0, 0],
  fouls: [0, 0],
  corners: [0, 0],
  isAtFullTime: false,
}

function polledMatchState(match: LiveMatch): SyncedMatchState {
  return {
    homeScore: match.homeScore,
    awayScore: match.awayScore,
    possession: match.possession,
    shots: match.shots,
    fouls: match.fouls,
    corners: match.corners,
    isAtFullTime: false,
  }
}

export function useVideoSyncedMatchState(
  match: LiveMatch | null | undefined,
  currentTimeSec: number,
  videoEnded = false,
): SyncedMatchState {
  return useMemo(() => {
    if (!match) return NEUTRAL

    const sync = match.matchSync
    const duration = sync?.videoDurationSec ?? 0
    const atFullTime =
      videoEnded || (duration > 0 && currentTimeSec >= duration - 0.25)

    if (atFullTime) {
      return {
        ...polledMatchState(match),
        isAtFullTime: true,
      }
    }

    if (!sync) {
      return polledMatchState(match)
    }

    const final = sync.finalStats
    const [homeScore, awayScore] = scoreAtTime(sync, currentTimeSec)
    const t = progress(currentTimeSec, duration)

    return {
      homeScore,
      awayScore,
      possession: [
        lerp(50, final.possession.homePct, t),
        lerp(50, final.possession.awayPct, t),
      ],
      shots: [lerp(0, final.shotsHome, t), lerp(0, final.shotsAway, t)],
      fouls: [lerp(0, final.foulsHome, t), lerp(0, final.foulsAway, t)],
      corners: [lerp(0, final.cornersHome, t), lerp(0, final.cornersAway, t)],
      isAtFullTime: false,
    }
  }, [match, currentTimeSec, videoEnded])
}
