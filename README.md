# Slack Monitoring System

Slack workspace event'lerini **Socket Mode** ile dinleyen, standart formatta kuyruğa alan ve HTTP API sunan servis. Tek process içinde hem Slack listener hem REST API çalışır; yapılandırma `.env`, loglar dönüşümlü dosyalara yazılır.

---

## Özellikler

- **Slack Socket Mode** — Açık URL veya ngrok gerekmez; WebSocket ile Slack’e bağlanır (App-Level Token: `xapp-...`).
- **Geniş event kapsamı** — Mesaj, reaction, kanal yaşam döngüsü, kullanıcı varlığı, dosya aktivitesi vb. (30+ event tipi).
- **Paylaşılan kuyruk** — Event’ler multiprocessing queue (`QueueServer`) üzerinden diğer process’lere tüketilmek üzere sunulur.
- **Yapılandırılmış loglama** — Üç dönüşümlü log: system (INFO), error (JSON), queue event’leri.
- **Graceful shutdown** — SIGINT/SIGTERM ile Socket Mode kapanır, queue ve log flush edilir.
- **HTTP API** — Health, status, info ve error log endpoint’leri (FastAPI + Uvicorn).
- **Hata dayanıklılığı** — Event seviyesinde hatalar loglanır, Slack’e 200 dönülür; process ayakta kalır.

---

## Gereksinimler

- **Python 3.10+**
- **Slack uygulaması** — Socket Mode açık, **App-Level Token** (`xapp-...`) ve `connections:write` yetkisi.
- Event’lere göre gerekli scope/abonelikler (örn. `message`, `reaction_added`, `member_joined_channel`).

---

## Kurulum

```bash
git clone <repository-url>
cd slack-monitoring-system
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Yapılandırma

Örnek env dosyasını kopyalayıp değerleri doldurun:

```bash
cp .env.example .env
```

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `SLACK_APP_TOKEN` | Evet | Slack App-Level Token (`xapp-...`). |
| `QUEUE_HOST` | Hayır | Queue manager bind adresi (varsayılan: `127.0.0.1`). |
| `QUEUE_PORT` | Hayır | Queue manager port (varsayılan: `50000`). |
| `QUEUE_AUTHKEY` | Hayır* | Queue manager auth secret. *Production’da zorunlu: `ENV=production` ve güçlü bir değer. |
| `API_HOST` | Hayır | HTTP API bind adresi (varsayılan: `127.0.0.1`). |
| `API_PORT` | Hayır | HTTP API port (varsayılan: `8002`). |
| `LOG_DIR` | Hayır | Log dosyalarının dizini (varsayılan: `logs`). |
| `ENV` | Hayır | `production` yapılırsa varsayılan `QUEUE_AUTHKEY` kabul edilmez. |

---

## Çalıştırma

Tek komutla hem API hem Slack listener başlar:

```bash
# Proje kökünden
export PYTHONPATH=.
python -m src
```

Veya:

```bash
python -m src.main
```

- **API** ana thread’de Uvicorn ile `API_HOST:API_PORT` (varsayılan `127.0.0.1:8002`) üzerinde çalışır.
- **Slack listener** arka planda bir thread’de Socket Mode ile bağlanır.
- Durdurmak: **Ctrl+C** (SIGINT); kapanış sırası: listener → queue → logging.

---

## Mimari (başlangıç akışı)

1. **Logging** — `setup_logging(_build_logging_config(log_dir))` ile system / error / queue logları kurulur.
2. **Startup** — `_startup()` (async): log dizini oluşturulur, `QueueServer.start()` çağrılır.
3. **Listener thread** — `listener_start()` ayrı thread’de çalışır (Socket Mode bloklayıcı).
4. **Uvicorn** — Ana thread’de `src.api.app:app` çalıştırılır; Ctrl+C ile önce Uvicorn biter, `finally` içinde `stop()` ile listener, queue ve logging kapatılır.

---

## API Endpoint’leri

Base URL varsayılan: `http://127.0.0.1:8002`

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/health` | Canlılık; `{"status": "ok"}`. |
| GET | `/monitoring/api/v1/status` | Kuyruk durumu: `queue_ready`, `queue_size`. |
| GET | `/monitoring/api/v1/info` | Uygulama bilgisi: `log_dir`, `env`. |
| GET | `/monitoring/api/v1/logs` | `error.log` son kayıtları (JSON). Query: `limit` (1–1000, varsayılan 100). |

**İnteraktif dokümantasyon**

- Swagger UI: `http://127.0.0.1:8002/docs`
- ReDoc: `http://127.0.0.1:8002/redoc`

---

## Loglama

Tüm loglar `LOG_DIR` (varsayılan `logs/`) altındadır. Uygulama tek bir logger (`app`) kullanır.

| Dosya | İçerik | Format |
|-------|--------|--------|
| `system.log` | Başlangıç, yaşam döngüsü, genel INFO. | Metin: `tarih \| seviye \| mesaj` |
| `error.log` | Sadece ERROR ve üzeri. | Satır başına JSON (timestamp, level, message, exception vb.) |
| `queue.log` | `queue_event` taşıyan kayıtlar (kuyruğa alınan event’ler). | Okunabilir: event_type, user_id, channel_id vb. |

- Logger seviyesi: **INFO**. Queue event kayıtları INFO ile yazılır ve `queue.log`’a düşer.
- Rotasyon: dosya başına 10 MB, 5 yedek.

---

## Kuyruk payload formatı

Event’ler kuyruğa standart bir dict olarak yazılır:

- **Zorunlu:** `event_type` (string).
- **Ortak (opsiyonel):** `user_id`, `channel_id`, `ts`, `thread_ts`, `text`.
- **Event’e özel:** örn. `reaction`, `links`, `file_id`, `channel_name`.

Consumer’lar en az `event_type` içeren `dict[str, Any]` beklemeli; diğer anahtarlar event tipine göre değişir.

---

## Proje yapısı

```
.
├── src/
│   ├── __main__.py       # python -m src → main()
│   ├── main.py           # main(), _startup(), stop(); uvicorn + listener thread
│   ├── listener.py       # Bolt app, Socket Mode, event handler’lar, _enqueue()
│   ├── queue.py          # QueueServer, build_message_event(), paylaşılan kuyruk
│   ├── api/
│   │   ├── app.py        # FastAPI uygulaması
│   │   ├── routes.py     # /health, /monitoring/api/v1/*
│   │   └── schemas.py    # Response modelleri
│   ├── core/
│   │   ├── logger.py     # Log config, formatter’lar, filter’lar, setup_logging
│   │   ├── settings.py   # Pydantic settings (.env), prod QUEUE_AUTHKEY kontrolü
│   │   └── singleton.py  # QueueServer için Singleton metaclass
│   └── services/
│       ├── log_service.py  # error.log okuma (get_error_logs)
│       └── __init__.py
├── logs/                 # system.log, error.log, queue.log (çalışırken oluşur)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Production

1. **`.env`** — `ENV=production` ve güçlü bir `QUEUE_AUTHKEY` tanımlayın; aksi halde uygulama başlamaz.
2. **Process yönetimi** — systemd, supervisord veya Docker restart policy ile process çökünce yeniden başlatılsın.
3. **API erişimi** — `/monitoring/*` ve özellikle `/logs` hassas bilgi içerebilir; reverse proxy, firewall veya API key ile kısıtlayın.
4. **Bind adresi** — API’ye dışarıdan erişilecekse `API_HOST=0.0.0.0` kullanın; güvenliği proxy/firewall ile sağlayın.
5. **Disk** — `LOG_DIR` yazılabilir olmalı ve dönüşümlü loglar için yeterli alan bırakın.

---

## Lisans

Proje lisans bilgisi repo ile birlikte verilir.
