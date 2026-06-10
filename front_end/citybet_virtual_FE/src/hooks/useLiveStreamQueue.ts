import { useCallback, useRef, useState } from 'react'
import { api } from '../api/client'
import type { LiveMatch, UpcomingMatch } from '../types'

function upcomingToLive(match: UpcomingMatch): LiveMatch {
  return {
    id: match.id,
    league: match.league,
    home: match.home,
    away: match.away,
    homeScore: 0,
    awayScore: 0,
    status: 'live',
    showAtMs: match.showAtMs,
    hasVideo: match.hasVideo,
    possession: [50, 50],
    shots: [0, 0],
    fouls: [0, 0],
    corners: [0, 0],
  }
}

/** Probe video URLs until one is playable or timeout. */
async function waitForVideoReady(matchId: string, timeoutMs = 120_000): Promise<boolean> {
  const sources = api.videoSources(matchId)
  const deadline = Date.now() + timeoutMs

  while (Date.now() < deadline) {
    for (const src of sources) {
      const ok = await new Promise<boolean>((resolve) => {
        const el = document.createElement('video')
        el.muted = true
        el.preload = 'auto'
        const done = (v: boolean) => {
          el.removeAttribute('src')
          el.load()
          resolve(v)
        }
        el.oncanplay = () => done(true)
        el.onerror = () => done(false)
        el.src = src
        window.setTimeout(() => done(false), 4000)
      })
      if (ok) return true
    }
    await new Promise((r) => setTimeout(r, 3000))
  }
  return false
}

/**
 * FIFO live stream queue: one kickoff match at a time, autoplay once, then remove.
 */
export function useLiveStreamQueue() {
  const [queue, setQueue] = useState<LiveMatch[]>([])
  const [preparingId, setPreparingId] = useState<string | null>(null)
  const enqueuedRef = useRef<Set<string>>(new Set())

  const enqueueFromUpcoming = useCallback(async (match: UpcomingMatch) => {
    if (enqueuedRef.current.has(match.id)) return
    enqueuedRef.current.add(match.id)
    setPreparingId(match.id)

    const ready = await waitForVideoReady(match.id)
    setPreparingId((id) => (id === match.id ? null : id))

    if (ready) {
      setQueue((q) => (q.some((m) => m.id === match.id) ? q : [...q, upcomingToLive(match)]))
    } else {
      enqueuedRef.current.delete(match.id)
    }
  }, [])

  const completeCurrent = useCallback(() => {
    setQueue((q) => {
      if (q.length === 0) return q
      const [finished, ...rest] = q
      enqueuedRef.current.delete(finished.id)
      return rest
    })
  }, [])

  const current = queue[0] ?? null

  return {
    current,
    queueLength: queue.length,
    preparingId,
    enqueueFromUpcoming,
    completeCurrent,
  }
}
