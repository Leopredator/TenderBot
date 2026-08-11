"""Базовый класс источника тендеров."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Tender


class Source(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_recent(self, max_pages: int) -> list[Tender]:
        """Возвращает свежие тендеры (страницы отсортированы по дате,
        самые новые — первые)."""