"""Thin client for the (free, keyless) Open Library API."""
import re
from typing import Optional

import httpx

from app.config import OPEN_LIBRARY_BASE

SERIES_PATTERN = re.compile(r"^(?P<title>.*?)\s*\((?P<series>[^,()]+),?\s*#?(?P<position>[\d.]+)?\)\s*$")


def parse_series_from_title(raw_title: str):
    """Open Library titles are often like 'Book Name (Series Name, #2)'.
    Returns (clean_title, series_name, series_position) best-effort.
    """
    match = SERIES_PATTERN.match(raw_title)
    if not match:
        return raw_title, None, None

    clean_title = match.group("title").strip()
    series = match.group("series").strip() if match.group("series") else None
    position_raw = match.group("position")
    position = None
    if position_raw:
        try:
            position = float(position_raw)
        except ValueError:
            position = None
    return clean_title or raw_title, series, position


async def search_books(query: str, limit: int = 20, page: int = 1) -> list[dict]:
    if not query or not query.strip():
        return []

    params = {
        "q": query.strip(),
        "limit": limit,
        "page": page,
        "fields": "key,title,author_name,first_publish_year,cover_i,isbn,edition_key",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{OPEN_LIBRARY_BASE}/search.json", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for doc in data.get("docs", []):
        raw_title = doc.get("title", "Untitled")
        clean_title, series_name, series_position = parse_series_from_title(raw_title)
        isbn_list = doc.get("isbn") or []
        results.append(
            {
                "ol_key": doc.get("key"),  # e.g. /works/OL45804W
                "title": clean_title,
                "raw_title": raw_title,
                "author_names": ", ".join(doc.get("author_name") or []),
                "first_publish_year": doc.get("first_publish_year"),
                "cover_id": doc.get("cover_i"),
                "isbn": isbn_list[0] if isbn_list else None,
                "series_name": series_name,
                "series_position": series_position,
            }
        )
    return results


async def search_by_author_or_series(text: str, limit: int = 40) -> list[dict]:
    """Used by the 'find more books in this series' feature."""
    return await search_books(text, limit=limit)
