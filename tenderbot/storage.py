"""SQLite-хранилище: чаты, фильтры, тендеры."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "tenderbot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id    INTEGER PRIMARY KEY,
    paused     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS keywords (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cities (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cat_filters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS category_dict (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS tenders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT NOT NULL UNIQUE,
    source     TEXT NOT NULL,
    number     TEXT NOT NULL DEFAULT '',
    title      TEXT NOT NULL DEFAULT '',
    customer   TEXT NOT NULL DEFAULT '',
    price      TEXT NOT NULL DEFAULT '',
    end_date   TEXT NOT NULL DEFAULT '',
    category   TEXT NOT NULL DEFAULT '',
    city       TEXT NOT NULL DEFAULT '',
    matched    INTEGER NOT NULL DEFAULT 0,
    found_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tenders_found_at ON tenders(found_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, path: Path = DB_PATH):
        self._path = path
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._ensure_column("tenders", "category",
                            "ALTER TABLE tenders ADD COLUMN category TEXT")
        self._ensure_column("tenders", "city",
                            "ALTER TABLE tenders ADD COLUMN city TEXT")
        self._conn.commit()

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        cols = {
            r["name"]
            for r in self._conn.execute(f"PRAGMA table_info({table})")
        }
        if column not in cols:
            self._conn.execute(ddl)

    def close(self) -> None:
        self._conn.close()

    # ---------- чаты ----------
    def add_chat(self, chat_id: int) -> bool:
        cur = self._conn.execute(
            "SELECT chat_id FROM chats WHERE chat_id=?",
            (chat_id,),
        )
        if cur.fetchone():
            self._conn.execute(
                "UPDATE chats SET paused=0 WHERE chat_id=?", (chat_id,)
            )
            self._conn.commit()
            return False
        self._conn.execute(
            "INSERT INTO chats (chat_id, paused, created_at) VALUES (?, 0, ?)",
            (chat_id, _now()),
        )
        self._conn.commit()
        return True

    def get_active_chats(self) -> list[int]:
        rows = self._conn.execute(
            "SELECT chat_id FROM chats WHERE paused=0"
        ).fetchall()
        return [r["chat_id"] for r in rows]

    def set_paused(self, chat_id: int, paused: bool) -> None:
        self._conn.execute(
            "UPDATE chats SET paused=? WHERE chat_id=?",
            (1 if paused else 0, chat_id),
        )
        self._conn.commit()

    # ---------- ключевые слова ----------
    def add_keyword(self, text: str) -> bool:
        text = text.strip().lower()
        if not text:
            return False
        try:
            self._conn.execute(
                "INSERT INTO keywords (text, created_at) VALUES (?, ?)",
                (text, _now()),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_keyword(self, text: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM keywords WHERE text=?", (text.strip().lower(),)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_keywords(self) -> list[str]:
        return [
            r["text"]
            for r in self._conn.execute(
                "SELECT text FROM keywords ORDER BY id"
            ).fetchall()
        ]

    # ---------- заказчики ----------
    def add_customer(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        try:
            self._conn.execute(
                "INSERT INTO customers (name, created_at) VALUES (?, ?)",
                (name, _now()),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_customer(self, name: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM customers WHERE name=?", (name.strip(),)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_customers(self) -> list[str]:
        return [
            r["name"]
            for r in self._conn.execute(
                "SELECT name FROM customers ORDER BY id"
            ).fetchall()
        ]

    # ---------- города ----------
    def add_city(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        try:
            self._conn.execute(
                "INSERT INTO cities (name, created_at) VALUES (?, ?)",
                (name, _now()),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_city_by_id(self, city_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM cities WHERE id=?", (city_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def remove_city(self, name: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM cities WHERE name=?", (name.strip(),)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_cities(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT id, name FROM cities ORDER BY id"
        ).fetchall()

    # ---------- категории (фильтры по отраслям) ----------
    def add_cat_filter(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        try:
            self._conn.execute(
                "INSERT INTO cat_filters (name, created_at) VALUES (?, ?)",
                (name, _now()),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_cat_filter(self, name: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM cat_filters WHERE name=?", (name.strip(),)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_cat_filters(self) -> list[str]:
        return [
            r["name"]
            for r in self._conn.execute(
                "SELECT name FROM cat_filters ORDER BY id"
            ).fetchall()
        ]

    def sync_categories(self) -> None:
        """Заносит все категории из собранных тендеров в словарь."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO category_dict (name)
            SELECT DISTINCT category FROM tenders
            WHERE category != ''
            """
        )
        self._conn.commit()

    def distinct_categories(
        self, limit: int = 30
    ) -> list[sqlite3.Row]:
        self.sync_categories()
        return self._conn.execute(
            """
            SELECT d.id, d.name, COUNT(t.id) AS cnt
            FROM category_dict d
            LEFT JOIN tenders t ON t.category = d.name
            GROUP BY d.id, d.name
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def category_name_by_id(self, cat_id: int) -> str:
        row = self._conn.execute(
            "SELECT name FROM category_dict WHERE id=?", (cat_id,)
        ).fetchone()
        return row["name"] if row else ""

    # ---------- тендеры ----------
    def tender_seen(self, url: str) -> bool:
        return (
            self._conn.execute(
                "SELECT 1 FROM tenders WHERE url=?", (url,)
            ).fetchone()
            is not None
        )

    def add_tender(
        self,
        url: str,
        source: str,
        number: str = "",
        title: str = "",
        customer: str = "",
        price: str = "",
        end_date: str = "",
        category: str = "",
        city: str = "",
        matched: bool = False,
    ) -> bool:
        """Добавляет тендер. Возвращает True, если он новый.

        Если тендер уже есть, а matched=True — обновляет флаг
        "подходит по фильтрам" (и дополняет категорию/город).
        """
        try:
            self._conn.execute(
                """
                INSERT INTO tenders
                    (url, source, number, title, customer, price, end_date,
                     category, city, matched, found_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (url, source, number, title, customer, price, end_date,
                 category, city, 1 if matched else 0, _now()),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            if matched:
                self._conn.execute(
                    """
                    UPDATE tenders
                    SET matched=1,
                        category=CASE WHEN category='' THEN ? ELSE category END,
                        city=CASE WHEN city='' THEN ? ELSE city END
                    WHERE url=?
                    """,
                    (category, city, url),
                )
                self._conn.commit()
            return False

    def search_tenders(self, query: str, limit: int = 20) -> list[sqlite3.Row]:
        pattern = f"%{query}%"
        return self._conn.execute(
            """
            SELECT url, source, number, title, customer, price, end_date,
                   category, city, matched, found_at
            FROM tenders
            WHERE title LIKE ? OR customer LIKE ? OR number LIKE ?
            ORDER BY found_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()

    def stats(self) -> dict:
        total = self._conn.execute(
            "SELECT COUNT(*) AS c FROM tenders"
        ).fetchone()["c"]
        matched = self._conn.execute(
            "SELECT COUNT(*) AS c FROM tenders WHERE matched=1"
        ).fetchone()["c"]
        return {
            "total": total,
            "matched": matched,
            "keywords": len(self.list_keywords()),
            "customers": len(self.list_customers()),
            "cities": len(self.list_cities()),
            "categories": len(self.list_cat_filters()),
            "active_chats": len(self.get_active_chats()),
        }