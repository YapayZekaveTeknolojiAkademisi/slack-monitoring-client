"""Thread-safe Singleton metaclass."""
from __future__ import annotations

import threading
from typing import Any, Dict, TypeVar

T = TypeVar("T")


class SingletonMeta(type):
    """
    Thread-safe (iş parçacığı güvenli) Singleton meta sınıfı.
    Bu sınıfı 'metaclass' olarak kullanan sınıflardan yalnızca bir örnek oluşturulabilir.
    """

    _instances: Dict[type, Any] = {}
    _lock: threading.RLock = threading.RLock()

    def __call__(cls: type[T], *args: Any, **kwargs: Any) -> T:
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]  # type: ignore[return-value]