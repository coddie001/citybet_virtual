#!/usr/bin/env bash
# CityBet Virtuals — start/stop API, coordinator, and simulation worker
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${SCRIPT_DIR}/venv/bin/python3"
PIDFILE_API="${SCRIPT_DIR}/.api.pid"
PIDFILE_WORKER="${SCRIPT_DIR}/.worker.pid"
PIDFILE_COORDINATOR="${SCRIPT_DIR}/.coordinator.pid"
LOG_DIR="${SCRIPT_DIR}/logs"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

API_HEALTH_URL="http://127.0.0.1:8000/health"

api_health_ok() {
    curl -sf --connect-timeout 1 --max-time 2 "$API_HEALTH_URL" >/dev/null 2>&1
}

api_port_listening() {
    if command -v ss >/dev/null 2>&1; then
        ss -ltn 2>/dev/null | grep -q ':8000 '
    elif command -v nc >/dev/null 2>&1; then
        nc -z 127.0.0.1 8000 2>/dev/null
    else
        return 1
    fi
}

api_running() {
    api_health_ok || api_port_listening
}

worker_running() { pgrep -f "venv/bin/python3 -m workers.game_simulator --mode all" >/dev/null 2>&1; }
coordinator_running() { pgrep -f "workers.platform_coordinator" >/dev/null 2>&1; }

count_workers() {
    pgrep -f "venv/bin/python3 -m workers.game_simulator --mode all" 2>/dev/null | wc -l | tr -d '[:space:]'
}

stop_pid() {
    local pidfile="$1"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid="$(cat "$pidfile")"
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 1
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pidfile"
    fi
}

kill_stale_api() {
    stop_pid "$PIDFILE_API"
    pkill -f "uvicorn main:app" 2>/dev/null || true
    sleep 1
}

wait_for_api_health() {
    local attempt
    for attempt in $(seq 1 10); do
        if api_health_ok; then
            return 0
        fi
        sleep 0.5
    done
    return 1
}

kill_all_orphans() {
    pkill -f "workers.game_simulator" 2>/dev/null || true
}

start_api() {
    if api_health_ok; then
        log "[API] Already running (healthy)."
        return 0
    fi
    if pgrep -f "uvicorn main:app" >/dev/null 2>&1 || api_port_listening; then
        log "[API] Unhealthy or stale process on :8000; restarting …"
        kill_stale_api
    fi
    log "[API] Starting FastAPI on :8000 …"
    nohup "$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port 8000 \
        >> "$LOG_DIR/api.log" 2>&1 &
    echo $! > "$PIDFILE_API"
    log "[API] PID $! → logs/api.log"
    if wait_for_api_health; then
        log "[API] Ready — $API_HEALTH_URL"
    else
        log "[API] WARNING: /health not OK after 5s — see logs/api.log"
        return 1
    fi
}

start_coordinator() {
    if coordinator_running; then
        log "[Coordinator] Already running."
        return 0
    fi
    log "[Coordinator] Starting platform coordinator …"
    nohup "$PYTHON" -m workers.platform_coordinator \
        >> "$LOG_DIR/coordinator.log" 2>&1 &
    echo $! > "$PIDFILE_COORDINATOR"
    log "[Coordinator] PID $! → logs/coordinator.log"
}

start_worker() {
    local count
    count="$(pgrep -fc 'workers\.game_simulator' 2>/dev/null | tr -d '[:space:]' || true)"
    count="${count:-0}"
    if [[ "$count" =~ ^[0-9]+$ ]] && [[ "$count" -gt 1 ]]; then
        log "[Worker] Found $count duplicate workers; stopping extras …"
        kill_all_orphans
        sleep 1
        count=0
    fi
    if [[ "$count" =~ ^[0-9]+$ ]] && [[ "$count" -eq 1 ]]; then
        log "[Worker] Already running."
        return 0
    fi
    log "[Worker] Starting simulation queue …"
    nohup "$PYTHON" -m workers.game_simulator --mode all \
        >> "$LOG_DIR/worker.log" 2>&1 &
    echo $! > "$PIDFILE_WORKER"
    log "[Worker] PID $! → logs/worker.log"
}

start_worker_gwk() {
    local gwk="${1:-1}"
    log "[Worker] One-shot gameweek $gwk …"
    "$PYTHON" -m workers.game_simulator --mode gameweek --gameweek "$gwk"
}

CMD="${1:-all}"
shift || true

case "$CMD" in
    api)
        start_api
        ;;
    worker)
        if [[ "${1:-}" == "--gwk" ]]; then
            start_worker_gwk "${2:-1}"
        else
            start_worker
        fi
        ;;
    coordinator)
        start_coordinator
        ;;
    stop)
        stop_pid "$PIDFILE_API"
        stop_pid "$PIDFILE_WORKER"
        stop_pid "$PIDFILE_COORDINATOR"
        kill_all_orphans
        pkill -f "workers.platform_coordinator" 2>/dev/null || true
        pkill -f "uvicorn main:app" 2>/dev/null || true
        log "All processes stopped."
        ;;
    restore)
        "$PYTHON" scripts/restore_from_pyc.py
        ;;
    all|*)
        if [[ ! -f "$SCRIPT_DIR/main.py" ]]; then
            log "main.py missing — running bytecode recovery first …"
            "$PYTHON" scripts/restore_from_pyc.py
        fi
        start_api
        sleep 1
        start_coordinator
        sleep 1
        start_worker
        log ""
        log "=============================="
        log " CityBet Virtuals is RUNNING  "
        log " API  → http://0.0.0.0:8000   "
        log " Docs → http://0.0.0.0:8000/docs"
        log " Tail API         : tail -f $LOG_DIR/api.log"
        log " Tail Coordinator : tail -f $LOG_DIR/coordinator.log"
        log " Tail Worker      : tail -f $LOG_DIR/worker.log"
        log " Stop all         : ./run.sh stop"
        log "=============================="
        ;;
esac