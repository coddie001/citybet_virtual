/** True when the backend has finished rendering and the MP4 is available. */
export function isBroadcastVideoReady(match: {
  status?: string
  hasVideo?: boolean
  source?: string
} | null): boolean {
  return match?.hasVideo === true
}

/** Sources that represent a replay match (not a genuine live broadcast). */
const REPLAY_SOURCES = new Set([
  'virtual_replay',
  'virtual_completed',
  'latest_completed',
])

/** On-air in the live stream drawer — includes replays when no live is available. */
export function isBroadcastOnAir(match: {
  status?: string
  hasVideo?: boolean
  source?: string
} | null): boolean {
  if (!match) return false
  const isLive = match.status === 'live' || match.source === 'live_status'
  const isReplayOnAir =
    REPLAY_SOURCES.has(match.source ?? '') && isBroadcastVideoReady(match)
  return (isLive && isBroadcastVideoReady(match)) || isReplayOnAir
}

/** True when this match is a replay (not a genuine live broadcast). */
export function isFallbackBroadcast(match: {
  source?: string
  isFallback?: boolean
} | null): boolean {
  if (!match) return false
  return match.isFallback === true || REPLAY_SOURCES.has(match.source ?? '')
}

/** Live in DB but sim/render still running — stays on carousel 00:00, not in drawer. */
export function isPreparingBroadcast(match: {
  status?: string
  hasVideo?: boolean
  source?: string
} | null): boolean {
  if (!match) return false
  if (match.status === 'preparing') return true
  const isLive = match.status === 'live' || match.source === 'live_status'
  return isLive && !isBroadcastVideoReady(match)
}

