#!/usr/bin/env bash
#
# Launch audio-server in the background with --preload, then wait until it
# accepts connections. Writes the PID to /tmp/audio-server.pid so the
# caller can kill it cleanly later.
#
# Usage:
#   ./start_server.sh              # port 8080, defaults
#   PORT=9000 ./start_server.sh    # override port
#   AUDIO_SERVER_BIN=/path/audio-server ./start_server.sh
#
# To stop:
#   kill "$(cat /tmp/audio-server.pid)"

set -euo pipefail

PORT="${PORT:-8080}"
PID_FILE="${PID_FILE:-/tmp/audio-server.pid}"
LOG_FILE="${LOG_FILE:-/tmp/audio-server.log}"
DEADLINE_SEC="${DEADLINE_SEC:-120}"  # preload of all models can take ~1-2 min cold

# Locate the binary. Homebrew install lands it on PATH; source builds put
# it under .build/release/.
if [[ -n "${AUDIO_SERVER_BIN:-}" ]]; then
    BIN="$AUDIO_SERVER_BIN"
elif command -v audio-server >/dev/null 2>&1; then
    BIN="$(command -v audio-server)"
elif [[ -x ".build/release/audio-server" ]]; then
    BIN=".build/release/audio-server"
else
    echo "ERROR: audio-server binary not found." >&2
    echo "Install: brew tap soniqo/speech https://github.com/soniqo/speech-swift && brew install speech" >&2
    echo "Or build: cd speech-swift && make build" >&2
    exit 1
fi

# If something is already on the port, bail rather than fork another instance.
if lsof -iTCP:"$PORT" -sTCP:LISTEN -nP >/dev/null 2>&1; then
    echo "audio-server (or something) is already listening on port $PORT." >&2
    echo "If it's a stale instance: kill \$(cat $PID_FILE) 2>/dev/null; or lsof -iTCP:$PORT" >&2
    exit 1
fi

echo "Starting $BIN --port $PORT --preload"
echo "  log:  $LOG_FILE"
echo "  pid:  $PID_FILE"
nohup "$BIN" --port "$PORT" --preload >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

# Wait until the port responds. Preload pulls every model into memory which
# can take a while on a cold cache (first run downloads ~5+ GB of weights).
echo "Waiting up to ${DEADLINE_SEC}s for audio-server to accept connections..."
elapsed=0
while [[ $elapsed -lt $DEADLINE_SEC ]]; do
    if curl -sS --max-time 1 "http://localhost:$PORT/" >/dev/null 2>&1; then
        echo "audio-server is up on port $PORT (pid $(cat "$PID_FILE"))."
        exit 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
    if (( elapsed % 10 == 0 )); then
        echo "  ... still waiting (${elapsed}s); tail of log:"
        tail -n 3 "$LOG_FILE" | sed 's/^/    /'
    fi
done

echo "ERROR: audio-server did not become ready within ${DEADLINE_SEC}s." >&2
echo "Check $LOG_FILE for details." >&2
exit 1
