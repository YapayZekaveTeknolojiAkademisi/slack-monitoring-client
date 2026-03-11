#!/usr/bin/env bash
# Slack Monitoring System — durdurma (graceful: SIGTERM)
set -e

cd "$(dirname "$0")"
PIDFILE="$PWD/.pid"

if [ ! -f "$PIDFILE" ]; then
  echo "PID dosyası yok (.pid). Uygulama çalışmıyor olabilir."
  exit 0
fi

PID=$(cat "$PIDFILE")
rm -f "$PIDFILE"

if ! kill -0 "$PID" 2>/dev/null; then
  echo "Process zaten kapalı (PID: $PID)."
  exit 0
fi

echo "Durduruluyor (PID: $PID)…"
kill -TERM "$PID" 2>/dev/null || true

# Kısa süre bekle, hâlâ çalışıyorsa zorla kapat
for _ in 1 2 3 4 5; do
  sleep 1
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "Durduruldu."
    exit 0
  fi
done

echo "SIGTERM yeterli olmadı, SIGKILL gönderiliyor."
kill -9 "$PID" 2>/dev/null || true
echo "Durduruldu."
