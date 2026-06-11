import { useEffect, useMemo, useRef, useState } from 'react'
import { api, VIDEO_PANE_REFRESH_MS } from '../../api/client'
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
import { useMatchCommentary } from '../../hooks/useMatchCommentary'
import { GameStatsBar } from './GameStatsBar'
import { LiveCommentaryStrip } from './LiveCommentaryStrip'
import { LiveScoreHeader } from './LiveScoreHeader'
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
  const [videoDurationSec, setVideoDurationSec] = useState(0)
  const [videoEnded, setVideoEnded] = useState(false)
  const [muted, setMuted] = useState(true)
  const videoRef = useRef<HTMLVideoElement>(null)
  const synced = useVideoSyncedMatchState(match, videoTimeSec, videoEnded, videoDurationSec)
  const commentary = useMatchCommentary(match, videoTimeSec, videoEnded, {
    home: synced.homeScore,
    away: synced.awayScore,
  })

  const sources = useMemo(() => api.videoSources(match.id), [match.id])
  const onAir = isBroadcastOnAir(match)
  const videoSrc = onAir ? (sources[sourceIndex] ?? '') : ''

  useEffect(() => {
    setSourceIndex(0)
    setVideoError(false)
    setFailure(null)
    setVideoTimeSec(0)
    setVideoDurationSec(0)
    setVideoEnded(false)
  }, [match.id])

  useEffect(() => {
    const el = videoRef.current
    if (!el || !videoSrc || !onAir) return
    const applyDuration = () => {
      if (el.duration && Number.isFinite(el.duration) && el.duration > 0) {
        setVideoDurationSec(el.duration)
      }
    }
    applyDuration()
    el.addEventListener('loadedmetadata', applyDuration)
    el.addEventListener('durationchange', applyDuration)
    return () => {
      el.removeEventListener('loadedmetadata', applyDuration)
      el.removeEventListener('durationchange', applyDuration)
    }
  }, [videoSrc, onAir, match.id])

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

  /** Recover stalled streams without disrupting smooth playback. */
  useEffect(() => {
    const el = videoRef.current
    if (!el || !videoSrc || videoError || !onAir) return

    let lastTime = el.currentTime
    let lastAdvance = Date.now()

    const id = window.setInterval(() => {
      if (el.paused || el.ended) {
        lastTime = el.currentTime
        lastAdvance = Date.now()
        return
      }
      if (el.currentTime > lastTime + 0.05) {
        lastTime = el.currentTime
        lastAdvance = Date.now()
        return
      }
      if (Date.now() - lastAdvance < 15_000) return

      const t = el.currentTime
      const wasMuted = el.muted
      el.load()
      const resume = () => {
        try {
          el.currentTime = t
        } catch {
          // ignore seek errors
        }
        el.muted = wasMuted
        void el.play().catch(() => {})
        lastAdvance = Date.now()
      }
      el.addEventListener('loadeddata', resume, { once: true })
    }, VIDEO_PANE_REFRESH_MS)

    return () => window.clearInterval(id)
  }, [videoSrc, videoError, onAir, match.id])

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

  const compactScoreLine = (
    <div className="px-2 pt-1">
      <div className="truncate text-center text-[11px] text-white/80">
        {match.home}{' '}
        <span className="font-mono font-bold text-white">
          {synced.homeScore} – {synced.awayScore}
        </span>{' '}
        {match.away}
      </div>
    </div>
  )

  const videoBlock = (
    <div
      className={
        expanded
          ? 'live-video-frame live-video-clean relative min-h-[200px] shrink-0 overflow-hidden rounded-xl border border-white/10 bg-black shadow-inner'
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
      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <LiveScoreHeader
          league={match.league}
          home={match.home}
          away={match.away}
          homeScore={synced.homeScore}
          awayScore={synced.awayScore}
          matchMinute={commentary.matchMinute}
          isReplay={match.isFallback === true}
        />

        {videoBlock}
        <div className="flex shrink-0 items-center justify-between gap-2">
          <p className="text-[10px] text-white/35">Clean feed — commentary below</p>
          <button
            type="button"
            onClick={() => setMuted((m) => !m)}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-fluid-xs text-white/60 hover:bg-white/5 hover:text-white"
          >
            {muted ? 'Unmute' : 'Mute'}
          </button>
        </div>
        <LiveCommentaryStrip line={commentary.activeLine} kind={commentary.activeKind} />
        <GameStatsBar synced={synced} />
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
      {compactScoreLine}
      {videoBlock}
    </div>
  )
}
