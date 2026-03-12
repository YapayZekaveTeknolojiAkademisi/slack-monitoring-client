import json 
from queue import Queue
from datetime import datetime, timezone
import logging
import logging.config
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from typing import Optional

# Tüm proje tek logger kullanır.
APP_LOGGER_NAME = "app"


def get_logger() -> logging.Logger:
    """Proje genelinde kullanılacak tek app logger'ı döner."""
    return logging.getLogger(APP_LOGGER_NAME)


_log_queue: Queue = Queue(maxsize=-1)
_queue_handler: Optional[QueueHandler] = None
_queue_listener: Optional[QueueListener] = None


def _extract_event_payload(record: logging.LogRecord, attr_name: str) -> Optional[dict]:
    """
    Ortak yardımcı:
    - record.<attr_name> bir dict ise onu döner
    - veya record.metadata[attr_name] bir dict ise onu döner
    Aksi halde None.
    """
    if hasattr(record, attr_name):
        value = getattr(record, attr_name)
        if isinstance(value, dict):
            return value

    if hasattr(record, "metadata"):
        meta = getattr(record, "metadata")
        if isinstance(meta, dict):
            value = meta.get(attr_name)
            if isinstance(value, dict):
                return value

    return None


class ConsoleFormatter(logging.Formatter):
    """Konsol için sade, okunaklı format."""
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts} | {record.levelname:<7} | {record.getMessage()}"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage()
        }

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)

class SystemFileFormatter(logging.Formatter):
    """Sade, okunaklı: tarih/saat | seviye | mesaj."""
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        return f"{ts} | {record.levelname:<7} | {record.getMessage()}"

class QueueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # Renk kodları (sadece event tipi için)
        _RED     = "\x1b[31m"
        _GREEN   = "\x1b[32m"
        _YELLOW  = "\x1b[33m"
        _MAGENTA = "\x1b[35m"  # turuncuya yakın ton
        _RESET   = "\x1b[0m"

        # Önce queue_event payload'unu bul
        payload = _extract_event_payload(record, "queue_event")
        # Ek olarak, doğrudan dict msg geldiyse onu da destekle
        if payload is None and isinstance(record.msg, dict):
            payload = record.msg

        # Dict değilse sadece timestamp + mesajı yaz
        if not isinstance(payload, dict):
            return f"[{timestamp}] {record.getMessage()}"

        event_type = payload.get("event_type") or "-"
        user_id = payload.get("user_id") or "-"
        channel_id = payload.get("channel_id") or "-"
        ts = payload.get("ts") or "-"
        thread_ts = payload.get("thread_ts") or "-"
        text = payload.get("text") or ""

        # Event tipine göre renk seçimi
        et_lower = str(event_type).lower()

        # listener.py'deki tabloya göre:
        # - member_left    → kanaldan ayrılma (kırmızı)
        # - member_joined  → kanala katılma (yeşil)
        # - message        → normal mesaj (sarı)
        # - thread_reply   → thread mesajı (turuncu ton)
        # - reaction_added → reaction eklendi (sarıya yakın)
        if et_lower in {"member_left", "channel_left", "leave_channel", "kanaldan_cikma"}:
            event_color = _RED
        elif et_lower in {"member_joined", "channel_joined", "join_channel", "kanala_girme"}:
            event_color = _GREEN
        elif et_lower in {"message", "mesaj", "reaction_added"}:
            event_color = _YELLOW
        elif et_lower in {"thread_reply", "thread", "thread_message"}:
            event_color = _MAGENTA
        else:
            event_color = _RESET

        colored_event = f"event={event_color}{event_type}{_RESET}"

        parts = [
            f"[{timestamp}]",
            colored_event,
            f"user={user_id}",
            f"channel={channel_id}",
            f"ts={ts}",
        ]

        if thread_ts != "-":
            parts.append(f"thread_ts={thread_ts}")

        base = " ".join(parts)

        if text:
            return f"{base} | {text}"
        return base

class ErrorOnlyFilter(logging.Filter):
    """
    error.log için:
    - Sadece ERROR ve üzeri seviyeleri kabul eder.
    - Event extras'ı (queue/analyse/remote) olup olmamasına bakmaz,
      böylece her türlü hata JSON olarak error.log'a düşer.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


class QueueEventFilter(logging.Filter):
    """
    Sadece queue ile ilgili kayıtları geçirir.
    Beklenen alan: extra={"queue_event": {...}} veya metadata["queue_event"].
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return hasattr(record, "queue_event")


class SystemOnlyFilter(logging.Filter):
    """
    Sadece queue dışı (sistem) kayıtları geçirir.
    queue_event içermeyen loglar console'a gider.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not hasattr(record, "queue_event")


def _build_logging_config(log_dir: str = "logs") -> dict:
    """logs/ altında 3 dosya: system.log, error.log, queue.log — hepsi RotatingFileHandler, kendi formatter'ı."""
    _file_kw = {"maxBytes": 10485760, "backupCount": 5, "encoding": "utf-8"}
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {"()": ConsoleFormatter},
            "system_file": {"()": SystemFileFormatter},
            "json": {"()": JsonFormatter},
            "queue": {"()": QueueFormatter},
        },
        "filters": {
            "system_only": {"()": SystemOnlyFilter},
            "error_only": {"()": ErrorOnlyFilter},
            "queue_event_only": {"()": QueueEventFilter},
        },
        "handlers": {
            "system_file": {
                "()": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "system_file",
                "filters": ["system_only"],
                "filename": f"{log_dir}/system.log",
                **_file_kw,
            },
            "error_file": {
                "()": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filters": ["error_only"],
                "filename": f"{log_dir}/error.log",
                **_file_kw,
            },
            "queue_file": {
                "()": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "queue",
                "filters": ["queue_event_only"],
                "filename": f"{log_dir}/queue.log",
                **_file_kw,
            },
        },
        "loggers": {
            APP_LOGGER_NAME: {
                "level": "INFO",
                "handlers": ["system_file", "error_file", "queue_file"],
                "propagate": False,
            },
        },
    }


LOGGING_CONFIG = _build_logging_config()


def setup_logging(config: dict):
    global _queue_listener, _log_queue

    logging.config.dictConfig(config)

    # Logger'da sadece QueueHandler kalsın; dosya handler'ları QueueListener'a ver (çift yazı önlenir)
    file_handlers = []
    for logger_name in config.get("loggers", {}):
        logger = logging.getLogger(logger_name)
        for h in list(logger.handlers):
            if not isinstance(h, QueueHandler):
                file_handlers.append(h)
                logger.removeHandler(h)
        if not any(isinstance(h, QueueHandler) for h in logger.handlers):
            logger.addHandler(QueueHandler(_log_queue))

    if _queue_listener is not None:
        _queue_listener.stop()

    _queue_listener = QueueListener(
        _log_queue,
        *file_handlers,
        respect_handler_level=True,
    )
    _queue_listener.start()


def stop_logging():
    global _queue_listener
    if _queue_listener is not None:
        # Listener'ı durdurmadan önce kuyruğun boşalmasını bekler
        _queue_listener.stop()
        _queue_listener = None

    # Logging modülünü kapatır (tüm handler'ları temizler)
    logging.shutdown()

# Uygulama başlarken tam logging config ile setup_logging(config) çağrılmalı.
# Import anında LOGGING_CONFIG'de loggers/handlers olmadığı için setup yapılmıyor.