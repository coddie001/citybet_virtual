import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'

const LOAD_TIMEOUT_MS = 20_000

/**
 * Stream match video with source fallback and stall timeout.
 */
export function useVideoStream(matchId: string | undefined, enabled = true) {
  const [sourceIndex, setSourceIndex] = useState(0)
  const [error, setError] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)

  const sources = useMemo(
    () => (matchId ? api.videoSources(matchId) : []),
    [matchId],
  )
  const videoSrc =
    matchId && enabled && !error ? (sources[sourceIndex] ?? null) : null

  useEffect(() => {
    setSourceIndex(0)
    setError(false)
    setIsPlaying(false)
  }, [matchId, enabled])

  useEffect(() => {
    if (!videoSrc || error || isPlaying) return
    const id = window.setTimeout(() => setError(true), LOAD_TIMEOUT_MS)
    return () => window.clearTimeout(id)
  }, [videoSrc, error, isPlaying, sourceIndex])

  const onVideoError = useCallback(() => {
    setSourceIndex((idx) => {
      const next = idx + 1
      if (next < sources.length) return next
      setError(true)
      return idx
    })
  }, [sources.length])

  const onVideoPlaying = useCallback(() => {
    setIsPlaying(true)
    setError(false)
  }, [])

  return {
    videoSrc,
    error,
    isPlaying,
    onVideoError,
    onVideoPlaying,
  }
}
