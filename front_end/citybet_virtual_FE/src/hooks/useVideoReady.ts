import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { isBroadcastVideoReady } from '../utils/liveVideo'

type MatchLike = {
  id?: string
  status?: string
  hasVideo?: boolean
  source?: string
} | null

/**
 * True when API reports has_video or a live match's MP4 responds to a range probe.
 */
export function useVideoReady(match: MatchLike): boolean {
  const apiReady = isBroadcastVideoReady(match)
  const [probedReady, setProbedReady] = useState(false)

  useEffect(() => {
    setProbedReady(false)
  }, [match?.id])

  useEffect(() => {
    if (!match?.id || apiReady) return
    const isLive = match.status === 'live' || match.source === 'live_status'
    if (!isLive) return

    let cancelled = false
    const check = async () => {
      const url = await api.probeVideo(match.id!)
      if (!cancelled && url) setProbedReady(true)
    }
    void check()
    const timer = window.setInterval(() => void check(), 5000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [match?.id, match?.status, match?.source, apiReady])

  return apiReady || probedReady
}
