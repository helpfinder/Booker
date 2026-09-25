from collections import Counter, defaultdict
from datetime import date

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, Book, UserBook, ReadStatus
from app.deps import require_user, get_lang, get_t
from app.main import templates

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    t=Depends(get_t),
):
    rows = session.exec(
        select(UserBook, Book)
        .join(Book, UserBook.book_id == Book.id)
        .where(UserBook.user_id == user.id)
    ).all()

    read_entries = [(ub, b) for ub, b in rows if ub.status == ReadStatus.READ]
    reading_entries = [(ub, b) for ub, b in rows if ub.status == ReadStatus.READING]

    total_read = len(read_entries)
    this_year = date.today().year
    read_this_year = [
        (ub, b) for ub, b in read_entries if ub.date_finished and ub.date_finished.year == this_year
    ]

    ratings = [ub.rating for ub, b in read_entries if ub.rating]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    per_year: Counter = Counter()
    for ub, b in read_entries:
        if ub.date_finished:
            per_year[ub.date_finished.year] += 1
    years_sorted = sorted(per_year.keys())
    books_per_year = [{"year": y, "count": per_year[y]} for y in years_sorted]
    max_per_year = max([p["count"] for p in books_per_year], default=0)

    per_month = Counter()
    for ub, b in read_this_year:
        per_month[ub.date_finished.month] += 1
    month_names = {
        "sk": ["Jan", "Feb", "Mar", "Apr", "Máj", "Jún", "Júl", "Aug", "Sep", "Okt", "Nov", "Dec"],
        "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    }
    names = month_names.get(lang, month_names["en"])
    books_per_month = [{"month": names[m - 1], "count": per_month.get(m, 0)} for m in range(1, 13)]
    max_per_month = max([p["count"] for p in books_per_month], default=0)

    author_counter: Counter = Counter()
    for ub, b in read_entries:
        for author in (b.author_names or "").split(","):
            author = author.strip()
            if author:
                author_counter[author] += 1
    top_authors = author_counter.most_common(8)
    max_author_count = top_authors[0][1] if top_authors else 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "t": t,
            "lang": lang,
            "user": user,
            "total_read": total_read,
            "read_this_year_count": len(read_this_year),
            "avg_rating": avg_rating,
            "currently_reading": reading_entries,
            "books_per_year": books_per_year,
            "max_per_year": max_per_year,
            "books_per_month": books_per_month,
            "max_per_month": max_per_month,
            "top_authors": top_authors,
            "max_author_count": max_author_count,
            "has_data": total_read > 0,
        },
    )
