import { useEffect, useState } from 'react'

const SPEED = Number(import.meta.env.VITE_VIRTUAL_CLOCK_SPEED ?? 60)
const DEFAULT_SPAN_MS = 110_160_000 // ~306 fixtures × 6 min

/** Virtual timeline position in ms (loops), aligned with backend show_at_ms. */
export function useVirtualClock(spanMs = DEFAULT_SPAN_MS) {
  const [virtualMs, setVirtualMs] = useState(0)

  useEffect(() => {
    const anchor = Date.now()
    const tick = () => {
      const elapsed = Date.now() - anchor
      setVirtualMs(Math.floor((elapsed * SPEED) % spanMs))
    }
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [spanMs])

  return virtualMs
}
