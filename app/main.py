from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY, BASE_DIR, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
from app.database import init_db
from app.deps import NotAuthenticated
from app.i18n import get_translator

app = FastAPI(title="Book Tracker")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.globals["supported_languages"] = SUPPORTED_LANGUAGES


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def index(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")


@app.get("/set-language/{lang}")
def set_language(lang: str, request: Request):
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    request.session["lang"] = lang
    next_url = request.query_params.get("next") or "/"
    return RedirectResponse(url=next_url)


from app.routers import auth as auth_router  # noqa: E402
from app.routers import books as books_router  # noqa: E402
from app.routers import library as library_router  # noqa: E402
from app.routers import dashboard as dashboard_router  # noqa: E402
from app.routers import series as series_router  # noqa: E402

app.include_router(auth_router.router)
app.include_router(books_router.router)
app.include_router(library_router.router)
app.include_router(dashboard_router.router)
app.include_router(series_router.router)
