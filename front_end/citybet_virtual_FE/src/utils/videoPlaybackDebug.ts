const LOG_PREFIX = '[video-debug]'
const MAX_EVENTS = 50

export type VideoDebugEventType =
  | 'attach'
  | 'detach'
  | 'url-probe'
  | 'error'
  | 'loadedmetadata'
  | 'canplay'
  | 'canplaythrough'
  | 'stalled'
  | 'waiting'
  | 'play'
  | 'play-rejected'
  | 'state'

export interface VideoDebugEvent {
  ts: number
  matchId: string
  type: VideoDebugEventType
  url?: string
  detail?: Record<string, unknown>
}

export interface VideoPlaybackFailure {
  code: 'http' | 'network' | 'decode' | 'unsupported' | 'aborted' | 'autoplay' | 'moov' | 'unknown'
  message: string
  httpStatus?: number
}

declare global {
  interface Window {
    __citybetVideoDebug?: {
      events: Record<string, VideoDebugEvent[]>
      lastFailure: Record<string, VideoPlaybackFailure | null>
      enabled: boolean
    }
  }
}

export function isVideoDebugEnabled(): boolean {
  if (import.meta.env.DEV) return true
  try {
    return localStorage.getItem('citybet_video_debug') === '1'
  } catch {
    return false
  }
}

function ensureStore(): NonNullable<Window['__citybetVideoDebug']> {
  if (!window.__citybetVideoDebug) {
    window.__citybetVideoDebug = { events: {}, lastFailure: {}, enabled: isVideoDebugEnabled() }
  }
  window.__citybetVideoDebug.enabled = isVideoDebugEnabled()
  return window.__citybetVideoDebug
}

function pushEvent(matchId: string, event: Omit<VideoDebugEvent, 'ts' | 'matchId'>): void {
  if (!isVideoDebugEnabled()) return
  const store = ensureStore()
  const entry: VideoDebugEvent = { ts: Date.now(), matchId, ...event }
  const list = store.events[matchId] ?? []
  list.push(entry)
  if (list.length > MAX_EVENTS) list.splice(0, list.length - MAX_EVENTS)
  store.events[matchId] = list
  console.info(LOG_PREFIX, matchId, event.type, event.detail ?? event.url ?? '')
}

export function logVideoDebug(
  matchId: string,
  type: VideoDebugEventType,
  detail?: Record<string, unknown>,
  url?: string,
): void {
  pushEvent(matchId, { type, detail, url })
}

export function setVideoDebugFailure(matchId: string, failure: VideoPlaybackFailure): void {
  if (!isVideoDebugEnabled()) return
  const store = ensureStore()
  store.lastFailure[matchId] = failure
  pushEvent(matchId, { type: 'state', detail: { failure } })
}

export function mediaErrorLabel(code: number | undefined): string {
  switch (code) {
    case MediaError.MEDIA_ERR_ABORTED:
      return 'aborted'
    case MediaError.MEDIA_ERR_NETWORK:
      return 'network'
    case MediaError.MEDIA_ERR_DECODE:
      return 'decode'
    case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
      return 'unsupported'
    default:
      return 'unknown'
  }
}

export function failureFromMediaError(
  el: HTMLVideoElement,
  url: string,
): VideoPlaybackFailure {
  const code = el.error?.code
  const networkState = el.networkState
  const readyState = el.readyState

  if (code === MediaError.MEDIA_ERR_NETWORK) {
    return {
      code: 'network',
      message: `Network error loading video (networkState=${networkState})`,
    }
  }
  if (code === MediaError.MEDIA_ERR_DECODE) {
    return {
      code: 'decode',
      message: 'Decode error — file may be incomplete or use an unsupported codec',
    }
  }
  if (code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) {
    return {
      code: 'unsupported',
      message: 'Format not supported — check Content-Type and codec (H.264 + moov-at-start)',
    }
  }
  if (code === MediaError.MEDIA_ERR_ABORTED) {
    return { code: 'aborted', message: 'Playback aborted' }
  }

  return {
    code: 'unknown',
    message: `Video error (code=${code ?? 'none'}, readyState=${readyState}, url=${url})`,
  }
}

export function failureMessage(failure: VideoPlaybackFailure | null): string {
  if (!failure) return 'Video failed to load'
  switch (failure.code) {
    case 'http':
      return failure.httpStatus === 404
        ? 'Video not found (HTTP 404)'
        : `Video unavailable (HTTP ${failure.httpStatus ?? 'error'})`
    case 'network':
      return 'Network error — check API proxy and connection'
    case 'decode':
      return 'Decode error — video may still be rendering'
    case 'unsupported':
      return 'Unsupported format — waiting for streamable MP4'
    case 'autoplay':
      return 'Autoplay blocked — tap play or unmute'
    case 'moov':
      return 'Video not streamable yet — metadata still being written'
    case 'aborted':
      return 'Playback aborted'
    default:
      return failure.message || 'Video failed to load'
  }
}

export async function probeVideoUrl(
  matchId: string,
  url: string,
): Promise<{ ok: boolean; status: number; headers: Record<string, string>; moovAtStart: boolean }> {
  const headers: Record<string, string> = {}
  let status = 0
  let moovAtStart = false

  try {
    const head = await fetch(url, { method: 'HEAD' })
    status = head.status
    head.headers.forEach((v, k) => {
      headers[k] = v
    })
    logVideoDebug(matchId, 'url-probe', { phase: 'HEAD', status, headers }, url)

    const range = await fetch(url, {
      method: 'GET',
      headers: { Range: 'bytes=0-65535' },
    })
    if (!status) status = range.status
    range.headers.forEach((v, k) => {
      headers[k] = v
    })

    if (range.ok || range.status === 206) {
      const buf = await range.arrayBuffer()
      const bytes = new Uint8Array(buf)
      for (let i = 0; i < bytes.length - 3; i++) {
        if (bytes[i] === 0x6d && bytes[i + 1] === 0x6f && bytes[i + 2] === 0x6f && bytes[i + 3] === 0x76) {
          moovAtStart = true
          break
        }
      }
    }

    logVideoDebug(
      matchId,
      'url-probe',
      {
        phase: 'RANGE',
        status: range.status,
        contentType: headers['content-type'],
        contentLength: headers['content-length'],
        acceptRanges: headers['accept-ranges'],
        contentRange: headers['content-range'],
        moovAtStart,
      },
      url,
    )

    const ok = (range.ok || range.status === 206) && moovAtStart
    return { ok, status: range.status || status, headers, moovAtStart }
  } catch (err) {
    logVideoDebug(matchId, 'url-probe', { error: String(err) }, url)
    return { ok: false, status, headers, moovAtStart }
  }
}

export function attachVideoPlaybackDebug(
  el: HTMLVideoElement,
  matchId: string,
  url: string,
): () => void {
  if (!isVideoDebugEnabled()) return () => {}

  logVideoDebug(matchId, 'attach', { url }, url)

  const on = (type: VideoDebugEventType, handler: EventListener) => {
    el.addEventListener(type, handler)
    return () => el.removeEventListener(type, handler)
  }

  const cleanups: Array<() => void> = []

  cleanups.push(
    on('error', () => {
      const failure = failureFromMediaError(el, url)
      setVideoDebugFailure(matchId, failure)
      logVideoDebug(matchId, 'error', {
        mediaErrorCode: el.error?.code,
        mediaErrorMessage: el.error?.message,
        networkState: el.networkState,
        readyState: el.readyState,
      }, url)
    }),
  )

  for (const evt of ['loadedmetadata', 'canplay', 'canplaythrough', 'stalled', 'waiting', 'play'] as const) {
    cleanups.push(
      on(evt, () => {
        logVideoDebug(matchId, evt, {
          currentTime: el.currentTime,
          duration: el.duration,
          readyState: el.readyState,
          networkState: el.networkState,
          paused: el.paused,
        }, url)
      }),
    )
  }

  const origPlay = el.play.bind(el)
  el.play = function patchedPlay(...args: Parameters<HTMLMediaElement['play']>) {
    const result = origPlay(...args)
    void result.catch((err: unknown) => {
      const name = err instanceof DOMException ? err.name : 'Error'
      const isAutoplay = name === 'NotAllowedError'
      const failure: VideoPlaybackFailure = isAutoplay
        ? { code: 'autoplay', message: 'Autoplay blocked by browser policy' }
        : { code: 'unknown', message: `play() rejected: ${name}` }
      setVideoDebugFailure(matchId, failure)
      logVideoDebug(matchId, 'play-rejected', { name, message: String(err) }, url)
    })
    return result
  }

  return () => {
    logVideoDebug(matchId, 'detach', { url }, url)
    cleanups.forEach((fn) => fn())
    el.play = origPlay
  }
}
