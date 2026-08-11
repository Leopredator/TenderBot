"""Парсер ЕИС zakupki.gov.ru (официальный портал госзакупок).

Важно: в некоторых сетях/регионах портал ограничивает анонимный доступ
(captcha, блокировка). Парсер работает через публичную поисковую страницу
и при любом сбое корректно пропускает цикл — бот продолжает работать
с остальными источниками. ЕИС-тендеры при этом почти полностью дублируются
в rostender.info.
"""
from __future__ import annotations

import logging
import re

import requests
from bs4 import BeautifulSoup

from ..config import REQUEST_TIMEOUT_SEC
from ..models import Tender

log = logging.getLogger(__name__)

BASE_URL = "https://zakupki.gov.ru"
SEARCH_URL = (
    BASE_URL
    + "/epz/order/extendedsearch/results.html"
    + "?fz44=on&fz223=on&af=on&morphology=on&sortDirection=false"
    + "&sortBy=UPDATE_DATE&recordsPerPage=_50&pageNumber={page}"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).replace("\xa0", " ").strip()


def _pick(root: BeautifulSoup, selectors: list[str]) -> str:
    for sel in selectors:
        el = root.select_one(sel)
        if el:
            text = _clean(el.get_text(" ", strip=True))
            if text:
                return text
    return ""


class EisSource:
    name = "eis"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        # Портал ЕИС отдаёт неполную цепочку сертификатов (Минцифры РФ),
        # стандартная проверка SSL завершается ошибкой. Данные публичные,
        # поэтому проверку отключаем локально.
        self.session.verify = False
        try:
            import urllib3

            urllib3.disable_warnings(
                urllib3.exceptions.InsecureRequestWarning
            )
        except Exception:  # noqa: BLE001
            pass

    def fetch_recent(self, max_pages: int = 1) -> list[Tender]:
        tenders: list[Tender] = []
        for page in range(1, max_pages + 1):
            try:
                resp = self.session.get(
                    SEARCH_URL.format(page=page), timeout=REQUEST_TIMEOUT_SEC
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.warning("eis: страница %s не загрузилась: %s", page, exc)
                break
            if "captcha" in resp.url.lower() or b"captcha" in resp.content[:2000]:
                log.warning("eis: портал запросил captcha, пропускаем источник")
                break
            page_tenders = self._parse(resp.text)
            if not page_tenders:
                break
            tenders.extend(page_tenders)
        log.info("eis: собрано %s тендеров", len(tenders))
        return tenders

    def _parse(self, html: str) -> list[Tender]:
        soup = BeautifulSoup(html, "lxml")
        blocks = soup.select(".search-registry-entry-block")
        if not blocks:
            blocks = soup.select(".search-registry-entry")
        tenders: list[Tender] = []
        for block in blocks:
            link = block.select_one(".registry-entry__header-mid__number a")
            if link is None:
                continue
            href = link.get("href") or ""
            url = href if href.startswith("http") else BASE_URL + href
            number = _clean(link.get_text(" ", strip=True))
            title = ""
            customer = ""
            for body_block in block.select(".registry-entry__body-block"):
                label = _pick(body_block, [".registry-entry__body-title"])
                if not title and label in ("Объект закупки", "Предмет контракта"):
                    title = _pick(body_block, [".registry-entry__body-value"])
                if "заказчик" in label.lower():
                    customer = _pick(
                        body_block, [".registry-entry__body-href"]
                    )
            if not title:
                title_el = block.select_one(
                    ".registry-entry__header-mid__title"
                )
                if title_el is not None:
                    title = _clean(title_el.get_text(" ", strip=True))
            if not href or not title:
                continue
            price = _pick(block, [".price-block__value"])
            end_date = ""
            for data_block in block.select(".data-block"):
                label = _pick(data_block, [".data-block__title"])
                if "окончан" in label.lower():
                    end_date = _pick(data_block, [".data-block__value"])
                    break
            if not end_date:
                end_date = _pick(block, [".data-block__value"])
            tenders.append(
                Tender(
                    url=url,
                    source=self.name,
                    number=number,
                    title=title,
                    customer=customer,
                    price=price,
                    end_date=end_date,
                )
            )
        return tenders