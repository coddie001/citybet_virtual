import { useEffect, useState } from 'react'
import type { ApiCountdown } from '../api/types'

/** Tick down ms_until_kickoff between API polls (server is source of truth). */
export function useApiCountdown(countdown: ApiCountdown | null | undefined) {
  const [seconds, setSeconds] = useState(countdown?.countdown_seconds ?? 0)
  const [inWindow, setInWindow] = useState(countdown?.in_countdown_window ?? false)
  const [isKickoff, setIsKickoff] = useState(countdown?.is_kickoff ?? false)

  useEffect(() => {
    if (!countdown) {
      setSeconds(0)
      setInWindow(false)
      setIsKickoff(false)
      return
    }
    setSeconds(countdown.countdown_seconds)
    setInWindow(countdown.in_countdown_window)
    setIsKickoff(countdown.is_kickoff)
  }, [
    countdown?.next_match_id,
    countdown?.countdown_seconds,
    countdown?.in_countdown_window,
    countdown?.is_kickoff,
    countdown?.ms_until_kickoff,
  ])

  useEffect(() => {
    if (!countdown?.in_countdown_window) return
    const id = window.setInterval(() => {
      setSeconds((s) => {
        const next = Math.max(0, s - 1)
        if (next === 0) {
          setInWindow(false)
          setIsKickoff(true)
        }
        return next
      })
    }, 1000)
    return () => window.clearInterval(id)
  }, [countdown?.in_countdown_window, countdown?.next_match_id])

  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')

  return {
    nextMatchId: countdown?.next_match_id,
    inWindow,
    isKickoff,
    formatted: inWindow ? `${mm}:${ss}` : '00:00',
  }
}
