"""Периодический сбор тендеров, фильтрация и рассылка в Telegram."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from . import config, filters
from .models import Tender
from .sources import build_sources
from .storage import Storage

log = logging.getLogger(__name__)


def _match(tender: Tender, keywords: list[str], customers: list[str],
           cities: list[str], categories: list[str]) -> bool:
    return filters.match_tender(
        keywords, customers, cities, categories,
        tender.title, tender.customer, tender.city, tender.category,
    )


def _has_filters(storage: Storage) -> bool:
    return bool(
        storage.list_keywords()
        or storage.list_customers()
        or storage.list_cities()
        or storage.list_cat_filters()
    )


def _collect(
    storage: Storage,
    max_pages: int,
    limit: int | None = None,
    check_db: bool = False,
) -> list[Tender]:
    """Общий сбор с источников.

    check_db=True — пропускает тендеры, уже известные базе (для рассылки).
    check_db=False — возвращает все подходящие, включая уже существующие.
    """
    keywords = storage.list_keywords()
    customers = storage.list_customers()
    cities = [r["name"] for r in storage.list_cities()]
    categories = storage.list_cat_filters()
    storage.sync_categories()

    matched: list[Tender] = []
    for source in build_sources():
        try:
            tenders = source.fetch_recent(max_pages)
        except Exception as exc:  # noqa: BLE001
            log.warning("источник %s упал: %s", source.name, exc)
            continue
        for tender in tenders:
            if not tender.url:
                continue
            is_new = storage.add_tender(
                url=tender.url,
                source=tender.source,
                number=tender.number,
                title=tender.title,
                customer=tender.customer,
                price=tender.price,
                end_date=tender.end_date,
                category=tender.category,
                city=tender.city,
                matched=False,
            )
            if check_db and not is_new:
                continue
            if _match(tender, keywords, customers, cities, categories):
                storage.add_tender(
                    url=tender.url,
                    source=tender.source,
                    number=tender.number,
                    title=tender.title,
                    customer=tender.customer,
                    price=tender.price,
                    end_date=tender.end_date,
                    category=tender.category,
                    city=tender.city,
                    matched=True,
                )
                matched.append(tender)
        if limit is not None and len(matched) >= limit:
            break
    return matched[:limit] if limit else matched


def scan_once(storage: Storage) -> list[Tender]:
    """Синхронный проход по всем источникам. Возвращает новые подходящие."""
    if not _has_filters(storage):
        log.info("нет активных фильтров — пропускаем сбор")
        return []
    new_matched = _collect(storage, config.MAX_PAGES_PER_SCAN, check_db=True)
    log.info("итого новых подходящих: %s", len(new_matched))
    return new_matched


def collect_matching(
    storage: Storage,
    max_pages: int | None = None,
    limit: int = 10,
) -> list[Tender]:
    """Все подходящие тендеры на площадках прямо сейчас.

    Не сверяется с базой — показывает и те тендеры, которые уже есть
    на сайтах (в том числе опубликованные до старта бота).
    """
    if not _has_filters(storage):
        return []
    pages = max_pages or config.MAX_PAGES_PER_SCAN
    matched = _collect(storage, pages, limit=limit, check_db=False)
    log.info("собрано подходящих по запросу: %s", len(matched))
    return matched


async def scan_task(bot: Bot, storage: Storage) -> None:
    """Бесконечный цикл: сканирование раз в SCAN_INTERVAL_MIN минут."""
    interval = max(1, config.SCAN_INTERVAL_MIN) * 60
    first = True
    while True:
        if not first:
            await asyncio.sleep(interval)
        first = False
        log.info("== начинаем проход ==")
        try:
            matched = await asyncio.to_thread(scan_once, storage)
        except Exception as exc:  # noqa: BLE001
            log.exception("ошибка прохода: %s", exc)
            continue
        if not matched:
            continue
        chats = storage.get_active_chats()
        if not chats:
            log.info("нет активных чатов для рассылки")
            continue
        for tender in matched:
            for chat_id in chats:
                try:
                    await bot.send_message(
                        chat_id, tender.card_text(), parse_mode="HTML"
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "не удалось отправить чату %s: %s", chat_id, exc
                    )
            await asyncio.sleep(0.1)