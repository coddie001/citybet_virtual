#!/usr/bin/env python3
"""Extract files from Cursor agent transcript Write tool calls."""
import json
import re
import sys
from pathlib import Path

TRANSCRIPT = Path(
    "/mnt/c/Users/HP/.cursor/projects/wsl-localhost-FedoraLinux-42-home-Warta-projects-citybet-virtuals"
    "/agent-transcripts/17da5c79-b2b6-401e-9665-2f927bbda79c/17da5c79-b2b6-401e-9665-2f927bbda79c.jsonl"
)
ROOT = Path(__file__).resolve().parents[1]
WIN_ROOT = "\\\\wsl.localhost\\FedoraLinux-42\\home\\Warta\\projects\\citybet_virtuals"


def to_local(path: str) -> Path:
    path = path.replace(WIN_ROOT, str(ROOT))
    path = path.replace("\\", "/")
    if path.startswith("/home/Warta/projects/citybet_virtuals"):
        path = str(ROOT) + path.split("citybet_virtuals", 1)[1]
    return Path(path)


def main():
    transcript = TRANSCRIPT
    if not transcript.is_file():
        transcript = Path.home() / ".cursor/projects/wsl-localhost-FedoraLinux-42-home-Warta-projects-citybet-virtuals/agent-transcripts/17da5c79-b2b6-401e-9665-2f927bbda79c/17da5c79-b2b6-401e-9665-2f927bbda79c.jsonl"
    if not transcript.is_file():
        print(f"Transcript not found: {transcript}", file=sys.stderr)
        sys.exit(1)

    restored = {}
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        if '"Write"' not in line and '"name":"Write"' not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        for block in obj.get("message", {}).get("content", []):
            if block.get("type") != "tool_use" or block.get("name") != "Write":
                continue
            inp = block.get("input", {})
            path = inp.get("path", "")
            contents = inp.get("contents", "")
            if not path or not contents:
                continue
            local = to_local(path)
            # keep latest write per path
            restored[str(local)] = (local, contents)

    count = 0
    for local, contents in restored.values():
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(contents, encoding="utf-8")
        print(f"RESTORED {local}")
        count += 1
    print(f"\nTotal: {count} files from transcript")


if __name__ == "__main__":
    main()
