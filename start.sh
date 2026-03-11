#!/usr/bin/env bash
# Slack Monitoring System — başlatma
set -e

cd "$(dirname "$0")"
ROOT="$PWD"

export PYTHONPATH="$ROOT"
export LOG_DIR="${LOG_DIR:-logs}"

PIDFILE="$ROOT/.pid"
LOGFILE="$ROOT/logs/start.log"

mkdir -p "$LOG_DIR"

if [ -f "$PIDFILE" ]; then
  OLD_PID=$(cat "$PIDFILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Zaten çalışıyor (PID: $OLD_PID). Durdurmak için: ./stop.sh"
    exit 1
  fi
  rm -f "$PIDFILE"
fi

echo "Başlatılıyor (log_dir=$LOG_DIR)…"
python -m src.main >> "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "Başlatıldı. PID: $(cat "$PIDFILE"). Durdurmak için: ./stop.sh"
