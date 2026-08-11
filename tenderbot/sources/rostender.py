"""Парсер rostender.info — агрегатора, покрывающего ЕИС (44/223-ФЗ)
и коммерческие площадки (B2B-Center, Росэлторг, РТС-тендер и др.).

Проверено вживую: GET /extsearch?page=N отдаёт страницу со свежими
тендерами (без авторизации), отсортированными по дате публикации.
"""
from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup

from ..config import REQUEST_TIMEOUT_SEC
from ..models import Tender

log = logging.getLogger(__name__)

BASE_URL = "https://rostender.info"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}

_NUMBER_RE = re.compile(r"^№?\s*[-–—]?\s*(\d+)\s*$")


def _clean(text: str) -> str:
    # убираем "шумовые" символы, которыми площадка скрывает текст от парсеров
    return re.sub(r"\s+", " ", text).replace("\xa0", " ").replace("\u2591", "").strip()


def _pick(row: BeautifulSoup, selectors: list[str]) -> str:
    for sel in selectors:
        el = row.select_one(sel)
        if el:
            text = _clean(el.get_text(" ", strip=True))
            if text:
                return text
    return ""


class RostenderSource:
    name = "rostender"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def fetch_recent(self, max_pages: int = 2) -> list[Tender]:
        tenders: list[Tender] = []
        page = 1
        while page <= max_pages:
            url = f"{BASE_URL}/extsearch?page={page}"
            try:
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT_SEC)
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.warning("rostender: страница %s не загрузилась: %s", page, exc)
                break
            page_tenders = self._parse(resp.text)
            if not page_tenders:
                log.info("rostender: на странице %s нет тендеров, стоп", page)
                break
            tenders.extend(page_tenders)
            page += 1
        log.info("rostender: собрано %s тендеров", len(tenders))
        return tenders

    def _parse(self, html: str) -> list[Tender]:
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("a.tender-info__link")
        tenders: list[Tender] = []
        for link in rows:
            href = link.get("href") or ""
            title = _clean(link.get_text(" ", strip=True))
            if not href or not title:
                continue
            url = href if href.startswith("http") else BASE_URL + href
            row = link
            for _ in range(6):
                parent = row.parent
                if parent is None:
                    break
                row = parent
                if row.select_one(".starting-price, .tender-customer__name"):
                    break
            number = _pick(row, [".tender__number"])
            number = _NUMBER_RE.sub(r"\1", number)
            # заказчик на rostender.info доступен только после регистрации,
            # публичное имя скрыто шумовыми символами — оставляем пустым
            customer = ""
            if not number:
                m = re.search(r"/(\d+)-[^/]*$", url)
                if m:
                    number = m.group(1)
            price = _pick(row, [".starting-price__price"])
            end_date = _pick(row, [".tender__countdown-text"])
            category = ""
            city = ""
            vevent = row.select_one(".vevent")
            if vevent is not None:
                cats = [
                    x.get_text(" ", strip=True)
                    for x in vevent.select("a.category")
                ]
                if cats:
                    category = cats[-1]
                loc = vevent.select_one(".location")
                if loc is not None:
                    city = _clean(loc.get_text(" ", strip=True))
                    city = re.sub(r",?\s*(Russia|Россия|RU)\s*$", "", city)
            tenders.append(
                Tender(
                    url=url,
                    source=self.name,
                    number=number,
                    title=title,
                    customer=customer,
                    price=price,
                    end_date=end_date,
                    category=category,
                    city=city,
                )
            )
        return tenders