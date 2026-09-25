from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import User
from app.security import hash_password, verify_password
from app.deps import get_current_user, get_lang, get_t
from app.config import ALLOW_REGISTRATION
from app.main import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, lang: str = Depends(get_lang), t=Depends(get_t)):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "t": t, "lang": lang, "error": None},
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/dashboard"),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    t=Depends(get_t),
):
    user = session.exec(select(User).where(User.email == email.strip().lower())).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "t": t, "lang": lang, "error": t("auth.error_invalid")},
            status_code=400,
        )
    request.session["user_id"] = user.id
    request.session["lang"] = user.language
    return RedirectResponse(url=next or "/dashboard", status_code=303)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, lang: str = Depends(get_lang), t=Depends(get_t)):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "t": t, "lang": lang, "error": None, "allow_registration": ALLOW_REGISTRATION},
    )


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    session: Session = Depends(get_session),
    lang: str = Depends(get_lang),
    t=Depends(get_t),
):
    ctx = {"request": request, "t": t, "lang": lang, "allow_registration": ALLOW_REGISTRATION}

    if not ALLOW_REGISTRATION:
        ctx["error"] = t("auth.registration_disabled")
        return templates.TemplateResponse("register.html", ctx, status_code=403)

    email_norm = email.strip().lower()
    username_norm = username.strip()

    if password != password_confirm:
        ctx["error"] = t("auth.error_password_mismatch")
        return templates.TemplateResponse("register.html", ctx, status_code=400)

    if len(password) < 8:
        ctx["error"] = t("auth.error_password_short")
        return templates.TemplateResponse("register.html", ctx, status_code=400)

    if session.exec(select(User).where(User.email == email_norm)).first():
        ctx["error"] = t("auth.error_email_taken")
        return templates.TemplateResponse("register.html", ctx, status_code=400)

    if session.exec(select(User).where(User.username == username_norm)).first():
        ctx["error"] = t("auth.error_username_taken")
        return templates.TemplateResponse("register.html", ctx, status_code=400)

    user = User(
        email=email_norm,
        username=username_norm,
        password_hash=hash_password(password),
        language=lang,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    request.session["user_id"] = user.id
    request.session["lang"] = user.language
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")


@router.post("/account/language")
def change_language(
    request: Request,
    language: str = Form(...),
    user=Depends(get_current_user),
    session: Session = Depends(get_session),
):
    from app.config import SUPPORTED_LANGUAGES

    if language in SUPPORTED_LANGUAGES:
        request.session["lang"] = language
        if user:
            user.language = language
            session.add(user)
            session.commit()
    next_url = request.headers.get("referer", "/dashboard")
    return RedirectResponse(url=next_url, status_code=303)
