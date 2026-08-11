"""Источники тендеров."""
from __future__ import annotations

from .. import config
from .base import Source
from .eis import EisSource
from .rostender import RostenderSource

__all__ = ["Source", "build_sources", "source_names"]

_SOURCE_BUILDERS = {
    "rostender": RostenderSource,
    "eis": EisSource,
}


def source_names() -> list[str]:
    return list(_SOURCE_BUILDERS)


def build_sources() -> list[Source]:
    sources: list[Source] = []
    for name in config.ENABLED_SOURCES:
        builder = _SOURCE_BUILDERS.get(name.lower())
        if builder is None:
            continue
        try:
            sources.append(builder())
        except Exception as exc:  # noqa: BLE001
            print(f"[tenderbot] источник '{name}' не запустился: {exc}")
    return sources