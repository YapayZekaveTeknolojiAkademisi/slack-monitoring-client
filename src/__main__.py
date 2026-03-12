"""
python -m src ile API (uvicorn) + Slack listener başlatılır.
Durdurmak: Ctrl+C veya SIGTERM (graceful shutdown).
"""
from __future__ import annotations

from src.main import main

if __name__ == "__main__":
    main()
