import { useEffect, useState } from 'react'

export function useCountdown(initialSeconds: number, active = true) {
  const [seconds, setSeconds] = useState(initialSeconds)

  useEffect(() => {
    setSeconds(initialSeconds)
  }, [initialSeconds])

  useEffect(() => {
    if (!active || seconds <= 0) return
    const id = window.setInterval(() => {
      setSeconds((s) => Math.max(0, s - 1))
    }, 1000)
    return () => window.clearInterval(id)
  }, [active, seconds])

  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')

  return { seconds, formatted: `${mm}:${ss}`, isComplete: seconds <= 0 }
}
