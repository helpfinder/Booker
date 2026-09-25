from fastapi import APIRouter, Request, Depends, Query, Form
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, Book, UserBook, ReadStatus
from app.deps import require_user, get_lang, get_t
from app.openlibrary import search_books_smart, fetch_details
from app.main import templates

router = APIRouter()


@router.get("/book/details", response_class=HTMLResponse)
async def book_details(
    request: Request,
    ol_key: str = "",
    isbn: str = "",
    user: User = Depends(require_user),
    t=Depends(get_t),
):
    details = await fetch_details(ol_key, isbn)
    return templates.TemplateResponse(
        "partials/book_details.html",
        {"request": request, "t": t, "details": details},
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = Query(default=""),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    t=Depends(get_t),
):
    results = []
    if q.strip():
        results = await search_books_smart(q, limit=24)

    existing_keys = set(
        session.exec(
            select(Book.ol_key)
            .join(UserBook, UserBook.book_id == Book.id)
            .where(UserBook.user_id == user.id)
        ).all()
    )

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "t": t,
            "lang": lang,
            "user": user,
            "query": q,
            "results": results,
            "existing_keys": existing_keys,
            "statuses": list(ReadStatus),
        },
    )


def _get_or_create_book(session: Session, item: dict) -> Book:
    book = session.exec(select(Book).where(Book.ol_key == item["ol_key"])).first()
    if book:
        return book
    book = Book(
        ol_key=item["ol_key"],
        title=item["title"],
        author_names=item.get("author_names") or "",
        first_publish_year=item.get("first_publish_year"),
        cover_id=item.get("cover_id"),
        isbn=item.get("isbn"),
        pages=item.get("pages"),
        series_name=item.get("series_name"),
        series_position=item.get("series_position"),
    )
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


@router.post("/search/add", response_class=HTMLResponse)
async def add_from_search(
    request: Request,
    ol_key: str = Form(...),
    title: str = Form(...),
    author_names: str = Form(default=""),
    first_publish_year: str = Form(default=""),
    cover_id: str = Form(default=""),
    isbn: str = Form(default=""),
    pages: str = Form(default=""),
    series_name: str = Form(default=""),
    series_position: str = Form(default=""),
    status: str = Form(default=ReadStatus.WANT_TO_READ.value),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    t=Depends(get_t),
):
    item = {
        "ol_key": ol_key,
        "title": title,
        "author_names": author_names,
        "first_publish_year": int(first_publish_year) if first_publish_year.isdigit() else None,
        "cover_id": int(cover_id) if cover_id.isdigit() else None,
        "isbn": isbn or None,
        "pages": int(pages) if pages.isdigit() else None,
        "series_name": series_name or None,
        "series_position": float(series_position) if series_position else None,
    }
    book = _get_or_create_book(session, item)

    existing = session.exec(
        select(UserBook).where(UserBook.user_id == user.id, UserBook.book_id == book.id)
    ).first()

    if not existing:
        try:
            status_enum = ReadStatus(status)
        except ValueError:
            status_enum = ReadStatus.WANT_TO_READ
        user_book = UserBook(user_id=user.id, book_id=book.id, status=status_enum)
        session.add(user_book)
        session.commit()

    return templates.TemplateResponse(
        "partials/added_badge.html", {"request": request, "t": t}
    )
