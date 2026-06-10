/** True when the backend has finished rendering and the MP4 is available. */
export function isBroadcastVideoReady(match: {
  status?: string
  hasVideo?: boolean
  source?: string
} | null): boolean {
  return match?.hasVideo === true
}

/** On-air in the live stream drawer — DB live and video file exists. */
export function isBroadcastOnAir(match: {
  status?: string
  hasVideo?: boolean
  source?: string
} | null): boolean {
  if (!match) return false
  const isLive = match.status === 'live' || match.source === 'live_status'
  return isLive && isBroadcastVideoReady(match)
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
