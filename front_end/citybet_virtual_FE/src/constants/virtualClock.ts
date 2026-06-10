/** Virtual broadcast timeline — must match backend VIRTUAL_CLOCK_SPEED / FIXTURE_INTERVAL_MS. */
export const VIRTUAL_CLOCK_SPEED = Number(import.meta.env.VITE_VIRTUAL_CLOCK_SPEED ?? 60)
export const FIXTURE_INTERVAL_MS = 6 * 60 * 1000
/** Real-time 3-minute countdown window (matches backend REAL_COUNTDOWN_MS). */
export const COUNTDOWN_WINDOW_MS = 3 * 60 * 1000
export const KICKOFF_GRACE_MS = 60_000

/** Convert virtual timeline milliseconds to real-time milliseconds for UI timers. */
export function virtualMsToRealMs(virtualMs: number): number {
  return virtualMs / VIRTUAL_CLOCK_SPEED
}
