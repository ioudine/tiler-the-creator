#!/usr/bin/env bash
set -euo pipefail

# stop_gui_codespace.sh
# Stops services started by run_gui_codespace.sh

PIDS_FILE="${PIDS_FILE:-/tmp/tiler_gui_pids.txt}"
TMPDIR="${TMPDIR:-/tmp/tiler-vnc}"

if [ -f "$PIDS_FILE" ]; then
  echo "Stopping processes listed in $PIDS_FILE"
  while read -r pid; do
    if [ -z "$pid" ]; then
      continue
    fi
    if kill -0 "$pid" 2>/dev/null; then
      echo "Killing PID $pid"
      kill "$pid" || true
    fi
  done < "$PIDS_FILE"
  rm -f "$PIDS_FILE"
else
  echo "No PID file found at $PIDS_FILE; attempting to stop known services by name"
  pkill -f websockify || true
  pkill -f x11vnc || true
  pkill -f Xvfb || true
  pkill -f fluxbox || true
fi

echo "Cleanup temporary files in $TMPDIR"
rm -rf "$TMPDIR" || true

echo "Stopped GUI services."
