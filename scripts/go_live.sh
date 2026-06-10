#!/usr/bin/env bash
# Go-live: deps, reset virtual clock, start platform clean.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== CityBet Virtuals — GO LIVE ==="

"$ROOT/venv/bin/pip" install -q -r requirements.txt
"$ROOT/venv/bin/pip" uninstall -y duckduckgo-search 2>/dev/null || true

"$ROOT/run.sh" stop
sleep 2

"$ROOT/venv/bin/python3" "$ROOT/scripts/go_live.py"

"$ROOT/run.sh"
echo ""
echo "=== GO LIVE complete ==="
echo "  API  → http://localhost:8000"
echo "  FE   → cd front_end/citybet_virtual_FE && npm run dev"
echo "  Status → venv/bin/python3 scripts/platform_status.py"
