"""Фильтрация тендеров: ключевые слова (со стеммингом) и заказчики.

Стеммер — компактная реализация алгоритма Porter (Snowball) для русского языка.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- стеммер
_PERFECTIVEGROUND = re.compile(
    r"((ив|ивши|ившись|ыв|ывши|ывшись)|((?<=[ая])(в|вши|вшись)))$"
)
_REFLEXIVE = re.compile(r"(с[яь])$")
_ADJECTIVE = re.compile(
    r"(ее|ие|ые|ое|ими|ыми|ей|ий|ый|ой|ем|им|ым|ом|его|ого|ему|ому|их|ых|"
    r"ую|юю|ая|яя|ою|ею)$"
)
_PARTICIPLE = re.compile(
    r"((ивш|ывш|ующ)|((?<=[ая])(ем|нн|вш|ющ|щ)))$"
)
_VERB = re.compile(
    r"((ила|ыла|ена|ейте|уйте|ите|или|ыли|ей|уй|ил|ыл|им|ым|ен|ило|ыло|"
    r"ено|ят|ует|уют|ит|ыт|ены|ить|ыть|ишь|ую|ю)|"
    r"((?<=[ая])(ла|на|ете|йте|ли|й|л|ем|н|ло|но|ет|ют|ны|ть|ешь|нно)))$"
)
_NOUN = re.compile(
    r"(а|ев|ов|ие|ье|е|иями|ями|ами|еи|ии|и|ией|ей|ой|ий|й|иям|ям|ием|ем|"
    r"ам|ом|о|у|ах|иях|ях|ы|ь|ию|ью|ю|ия|ья|я)$"
)
_RVRE = re.compile(r"^(.*?[аеиоуыэюя])(.*)$")
_DERIVATIONAL = re.compile(r".*[^аеиоуыэюя]+[аеиоуыэюя].*ость?$")


def stem_word(word: str) -> str:
    word = word.lower()
    if len(word) <= 2 or not re.search(r"[а-яё]", word):
        return word
    m = _RVRE.match(word)
    if not m:
        return word
    start, rv = m.group(1), m.group(2)

    rv = _PERFECTIVEGROUND.sub("", rv, count=1)
    rv = _REFLEXIVE.sub("", rv, count=1)
    if _ADJECTIVE.search(rv):
        rv = _ADJECTIVE.sub("", rv, count=1)
        rv = _PARTICIPLE.sub("", rv, count=1)
    else:
        rv = _VERB.sub("", rv, count=1)
    rv = _NOUN.sub("", rv, count=1)
    if rv.endswith("и"):
        rv = rv[:-1]
    if _DERIVATIONAL.search(rv):
        rv = rv[:-4]
    if rv.endswith("нн"):
        rv = rv[:-1]
    return start + rv


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[а-яёa-z0-9]+", text.lower(), flags=re.IGNORECASE)
    return {stem_word(w) for w in words if len(w) >= 2}


def match_tender(
    keywords: list[str],
    customers: list[str],
    cities: list[str],
    categories: list[str],
    title: str,
    customer: str,
    city: str = "",
    category: str = "",
) -> bool:
    """Возвращает True, если тендер подходит хотя бы по одному фильтру."""
    if keywords:
        title_tokens = _tokens(title)
        for kw in keywords:
            kw_tokens = _tokens(kw)
            if kw_tokens and kw_tokens <= title_tokens:
                return True
    if customers:
        title_l = title.lower()
        customer_l = customer.lower()
        for name in customers:
            needle = name.lower()
            if needle in customer_l or needle in title_l:
                return True
    if cities:
        city_l = city.lower()
        for name in cities:
            if name.lower() in city_l:
                return True
    if categories:
        for name in categories:
            if name == category:
                return True
    return False
