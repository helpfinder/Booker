import json
from pathlib import Path
from typing import Dict

from app.config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

LOCALES_DIR = Path(__file__).resolve().parent / "locales"

_translations: Dict[str, Dict[str, str]] = {}


def load_translations() -> None:
    for lang in SUPPORTED_LANGUAGES:
        path = LOCALES_DIR / f"{lang}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                _translations[lang] = json.load(f)


def get_translator(lang: str):
    if lang not in _translations:
        lang = DEFAULT_LANGUAGE

    strings = _translations.get(lang, {})
    fallback = _translations.get(DEFAULT_LANGUAGE, {})

    def t(key: str) -> str:
        return strings.get(key, fallback.get(key, key))

    return t


load_translations()
