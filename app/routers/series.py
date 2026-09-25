from collections import defaultdict

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, Book, UserBook, ReadStatus
from app.deps import require_user, get_lang, get_t
from app.openlibrary import search_by_author_or_series
from app.main import templates

router = APIRouter()


@router.get("/series", response_class=HTMLResponse)
def series_list(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    t=Depends(get_t),
):
    rows = session.exec(
        select(UserBook, Book).join(Book, UserBook.book_id == Book.id).where(UserBook.user_id == user.id)
    ).all()

    groups = defaultdict(list)
    for ub, b in rows:
        series_name = ub.effective_series_name()
        if series_name:
            groups[series_name].append((ub, b))

    series_summaries = []
    for name, entries in groups.items():
        entries_sorted = sorted(
            entries, key=lambda pair: (pair[0].effective_series_position() or 0)
        )
        read_count = sum(1 for ub, b in entries_sorted if ub.status == ReadStatus.READ)
        authors = set()
        for ub, b in entries_sorted:
            for a in (b.author_names or "").split(","):
                a = a.strip()
                if a:
                    authors.add(a)
        series_summaries.append(
            {
                "name": name,
                "entries": entries_sorted,
                "total": len(entries_sorted),
                "read_count": read_count,
                "authors": sorted(authors),
            }
        )

    series_summaries.sort(key=lambda s: s["name"].lower())

    return templates.TemplateResponse(
        "series.html",
        {
            "request": request,
            "t": t,
            "lang": lang,
            "user": user,
            "series_summaries": series_summaries,
        },
    )


@router.get("/series/find", response_class=HTMLResponse)
async def series_find_more(
    request: Request,
    name: str,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    t=Depends(get_t),
):
    results = await search_by_author_or_series(name, limit=40)

    owned_keys = set(
        session.exec(
            select(Book.ol_key)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(UserBook.user_id == user.id)
        ).all()
    )

    # keep only results that look like they belong to this series
    name_lower = name.lower()
    filtered = [
        r for r in results
        if (r.get("series_name") and r["series_name"].lower() == name_lower)
    ]
    if not filtered:
        # fall back to everything found, since series tagging on Open Library is inconsistent
        filtered = results

    return templates.TemplateResponse(
        "partials/series_search_results.html",
        {
            "request": request,
            "t": t,
            "results": filtered,
            "owned_keys": owned_keys,
            "series_name": name,
        },
    )
