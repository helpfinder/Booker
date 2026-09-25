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


_LANGUAGE_NAMES = {
    "eng": "EN", "ger": "DE", "deu": "DE", "fre": "FR", "fra": "FR",
    "spa": "ES", "ita": "IT", "cze": "CS", "ces": "CS", "slo": "SK",
    "slk": "SK", "pol": "PL", "rus": "RU", "por": "PT", "dut": "NL",
    "nld": "NL",
}


async def _get_json(client: httpx.AsyncClient, url: str, params: Optional[dict] = None):
    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return None


async def fetch_details(ol_key: str = "", isbn: str = "") -> Optional[dict]:
    """Fetch richer per-book info for the "Details" panel: publisher, exact
    publish date, page count, language, description, subjects and average
    rating -- all from Open Library, which needs no API key and (unlike
    Google Books) has no quota wall for anonymous use.

    Combines three calls run in parallel: the edition record (by ISBN, for
    publisher/pages/publish date/cover), the work record (by ol_key, for
    the description and subjects), and the work's ratings summary.
    """
    if not ol_key and not isbn:
        return None

    async with httpx.AsyncClient(timeout=8.0) as client:
        edition_coro = (
            _get_json(
                client,
                f"{OPEN_LIBRARY_BASE}/api/books",
                {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            )
            if isbn
            else asyncio.sleep(0, result=None)
        )
        work_coro = (
            _get_json(client, f"{OPEN_LIBRARY_BASE}{ol_key}.json")
            if ol_key
            else asyncio.sleep(0, result=None)
        )
        ratings_coro = (
            _get_json(client, f"{OPEN_LIBRARY_BASE}{ol_key}/ratings.json")
            if ol_key
            else asyncio.sleep(0, result=None)
        )
        edition_raw, work, ratings = await asyncio.gather(edition_coro, work_coro, ratings_coro)

    edition = edition_raw.get(f"ISBN:{isbn}") if edition_raw else None

    publisher = None
    publish_date = None
    page_count = None
    cover_url = None
    language = None
    series_hint = None
    if edition:
        publishers = edition.get("publishers") or []
        if publishers and isinstance(publishers[0], dict):
            publisher = publishers[0].get("name")
        publish_date = edition.get("publish_date")
        page_count = edition.get("number_of_pages")
        cover = edition.get("cover") or {}
        cover_url = cover.get("medium") or cover.get("large") or cover.get("small")
        languages = edition.get("languages") or []
        if languages and isinstance(languages[0], dict):
            code = (languages[0].get("key") or "").rsplit("/", 1)[-1]
            language = _LANGUAGE_NAMES.get(code, code.upper() or None)
        series_list = edition.get("series") or []
        if series_list:
            series_hint = series_list[0]

    description = None
    categories: list[str] = []
    if work:
        desc = work.get("description")
        if isinstance(desc, dict):
            description = desc.get("value")
        elif isinstance(desc, str):
            description = desc
        categories = (work.get("subjects") or [])[:6]

    average_rating = None
    rating_count = None
    if ratings:
        summary = ratings.get("summary") or {}
        avg = summary.get("average")
        if avg:
            average_rating = round(avg, 1)
            rating_count = summary.get("count")

    if not any(
        [publisher, publish_date, page_count, description, categories, cover_url, average_rating, series_hint]
    ):
        return None

    return {
        "publisher": publisher,
        "published_date": publish_date,
        "page_count": page_count,
        "language": language,
        "description": description,
        "categories": categories,
        "cover_url": cover_url,
        "average_rating": average_rating,
        "rating_count": rating_count,
        "series_hint": series_hint,
    }


SERIES_FIELD_PATTERN = re.compile(
    r"^(?P<name>.*?)[,]?\s*(?:#|[Bb]ook|[Vv]ol\.?|[Vv]olume)\s*(?P<num>[\d.]+)\s*$"
)


def parse_series_field(raw: str):
    """Parse an Open Library edition "series" string, e.g. 'Harry Potter #1'
    or 'Harry Potter, Book 1' or just 'Harry Potter' (no position).
    Returns (name, position).
    """
    raw = (raw or "").strip()
    if not raw:
        return None, None
    match = SERIES_FIELD_PATTERN.match(raw)
    if match:
        name = match.group("name").strip().rstrip(",").strip()
        try:
            position = float(match.group("num"))
        except (TypeError, ValueError):
            position = None
        return (name or raw), position
    return raw, None


async def lookup_series_from_edition(isbn: str):
    """Fallback series lookup used when adding a book: if the title itself
    didn't encode a series (see parse_series_from_title), some Open Library
    editions carry a separate "series" field we can check via ISBN. Not
    every book has this either, but it catches a few more cases for free.
    Returns (series_name, series_position), both possibly None.
    """
    if not isbn:
        return None, None
    async with httpx.AsyncClient(timeout=8.0) as client:
        data = await _get_json(
            client,
            f"{OPEN_LIBRARY_BASE}/api/books",
            {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
        )
    if not data:
        return None, None
    edition = data.get(f"ISBN:{isbn}")
    if not edition:
        return None, None
    series_list = edition.get("series") or []
    if not series_list:
        return None, None
    return parse_series_field(series_list[0])
