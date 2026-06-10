"""Range-aware MP4 streaming — no 304/etag (breaks HTML5 video)."""
import re
from pathlib import Path
from typing import Iterator, Optional

from fastapi import HTTPException, Request
from starlette.responses import Response, StreamingResponse

_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
_CHUNK = 256 * 1024


def _parse_range(range_header: str, size: int) -> Optional[tuple[int, int]]:
    match = _RANGE_RE.match(range_header.strip())
    if not match:
        return None
    start_s, end_s = match.groups()
    if start_s == "" and end_s == "":
        return None
    if start_s == "":
        # suffix range: bytes=-500
        suffix = int(end_s)
        if suffix <= 0:
            return None
        start = max(0, size - suffix)
        return start, size - 1
    start = int(start_s)
    end = int(end_s) if end_s else size - 1
    if start >= size:
        return None
    end = min(end, size - 1)
    if end < start:
        return None
    return start, end


def _iter_file(path: Path, start: int, end: int) -> Iterator[bytes]:
    with path.open("rb") as fh:
        fh.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = fh.read(min(_CHUNK, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def _range_response_headers(
    path: Path, request: Request, size: int, base_headers: dict
) -> tuple[int, dict]:
    """Return (status_code, headers) honoring Range on GET/HEAD."""
    range_header = request.headers.get("range")
    if range_header:
        parsed = _parse_range(range_header, size)
        if parsed:
            start, end = parsed
            length = end - start + 1
            return 206, {
                **base_headers,
                "Content-Length": str(length),
                "Content-Range": f"bytes {start}-{end}/{size}",
            }
    return 200, {**base_headers, "Content-Length": str(size)}


def head_mp4(path: Path, request: Request) -> Response:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Video file not found")

    size = path.stat().st_size
    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Content-Disposition": 'inline; filename="{}"'.format(path.name),
    }
    status, headers = _range_response_headers(path, request, size, base_headers)
    return Response(status_code=status, headers=headers)


def stream_mp4(path: Path, request: Request) -> StreamingResponse:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Video file not found")

    size = path.stat().st_size
    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Content-Disposition": 'inline; filename="{}"'.format(path.name),
    }

    range_header = request.headers.get("range")
    if range_header:
        parsed = _parse_range(range_header, size)
        if parsed:
            start, end = parsed
            length = end - start + 1
            headers = {
                **base_headers,
                "Content-Length": str(length),
                "Content-Range": f"bytes {start}-{end}/{size}",
            }
            return StreamingResponse(
                _iter_file(path, start, end),
                status_code=206,
                headers=headers,
            )

    headers = {**base_headers, "Content-Length": str(size)}
    return StreamingResponse(
        _iter_file(path, 0, size - 1),
        status_code=200,
        headers=headers,
    )
