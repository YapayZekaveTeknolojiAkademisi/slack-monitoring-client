import threading 

class SingletonMeta(type):
    """
    Thread-safe (iş parçacığı güvenli) Singleton meta sınıfı.
    Bu sınıfı 'metaclass' olarak kullanan sınıflardan yalnızca bir örnek oluşturulabilir.
    """
    _instances = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # İlk kontrol (Kilit maliyetinden kaçınmak için)
        if cls not in cls._instances:
            with cls._lock:
                # İkinci kontrol (Kilidi beklerken başka bir thread oluşturmuş olabilir)
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]