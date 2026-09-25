"""Thin client for the (free, keyless) Open Library API."""
import asyncio
import re
from typing import Optional

import httpx

from app.config import OPEN_LIBRARY_BASE

SERIES_PATTERN = re.compile(r"^(?P<title>.*?)\s*\((?P<series>[^,()]+),?\s*#?(?P<position>[\d.]+)?\)\s*$")

SEARCH_FIELDS = "key,title,author_name,first_publish_year,cover_i,isbn,edition_key,number_of_pages_median"


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


def _doc_to_result(doc: dict) -> dict:
    raw_title = doc.get("title", "Untitled")
    clean_title, series_name, series_position = parse_series_from_title(raw_title)
    isbn_list = doc.get("isbn") or []
    return {
        "ol_key": doc.get("key"),  # e.g. /works/OL45804W
        "title": clean_title,
        "raw_title": raw_title,
        "author_names": ", ".join(doc.get("author_name") or []),
        "first_publish_year": doc.get("first_publish_year"),
        "cover_id": doc.get("cover_i"),
        "isbn": isbn_list[0] if isbn_list else None,
        "pages": doc.get("number_of_pages_median"),
        "series_name": series_name,
        "series_position": series_position,
    }


async def _raw_search(client: httpx.AsyncClient, query: str, limit: int, page: int) -> list[dict]:
    if not query or not query.strip():
        return []
    params = {
        "q": query.strip(),
        "limit": limit,
        "page": page,
        "fields": SEARCH_FIELDS,
    }
    resp = await client.get(f"{OPEN_LIBRARY_BASE}/search.json", params=params)
    resp.raise_for_status()
    data = resp.json()
    return [_doc_to_result(doc) for doc in data.get("docs", [])]


async def search_books(query: str, limit: int = 20, page: int = 1) -> list[dict]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await _raw_search(client, query, limit, page)


async def search_books_smart(query: str, limit: int = 24) -> list[dict]:
    """Search Open Library, boosting results whose author name matches the
    query to the top.

    Open Library's plain relevance ranking is a generic text match across
    title/author/subjects, so a search like "Neuer" (a German author's
    surname, but also a common German word meaning "newer") can bury the
    author's own books under unrelated titles that merely contain the word.
    Running a second, author-field-scoped query in parallel and putting its
    (deduplicated) results first fixes the common case of "I'm looking for
    books by this person" without needing a heavier search backend.
    """
    if not query or not query.strip():
        return []

    async with httpx.AsyncClient(timeout=10.0) as client:
        general_task = _raw_search(client, query, limit, page=1)
        author_task = _raw_search(client, f'author:"{query.strip()}"', limit, page=1)
        general, author_matches = await asyncio.gather(
            general_task, author_task, return_exceptions=True
        )

    if isinstance(general, BaseException):
        general = []
    if isinstance(author_matches, BaseException):
        author_matches = []

    merged: list[dict] = []
    seen: set[str] = set()
    for item in list(author_matches) + list(general):
        key = item.get("ol_key")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged


async def search_by_author_or_series(text: str, limit: int = 40) -> list[dict]:
    """Used by the 'find more books in this series' feature."""
    return await search_books(text, limit=limit)
