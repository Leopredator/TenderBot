"""Конфигурация TenderBot: читает .env файл (если есть) и переменные окружения."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ENV_FILE)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

# Как часто проверять появление новых тендеров, минут
SCAN_INTERVAL_MIN: int = _int("SCAN_INTERVAL_MIN", 30)

# Сколько страниц свежих тендеров проверять за один проход по каждому источнику
MAX_PAGES_PER_SCAN: int = _int("MAX_PAGES_PER_SCAN", 2)

# Включённые источники ("rostender", "eis")
ENABLED_SOURCES: list[str] = [
    s.strip()
    for s in os.environ.get(
        "ENABLED_SOURCES", "rostender,eis"
    ).split(",")
    if s.strip()
]

REQUEST_TIMEOUT_SEC: int = _int("REQUEST_TIMEOUT_SEC", 30)

# Реальные IP api.telegram.org (обход DNS-блокировок провайдера).
# Официальные адреса Telegram стабильны; если DNS на вашей сети врёт,
# бот подключается напрямую по этим IP, минуя резолв. Пусто — обычный DNS.
TELEGRAM_REAL_IP: list[str] = [
    ip.strip()
    for ip in os.environ.get(
        "TELEGRAM_REAL_IP",
        "149.154.167.220,149.154.175.50,91.108.56.170",
    ).split(",")
    if ip.strip()
]
