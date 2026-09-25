from typing import Optional

from fastapi import Request, Depends
from sqlmodel import Session

from app.database import get_session
from app.models import User
from app.config import DEFAULT_LANGUAGE
from app.i18n import get_translator


class NotAuthenticated(Exception):
    """Raised when a route requires login but no user is in the session."""


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return session.get(User, user_id)


def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise NotAuthenticated()
    return user


def get_lang(request: Request, user: Optional[User] = Depends(get_current_user)) -> str:
    if user and user.language:
        return user.language
    return request.session.get("lang", DEFAULT_LANGUAGE)


def get_t(lang: str = Depends(get_lang)):
    return get_translator(lang)
