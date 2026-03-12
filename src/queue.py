from __future__ import annotations

import queue
from multiprocessing.managers import BaseManager
from typing import Any

from src.core.logger import get_logger
from src.core.settings import get_settings
from src.core.singleton import SingletonMeta

logger = get_logger()
_SETTINGS = get_settings()

QUEUE_HOST = _SETTINGS.queue_host
QUEUE_PORT = _SETTINGS.queue_port
QUEUE_AUTHKEY = _SETTINGS.queue_authkey


# Kuyruk payload formatı (tüm consumer'lar bu yapıyı beklemeli):
# {
# "event_type": str, 
# "user_id": str|None, 
# "channel_id": str|None, 
# "ts": str|None,
# "thread_ts": str|None, 
# "text": str|None, ...event'e özel alanlar
# }
# Zorunlu alan: event_type. Diğerleri event tipine göre optional.


def build_message_event(event_type: str, **kwargs: Any) -> dict[str, Any]:
    """Slack event'ini kuyruk için standart dict formatına dönüştürür."""
    return {"event_type": event_type, **kwargs}


def _make_shared_queue() -> queue.Queue:
    """Manager tarafından paylaşılacak queue factory'si."""
    return queue.Queue()

class _QueueManager(BaseManager):
    """Modül seviyesinde tanımlı; multiprocessing pickle için gerekli."""

_QueueManager.register("get_queue", callable=_make_shared_queue)


class QueueServer(metaclass=SingletonMeta):
    def __init__(
        self,
        host: str = QUEUE_HOST,
        port: int = QUEUE_PORT,
        authkey: bytes = QUEUE_AUTHKEY,
    ) -> None:
        self._manager = _QueueManager(address=(host, port), authkey=authkey)
        self._queue: queue.Queue | None = None

    def start(self) -> None:
        """
        Queue manager'ı başlatır ve paylaşılan kuyruğu hazırlar.
        Zaten başlatılmışsa tekrar başlatmaz (idempotent).
        """
        if self._queue is not None:
            return
        try:
            self._manager.start()
            self._queue = self._manager.get_queue()  # type: ignore[attr-defined]
            logger.info("Queue hazır.")
        except Exception:
            logger.exception("Queue manager başlatılamadı.")
            raise

    def stop(self) -> None:
        try:
            logger.info("Queue kapatıldı.")
            self._manager.shutdown()
        except Exception:
            logger.exception("Queue manager kapatılırken hata.")
            raise

    @property
    def queue(self) -> queue.Queue:
        if self._queue is None:
            logger.error("Queue henüz başlatılmadı.")
            raise RuntimeError("QueueServer başlatılmadı. Önce start() çağırın.")
        return self._queue

    def put(self, item: dict[str, Any]) -> None:
        """Standart formata dönüştürülmüş event'i kuyruğa ekler."""
        try:
            self.queue.put(item)
            event_type = item.get("event_type", "-") if isinstance(item, dict) else "-"
            logger.debug("Kuyruğa event eklendi", extra={"event_type": event_type, "queue_size": self.queue.qsize()})
        except Exception:
            logger.exception("put() başarısız (event_type=%s)", item.get("event_type", "-") if isinstance(item, dict) else "-")
            raise

    def get(self, block: bool = True, timeout: float | None = None) -> dict[str, Any]:
        try:
            item = self.queue.get(block=block, timeout=timeout)
            event_type = item.get("event_type", "-") if isinstance(item, dict) else "-"
            logger.debug("Kuyruktan event alındı", extra={"event_type": event_type, "queue_size": self.queue.qsize()})
            return item
        except queue.Empty:
            raise
        except Exception:
            logger.exception("get() başarısız.")
            raise

    def size(self) -> int:
        return self.queue.qsize()