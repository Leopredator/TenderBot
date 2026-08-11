"""Модель тендера."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Tender:
    url: str
    source: str
    number: str = ""
    title: str = ""
    customer: str = ""
    price: str = ""
    end_date: str = ""
    category: str = ""
    city: str = ""
    extra: dict = field(default_factory=dict)

    def card_text(self) -> str:
        """Текст уведомления о тендере (HTML для Telegram)."""
        parts = ["<b>Найден новый тендер</b>", ""]
        if self.number:
            parts.append(f"Номер: {self.number}")
        if self.title:
            parts.append(f"Название: {self.title}")
        if self.customer:
            parts.append(f"Заказчик: {self.customer}")
        if self.price:
            parts.append(f"Цена: {self.price}")
        if self.end_date:
            parts.append(f"Окончание: {self.end_date}")
        if self.category:
            parts.append(f"Категория: {self.category}")
        if self.city:
            parts.append(f"Регион: {self.city}")
        parts.append(f"Источник: {self.source}")
        parts.append(f"Ссылка: {self.url}")
        return "\n".join(parts)