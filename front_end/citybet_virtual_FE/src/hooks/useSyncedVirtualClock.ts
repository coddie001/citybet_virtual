import { useEffect, useMemo, useState } from 'react'

const SPEED = Number(import.meta.env.VITE_VIRTUAL_CLOCK_SPEED ?? 60)
const FIXTURE_INTERVAL_MS = 360_000

/** Extrapolate virtual clock between 60s API polls, looping within season span. */
export function useSyncedVirtualClock(apiClockMs: number, maxShowAtMs: number) {
  const spanMs = useMemo(
    () => (maxShowAtMs > 0 ? maxShowAtMs + FIXTURE_INTERVAL_MS : 110_160_000),
    [maxShowAtMs],
  )
  const [anchor, setAnchor] = useState({ clock: apiClockMs, at: Date.now() })

  useEffect(() => {
    setAnchor({ clock: apiClockMs, at: Date.now() })
  }, [apiClockMs])

  const [virtualMs, setVirtualMs] = useState(apiClockMs)

  useEffect(() => {
    const tick = () => {
      const elapsed = Date.now() - anchor.at
      const raw = anchor.clock + elapsed * SPEED
      setVirtualMs(Math.floor(raw % spanMs))
    }
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [anchor, spanMs])

  return virtualMs
}
