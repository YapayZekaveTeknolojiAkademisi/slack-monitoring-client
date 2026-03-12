"""
Merkezi giriş noktası: startup, main, stop.
python -m src ile API (uvicorn) + Slack listener (arka planda) birlikte başlar.
"""
from __future__ import annotations

import asyncio
import os
import threading
import uvicorn

from src.core.logger import (
    _build_logging_config,
    get_logger,
    setup_logging,
    stop_logging,
)
from src.core.settings import get_settings
from src.listener import queue_server, start as listener_start, stop as listener_stop

_listener_thread: threading.Thread | None = None


# -----------------------------------------------------------------------------
# Startup
# -----------------------------------------------------------------------------


def _ensure_log_dir(log_dir: str) -> None:
    """Log dizinini oluşturur."""
    os.makedirs(log_dir, exist_ok=True)


async def _startup() -> None:
    """
    Uygulama başlamadan önce bir kez çalışır:
    - Log dizinini oluşturur
    - Queue manager'ı başlatır
    """
    logger = get_logger()
    logger.info("Startup: starting")
    settings = get_settings()
    _ensure_log_dir(settings.log_dir)
    logger.info("Startup: log dir ready")
    queue_server.start()
    logger.info("Startup: completed")


# -----------------------------------------------------------------------------
# Main & stop
# -----------------------------------------------------------------------------


def stop() -> None:
    """Listener, queue ve logging'i kapatır."""
    global _listener_thread
    logger = get_logger()
    try:
        listener_stop()
    except Exception as e:
        logger.warning("Listener kapatılırken hata: %s", e)
    if _listener_thread is not None:
        _listener_thread.join(timeout=5.0)
        _listener_thread = None
    try:
        queue_server.stop()
    except Exception as e:
        logger.warning("QueueServer kapatılırken hata: %s", e)
    try:
        stop_logging()
    except Exception as e:
        logger.warning("Logging kapatılırken hata: %s", e)


def main() -> None:
    """Uygulamayı uvicorn + Slack listener ile başlatır."""
    global _listener_thread
    settings = get_settings()
    setup_logging(_build_logging_config(settings.log_dir))
    logger = get_logger()
    logger.info("Slack Monitoring System starting")

    asyncio.run(_startup())

    _listener_thread = threading.Thread(target=listener_start, daemon=False)
    _listener_thread.start()
    logger.info("Slack listener running in background")

    try:
        uvicorn.run(
            "src.api.app:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=False,
        )
    finally:
        logger.info("Slack Monitoring System stopping")
        stop()


if __name__ == "__main__":
    main()
