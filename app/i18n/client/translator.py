from __future__ import annotations

from app.i18n.client import ru, tj, uz


_TEXTS_BY_LOCALE: dict[str, dict[str, str]] = {
    "ru": ru.TEXTS,
    "tj": tj.TEXTS,
    "uz": uz.TEXTS,
}


def t(locale: str, key: str, **kwargs: object) -> str:
    """Возвращает перевод по ключу с fallback на RU."""
    texts = _TEXTS_BY_LOCALE.get(locale, ru.TEXTS)
    value = texts.get(key) or ru.TEXTS.get(key) or key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    return value
