"""Telegram-бот: кнопки меню, команды и инлайн-кнопки категорий/городов."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from .scanner import collect_matching
from .storage import Storage

log = logging.getLogger(__name__)

MENU_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Актуальное"), KeyboardButton(text="Статистика")],
        [KeyboardButton(text="Категории"), KeyboardButton(text="Города")],
    ],
    resize_keyboard=True,
)

HELP_TEXT = (
    "Команды бота:\n"
    "/add_word текст — добавить ключевое слово\n"
    "/del_word текст — убрать ключевое слово\n"
    "/add_customer название — следить за заказчиком\n"
    "/del_customer название — перестать следить\n"
    "/add_city город — следить за городом/регионом\n"
    "/del_city город — убрать город\n"
    "/list — показать активные фильтры\n"
    "/fresh — все подходящие тендеры на площадках прямо сейчас\n"
    "/categories — категории из собранных тендеров\n"
    "/cities — управление городами\n"
    "/search текст — поиск по сохранённым тендерам\n"
    "/pause — приостановить уведомления\n"
    "/resume — возобновить уведомления\n"
    "/stats — статистика\n"
    "/menu — показать кнопки\n"
    "/help — эта справка"
)

WELCOME_TEXT = (
    "Привет! Я мониторю тендерные площадки (ЕИС, B2B-Center, Росэлторг, "
    "РТС-тендер и другие через агрегаторы) и пришлю уведомление, когда "
    "появится тендер по вашим интересам.\n\n"
    "Добавьте фильтры:\n"
    "/add_word поставка компьютеров — по словам\n"
    "/add_city Москва — по городу/региону\n"
    "/add_customer РЖД — по заказчику\n\n"
    "Кнопки меню: Актуальное, Статистика, Категории, Города.\n"
    "Полный список команд — /help"
)


def _rest(message: Message) -> str:
    text = (message.text or "").strip()
    _, _, rest = text.partition(" ")
    return rest.strip()


def _chunk_texts(blocks: list[str], max_len: int = 3800) -> list[str]:
    """Разбивает блоки текста на сообщения в пределах лимита Telegram."""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        if current and size + len(block) + 2 > max_len:
            chunks.append("\n\n".join(current))
            current = []
            size = 0
        current.append(block)
        size += len(block) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def register(dp: Dispatcher, storage: Storage) -> None:
    # ------------------------------------------------------------- кнопки
    @dp.message(F.text == "Актуальное")
    async def btn_fresh(message: Message) -> None:
        await _fresh(message, storage)

    @dp.message(F.text == "Статистика")
    async def btn_stats(message: Message) -> None:
        await _stats(message, storage)

    @dp.message(F.text == "Категории")
    async def btn_categories(message: Message) -> None:
        await _categories(message, storage)

    @dp.message(F.text == "Города")
    async def btn_cities(message: Message) -> None:
        await _cities(message, storage)

    # ---------------------------------------------------------- команды
    @dp.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        storage.add_chat(message.chat.id)
        await message.answer(WELCOME_TEXT, reply_markup=MENU_KEYBOARD)

    @dp.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(HELP_TEXT)

    @dp.message(Command("menu"))
    async def cmd_menu(message: Message) -> None:
        await message.answer("Кнопки меню:", reply_markup=MENU_KEYBOARD)

    @dp.message(Command("add_word"))
    async def cmd_add_word(message: Message) -> None:
        word = _rest(message)
        if not word:
            await message.answer("Пример: /add_word поставка компьютеров")
            return
        if storage.add_keyword(word):
            await message.answer(
                f"Ключевое слово добавлено: {word}", reply_markup=MENU_KEYBOARD
            )
        else:
            await message.answer("Такое слово уже есть.")

    @dp.message(Command("del_word"))
    async def cmd_del_word(message: Message) -> None:
        word = _rest(message)
        if not word:
            await message.answer("Пример: /del_word поставка компьютеров")
            return
        if storage.remove_keyword(word):
            await message.answer(
                f"Ключевое слово удалено: {word}", reply_markup=MENU_KEYBOARD
            )
        else:
            await message.answer("Такого слова в списке нет.")

    @dp.message(Command("add_customer"))
    async def cmd_add_customer(message: Message) -> None:
        name = _rest(message)
        if not name:
            await message.answer("Пример: /add_customer РЖД")
            return
        if storage.add_customer(name):
            await message.answer(
                f"Заказчик добавлен: {name}", reply_markup=MENU_KEYBOARD
            )
        else:
            await message.answer("Такой заказчик уже есть.")

    @dp.message(Command("del_customer"))
    async def cmd_del_customer(message: Message) -> None:
        name = _rest(message)
        if not name:
            await message.answer("Пример: /del_customer РЖД")
            return
        if storage.remove_customer(name):
            await message.answer(
                f"Заказчик удалён: {name}", reply_markup=MENU_KEYBOARD
            )
        else:
            await message.answer("Такого заказчика в списке нет.")

    @dp.message(Command("add_city"))
    async def cmd_add_city(message: Message) -> None:
        name = _rest(message)
        if not name:
            await message.answer("Пример: /add_city Москва")
            return
        if storage.add_city(name):
            await message.answer(
                f"Город добавлен: {name}", reply_markup=MENU_KEYBOARD
            )
        else:
            await message.answer("Такой город уже есть.")

    @dp.message(Command("del_city"))
    async def cmd_del_city(message: Message) -> None:
        name = _rest(message)
        if not name:
            await message.answer("Пример: /del_city Москва")
            return
        if storage.remove_city(name):
            await message.answer(
                f"Город удалён: {name}", reply_markup=MENU_KEYBOARD
            )
        else:
            await message.answer("Такого города в списке нет.")

    @dp.message(Command("list"))
    async def cmd_list(message: Message) -> None:
        words = storage.list_keywords()
        customers = storage.list_customers()
        cities = storage.list_cities()
        cats = storage.list_cat_filters()
        lines = ["<b>Ключевые слова:</b>"]
        lines += [f"- {w}" for w in words] or ["(пусто)"]
        lines.append("")
        lines.append("<b>Заказчики:</b>")
        lines += [f"- {c}" for c in customers] or ["(пусто)"]
        lines.append("")
        lines.append("<b>Города/регионы:</b>")
        lines += [f"- {c['name']}" for c in cities] or ["(пусто)"]
        lines.append("")
        lines.append("<b>Категории:</b>")
        lines += [f"- {c}" for c in cats] or ["(пусто)"]
        await message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("fresh"))
    async def cmd_fresh(message: Message) -> None:
        await _fresh(message, storage)

    @dp.message(Command("categories"))
    async def cmd_categories(message: Message) -> None:
        await _categories(message, storage)

    @dp.message(Command("cities"))
    async def cmd_cities(message: Message) -> None:
        await _cities(message, storage)

    @dp.message(Command("pause"))
    async def cmd_pause(message: Message) -> None:
        storage.set_paused(message.chat.id, True)
        await message.answer("Уведомления приостановлены. Возобновить: /resume")

    @dp.message(Command("resume"))
    async def cmd_resume(message: Message) -> None:
        storage.set_paused(message.chat.id, False)
        await message.answer("Уведомления возобновлены.")

    @dp.message(Command("stats"))
    async def cmd_stats(message: Message) -> None:
        await _stats(message, storage)

    @dp.message(Command("search"))
    async def cmd_search(message: Message) -> None:
        query = _rest(message)
        if not query:
            await message.answer("Пример: /search поставка ноутбуков")
            return
        rows = storage.search_tenders(query, limit=10)
        if not rows:
            await message.answer("Ничего не найдено.")
            return
        lines = [f"Найдено: {len(rows)}", ""]
        for r in rows:
            head = r["title"] or r["number"] or r["url"]
            line = f"<b>{head}</b>"
            if r["price"]:
                line += f" | {r['price']}"
            line += f"\n{r['url']}"
            lines.append(line)
        for chunk in _chunk_texts(lines):
            await message.answer(chunk, parse_mode="HTML")

    # ---------------------------------------------------- инлайн-кнопки
    @dp.callback_query(F.data.startswith("cat:"))
    async def cb_cat(callback: CallbackQuery) -> None:
        cat_id = int(callback.data.split(":", 1)[1])
        name = storage.category_name_by_id(cat_id)
        if not name:
            await callback.answer("Категория не найдена", show_alert=True)
            return
        if storage.add_cat_filter(name):
            await callback.answer(
                f"Категория добавлена в фильтры: {name[:40]}"
            )
            await callback.message.answer(
                f"Категория добавлена в фильтры: {name}",
                reply_markup=MENU_KEYBOARD,
            )
        else:
            await callback.answer("Такая категория уже в фильтрах")

    @dp.callback_query(F.data.startswith("delcity:"))
    async def cb_del_city(callback: CallbackQuery) -> None:
        city_id = int(callback.data.split(":", 1)[1])
        if storage.remove_city_by_id(city_id):
            await callback.answer("Город удалён из фильтров")
            await _cities(callback.message, storage)  # обновляем список
        else:
            await callback.answer("Уже удалён", show_alert=True)

    @dp.callback_query(F.data == "info")
    async def cb_info(callback: CallbackQuery) -> None:
        await callback.answer("Свои слова: /add_word текст")


# ----------------------------------------------------------- реализации
async def _fresh(message: Message, storage: Storage) -> None:
    if not (
        storage.list_keywords()
        or storage.list_customers()
        or storage.list_cities()
        or storage.list_cat_filters()
    ):
        await message.answer(
            "Сначала добавьте фильтры:\n"
            "/add_word поставка компьютеров\n"
            "/add_city Москва\n"
            "/add_customer РЖД",
            reply_markup=MENU_KEYBOARD,
        )
        return
    await message.answer(
        "Собираю текущие тендеры с площадок, это займёт до минуты..."
    )
    matched = await asyncio.to_thread(collect_matching, storage, None, 10)
    if not matched:
        await message.answer("Сейчас подходящих тендеров нет.",
                             reply_markup=MENU_KEYBOARD)
        return
    await message.answer("<b>Текущие подходящие тендеры:</b>",
                         parse_mode="HTML")
    for chunk in _chunk_texts([t.card_text() for t in matched]):
        await message.answer(chunk, parse_mode="HTML")


async def _stats(message: Message, storage: Storage) -> None:
    s = storage.stats()
    await message.answer(
        "Статистика:\n"
        f"- всего тендеров в базе: {s['total']}\n"
        f"- подходящих по фильтрам: {s['matched']}\n"
        f"- ключевых слов: {s['keywords']}\n"
        f"- заказчиков: {s['customers']}\n"
        f"- городов/регионов: {s['cities']}\n"
        f"- категорий: {s['categories']}\n"
        f"- получают уведомления: {s['active_chats']} чат(ов)"
    )


async def _categories(message: Message, storage: Storage) -> None:
    rows = storage.distinct_categories(limit=30)
    if not rows:
        await message.answer(
            "Пока нет категорий — они появятся после первого полного "
            "сканирования (каждые 30 минут).",
            reply_markup=MENU_KEYBOARD,
        )
        return
    buttons = [
        [InlineKeyboardButton(
            text=f"{r['name'][:35]} ({r['cnt']})",
            callback_data=f"cat:{r['id']}",
        )]
        for r in rows
    ]
    buttons.append(
        [InlineKeyboardButton(text="Искать свои: /add_word", callback_data="info")]
    )
    await message.answer(
        "Категории из собранных тендеров. Нажмите, чтобы добавить "
        "в фильтры:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


async def _cities(message: Message, storage: Storage) -> None:
    cities = storage.list_cities()
    if not cities:
        await message.answer(
            "Городов в фильтрах нет.\n"
            "Добавьте: /add_city Москва или /add_city Приморский край",
            reply_markup=MENU_KEYBOARD,
        )
        return
    buttons = [
        [
            InlineKeyboardButton(
                text=f"Убрать: {r['name']}", callback_data=f"delcity:{r['id']}"
            )
        ]
        for r in cities
    ]
    await message.answer(
        "Активные города/регионы (кнопка убирает из фильтров):\n"
        + "\n".join(f"- {r['name']}" for r in cities)
        + "\n\nНовый: /add_city Название",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )