"""
Merkezi giriş noktası: start, stop ve yardımcılar.
"""
from __future__ import annotations

import os
import signal
import sys

from src.core.logger import (
    _build_logging_config,
    get_logger,
    setup_logging,
    stop_logging,
)
from src.listener import queue_server, start as listener_start, stop as listener_stop

LOG_DIR = os.environ.get("LOG_DIR", "logs")


# -----------------------------------------------------------------------------
# Yardımcılar
# -----------------------------------------------------------------------------


def _ensure_log_dir() -> None:
    """logs dizinini oluşturur."""
    os.makedirs(LOG_DIR, exist_ok=True)


def _register_signal_handlers() -> None:
    """SIGINT/SIGTERM için graceful shutdown kaydeder."""
    def _on_signal(_signum: int | None, _frame) -> None:
        logger = get_logger()
        logger.info("Kapatılıyor.")
        stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)


# -----------------------------------------------------------------------------
# Ana fonksiyonlar: start, stop
# -----------------------------------------------------------------------------


def start() -> None:
    """Uygulamayı başlatır: log dizini, logging, sinyaller, listener (bloklayıcı)."""
    _ensure_log_dir()
    setup_logging(_build_logging_config(LOG_DIR))
    logger = get_logger()
    logger.info("Başlatılıyor.")
    _register_signal_handlers()
    try:
        listener_start()
    except Exception:
        logger.exception("Listener çöktü.")
        stop()
        sys.exit(1)


def stop() -> None:
    """Uygulamayı kapatır: listener, queue, logging."""
    logger = get_logger()
    try:
        listener_stop()
    except Exception as e:
        logger.warning("Listener kapatılırken hata: %s", e)
    try:
        queue_server.stop()
    except Exception as e:
        logger.warning("QueueServer kapatılırken hata: %s", e)
    try:
        stop_logging()
    except Exception as e:
        logger.warning("Logging kapatılırken hata: %s", e)


if __name__ == "__main__":
    start()
