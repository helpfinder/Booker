from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, Book, UserBook, ReadStatus
from app.deps import require_user, get_lang, get_t
from app.main import templates

router = APIRouter()


@router.get("/library", response_class=HTMLResponse)
def library_page(
    request: Request,
    status: str = Query(default="all"),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    t=Depends(get_t),
):
    query = select(UserBook, Book).join(Book, UserBook.book_id == Book.id).where(
        UserBook.user_id == user.id
    )
    if status != "all":
        try:
            status_enum = ReadStatus(status)
            query = query.where(UserBook.status == status_enum)
        except ValueError:
            pass

    query = query.order_by(UserBook.added_at.desc())
    rows = session.exec(query).all()

    entries = [{"user_book": ub, "book": b} for ub, b in rows]

    # All distinct series names this user already has, so the "Séria" field
    # can suggest them (as a datalist) instead of making people retype an
    # existing series name by hand every time.
    all_rows = session.exec(
        select(UserBook, Book).join(Book, UserBook.book_id == Book.id).where(UserBook.user_id == user.id)
    ).all()
    series_names = sorted(
        {name for ub, b in all_rows if (name := ub.effective_series_name())}
    )

    return templates.TemplateResponse(
        "library.html",
        {
            "request": request,
            "t": t,
            "lang": lang,
            "user": user,
            "entries": entries,
            "current_status": status,
            "statuses": list(ReadStatus),
            "series_names": series_names,
        },
    )


def _get_owned_user_book(session: Session, user: User, user_book_id: int) -> Optional[UserBook]:
    ub = session.get(UserBook, user_book_id)
    if ub and ub.user_id == user.id:
        return ub
    return None


@router.post("/library/{user_book_id}/status")
def update_status(
    user_book_id: int,
    status: str = Form(...),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    ub = _get_owned_user_book(session, user, user_book_id)
    if ub:
        try:
            new_status = ReadStatus(status)
        except ValueError:
            new_status = ub.status
        ub.status = new_status
        if new_status == ReadStatus.READ and not ub.date_finished:
            ub.date_finished = date.today()
        if new_status == ReadStatus.READING and not ub.date_started:
            ub.date_started = date.today()
        session.add(ub)
        session.commit()

    next_url = "/library"
    referer = None
    return RedirectResponse(url=next_url, status_code=303)


@router.post("/library/{user_book_id}/edit")
def edit_entry(
    user_book_id: int,
    rating: str = Form(default=""),
    notes: str = Form(default=""),
    series_name: str = Form(default=""),
    series_position: str = Form(default=""),
    date_started: str = Form(default=""),
    date_finished: str = Form(default=""),
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    ub = _get_owned_user_book(session, user, user_book_id)
    if ub:
        ub.rating = int(rating) if rating.isdigit() else None
        ub.notes = notes or None
        ub.series_name = series_name.strip() or None

        # Series position must be a whole number >= 1 (sanity-bounded so a
        # stray value can't do anything worse than get ignored), and only
        # meaningful when there's an actual series name to go with it --
        # either just set above, or already inherited from the book itself.
        position = None
        if series_position.strip():
            try:
                candidate = int(series_position)
                if 1 <= candidate <= 9999:
                    position = candidate
            except ValueError:
                position = None

        effective_name = ub.series_name or (ub.book.series_name if ub.book else None)
        ub.series_position = position if effective_name else None

        try:
            ub.date_started = datetime.strptime(date_started, "%Y-%m-%d").date() if date_started else None
        except ValueError:
            pass
        try:
            ub.date_finished = datetime.strptime(date_finished, "%Y-%m-%d").date() if date_finished else None
        except ValueError:
            pass
        session.add(ub)
        session.commit()

    return RedirectResponse(url="/library", status_code=303)


@router.post("/library/{user_book_id}/remove")
def remove_entry(
    user_book_id: int,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    ub = _get_owned_user_book(session, user, user_book_id)
    if ub:
        session.delete(ub)
        session.commit()
    return RedirectResponse(url="/library", status_code=303)
