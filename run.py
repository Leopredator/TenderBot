"""Точка входа: запускает бота и периодический сканер."""
from __future__ import annotations

import asyncio
import logging
import socket

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from tenderbot import config
from tenderbot.bot import register
from tenderbot.scanner import scan_task
from tenderbot.storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("tenderbot")


class _StaticResolver:
    """Резолвер aiohttp, подставляющий фиксированные IP вместо DNS.
    Нужен, если провайдер подменяет DNS-ответы для api.telegram.org."""

    def __init__(self, ips: list[str]):
        self._ips = ips

    async def resolve(self, host: str, port: int = 0, family: int = 0):
        return [
            {
                "hostname": host,
                "host": ip,
                "port": port,
                "family": socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
            for ip in self._ips
        ]


class _IpPinnedSession(AiohttpSession):
    """Сессия aiogram с коннектором, который резолвит api.telegram.org
    в фиксированные IP (обход подмены DNS)."""

    def __init__(self, ips: list[str], **kwargs):
        super().__init__(**kwargs)
        self._connector_init["resolver"] = _StaticResolver(ips)


def make_bot(token: str) -> Bot:
    if config.TELEGRAM_REAL_IP:
        session = _IpPinnedSession(ips=config.TELEGRAM_REAL_IP)
        log.info(
            "Подключение к Telegram по фиксированным IP: %s",
            ",".join(config.TELEGRAM_REAL_IP),
        )
        return Bot(token=token, session=session)
    return Bot(token=token)


async def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        print("Ошибка: не задан TELEGRAM_BOT_TOKEN.")
        print("Создайте файл .env рядом с run.py и укажите в нём:")
        print("  TELEGRAM_BOT_TOKEN=123456:ABC...")
        print("Как получить токен (BotFather) — см. README.md")
        return

    storage = Storage()
    bot = make_bot(config.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    register(dp, storage)

    log.info(
        "TenderBot запущен. Источники: %s. Интервал: %s мин.",
        ",".join(config.ENABLED_SOURCES) or "нет",
        config.SCAN_INTERVAL_MIN,
    )

    await asyncio.gather(
        dp.start_polling(bot),
        scan_task(bot, storage),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлено")