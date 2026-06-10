import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api/client'
import { useVideoSyncedMatchState } from '../../hooks/useVideoSyncedMatchState'
import { isBroadcastOnAir } from '../../utils/liveVideo'
import {
  attachVideoPlaybackDebug,
  failureFromMediaError,
  failureMessage,
  isVideoDebugEnabled,
  logVideoDebug,
  probeVideoUrl,
  setVideoDebugFailure,
  type VideoPlaybackFailure,
} from '../../utils/videoPlaybackDebug'
import { GameStatsBar } from './GameStatsBar'
import type { LiveMatch } from '../../types'

interface LiveVideoTileProps {
  match: LiveMatch
  onEnded?: (matchId: string) => void
  /** Full drawer layout with score header + stats (single broadcast). */
  expanded?: boolean
}

export function LiveVideoTile({ match, onEnded, expanded = false }: LiveVideoTileProps) {
  const [sourceIndex, setSourceIndex] = useState(0)
  const [videoError, setVideoError] = useState(false)
  const [failure, setFailure] = useState<VideoPlaybackFailure | null>(null)
  const [videoTimeSec, setVideoTimeSec] = useState(0)
  const [videoEnded, setVideoEnded] = useState(false)
  const [muted, setMuted] = useState(true)
  const videoRef = useRef<HTMLVideoElement>(null)
  const synced = useVideoSyncedMatchState(match, videoTimeSec, videoEnded)

  const sources = useMemo(() => api.videoSources(match.id), [match.id])
  const onAir = isBroadcastOnAir(match)
  const videoSrc = onAir ? (sources[sourceIndex] ?? '') : ''

  useEffect(() => {
    setSourceIndex(0)
    setVideoError(false)
    setFailure(null)
    setVideoTimeSec(0)
    setVideoEnded(false)
  }, [match.id])

  useEffect(() => {
    if (!videoSrc || !onAir || videoError) return

    let cancelled = false
    void (async () => {
      const probe = await probeVideoUrl(match.id, videoSrc)
      if (cancelled) return
      if (!probe.ok) {
        const nextFailure: VideoPlaybackFailure = !probe.moovAtStart && (probe.status === 200 || probe.status === 206)
          ? { code: 'moov', message: 'MP4 metadata not at file start — still finalizing' }
          : probe.status === 404
            ? { code: 'http', message: 'Video not found', httpStatus: 404 }
            : probe.status > 0
              ? { code: 'http', message: `HTTP ${probe.status}`, httpStatus: probe.status }
              : { code: 'network', message: 'Could not reach video endpoint' }
        setVideoDebugFailure(match.id, nextFailure)
        if (isVideoDebugEnabled()) {
          logVideoDebug(match.id, 'state', { preflightFailed: true, probe })
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [videoSrc, onAir, videoError, match.id])

  useEffect(() => {
    const el = videoRef.current
    if (!el || !videoSrc || videoError || !onAir) return

    const detachDebug = attachVideoPlaybackDebug(el, match.id, videoSrc)

    el.muted = muted
    el.load()
    const play = () => {
      void el.play().catch((err: unknown) => {
        const name = err instanceof DOMException ? err.name : 'Error'
        if (name === 'NotAllowedError') {
          const autoplayFailure: VideoPlaybackFailure = {
            code: 'autoplay',
            message: 'Autoplay blocked by browser policy',
          }
          setFailure(autoplayFailure)
          setVideoDebugFailure(match.id, autoplayFailure)
        }
      })
    }
    play()
    el.addEventListener('loadeddata', play)
    el.addEventListener('canplay', play)
    return () => {
      el.removeEventListener('loadeddata', play)
      el.removeEventListener('canplay', play)
      detachDebug()
    }
  }, [videoSrc, videoError, onAir, muted, match.id])

  useEffect(() => {
    const el = videoRef.current
    if (!el || !videoSrc || videoError || !onAir) return

    let raf = 0
    const tick = () => {
      if (!el.paused && !el.ended) {
        setVideoTimeSec(el.currentTime)
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [videoSrc, videoError, onAir, match.id])

  const handleVideoError = () => {
    const el = videoRef.current
    const mediaFailure = el ? failureFromMediaError(el, videoSrc) : null
    const next = sourceIndex + 1
    if (next < sources.length) {
      if (mediaFailure) setVideoDebugFailure(match.id, mediaFailure)
      setSourceIndex(next)
      return
    }
    setFailure(mediaFailure)
    setVideoError(true)
    if (mediaFailure) setVideoDebugFailure(match.id, mediaFailure)
  }

  const errorText = videoError ? failureMessage(failure) : 'Waiting for broadcast…'

  const scoreLine = (
    <div className={expanded ? 'mb-3 shrink-0' : 'px-2 pt-1'}>
      {expanded && (
        <p className="text-fluid-xs font-semibold uppercase tracking-wider text-brand">
          {match.league}
        </p>
      )}
      <div
        className={
          expanded
            ? 'mt-1 grid grid-cols-[1fr_auto_1fr] items-center gap-2'
            : 'truncate text-center text-[11px] text-white/80'
        }
      >
        <p className={expanded ? 'truncate text-right text-fluid-sm font-medium text-white' : ''}>
          {expanded ? match.home : `${match.home} `}
        </p>
        <span
          className={
            expanded
              ? 'font-mono text-fluid-lg font-bold tabular-nums text-white'
              : 'font-mono font-bold text-white'
          }
        >
          {synced.homeScore} – {synced.awayScore}
        </span>
        <p className={expanded ? 'truncate text-left text-fluid-sm font-medium text-white' : ''}>
          {expanded ? match.away : match.away}
        </p>
      </div>
    </div>
  )

  const videoBlock = (
    <div
      className={
        expanded
          ? 'live-video-frame relative min-h-[220px] flex-1 overflow-hidden rounded-lg border border-white/10 bg-black'
          : 'relative aspect-video w-full bg-black'
      }
    >
      {!videoError && videoSrc ? (
        <video
          ref={videoRef}
          key={`${match.id}-${sourceIndex}`}
          src={videoSrc}
          autoPlay
          muted={muted}
          playsInline
          controls
          preload="auto"
          className={expanded ? 'h-full w-full object-contain' : 'h-full w-full object-cover'}
          onError={handleVideoError}
          onTimeUpdate={(e) => setVideoTimeSec(e.currentTarget.currentTime)}
          onEnded={() => {
            setVideoEnded(true)
            onEnded?.(match.id)
          }}
        />
      ) : (
        <p className="flex h-full items-center justify-center px-4 text-center text-fluid-sm text-white/50">
          {errorText}
        </p>
      )}
    </div>
  )

  if (expanded) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        {scoreLine}
        {videoBlock}
        <div className="mt-3 flex shrink-0 items-center justify-end">
          <button
            type="button"
            onClick={() => setMuted((m) => !m)}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-fluid-xs text-white/60 hover:bg-white/5 hover:text-white"
          >
            {muted ? 'Unmute' : 'Mute'}
          </button>
        </div>
        <div className="shrink-0">
          <GameStatsBar synced={synced} />
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-white/10 bg-black/80">
      <div className="flex items-center justify-between gap-1 border-b border-white/10 px-2 py-1">
        <p className="truncate text-[10px] font-semibold uppercase tracking-wide text-brand">
          {match.league}
        </p>
        <button
          type="button"
          onClick={() => setMuted((m) => !m)}
          className="shrink-0 rounded px-1.5 py-0.5 text-[10px] text-white/50 hover:bg-white/10 hover:text-white"
          aria-label={muted ? 'Unmute' : 'Mute'}
        >
          {muted ? '🔇' : '🔊'}
        </button>
      </div>
      {scoreLine}
      {videoBlock}
    </div>
  )
}
