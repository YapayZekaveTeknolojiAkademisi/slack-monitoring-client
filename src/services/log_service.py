from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.core.logger import get_logger
from src.core.settings import get_settings


class LogService:
    """
    Logger servisi:
    - error.log dosyasındaki JSON error kayıtlarını okur
    - İstenilen sayıda kaydı liste olarak döndürür
    """

    def __init__(self) -> None:
        self._logger = get_logger()
        self._settings = get_settings()
        self._error_log_path = Path(self._settings.log_dir) / "error.log"

    def get_error_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        error.log içindeki son `limit` adet JSON log kaydını döndürür.
        Her satır bir JSON obje olarak parse edilir; parse edilemeyen satırlar atlanır.
        """
        try:
            if not self._error_log_path.exists():
                return []

            with self._error_log_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()

            lines = lines[-limit:] if limit > 0 else lines

            logs: List[Dict[str, Any]] = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        logs.append(data)
                except json.JSONDecodeError:
                    continue

            return logs
        except Exception:
            self._logger.exception("Failed to read error logs")
            return []
