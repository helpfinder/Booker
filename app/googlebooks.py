"""Thin client for the (free, keyless) Google Books API.

Used only for the on-demand "details" panel: Open Library's search index
gives us enough to list and add books, but Google Books tends to have
richer per-edition metadata (publisher, exact publish date, description)
and often a better cover image, so we fetch it lazily only when someone
actually asks to see it rather than for every search result up front.
"""
from typing import Optional

import httpx

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


async def fetch_details(title: str, author_names: str = "", isbn: Optional[str] = None) -> Optional[dict]:
    query_parts = []
    if isbn:
        query_parts.append(f"isbn:{isbn}")
    else:
        if title:
            query_parts.append(f'intitle:"{title}"')
        first_author = (author_names or "").split(",")[0].strip()
        if first_author:
            query_parts.append(f'inauthor:"{first_author}"')

    if not query_parts:
        return None

    params = {"q": " ".join(query_parts), "maxResults": 1}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GOOGLE_BOOKS_API, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return None

    items = data.get("items") or []
    if not items:
        return None

    info = items[0].get("volumeInfo", {})
    image_links = info.get("imageLinks") or {}
    cover = image_links.get("thumbnail") or image_links.get("smallThumbnail")
    if cover:
        cover = cover.replace("http://", "https://")

    return {
        "publisher": info.get("publisher"),
        "published_date": info.get("publishedDate"),
        "page_count": info.get("pageCount"),
        "language": info.get("language"),
        "description": info.get("description"),
        "categories": info.get("categories") or [],
        "cover_url": cover,
        "average_rating": info.get("averageRating"),
    }
