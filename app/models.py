from datetime import datetime, date
from enum import Enum
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship


class ReadStatus(str, Enum):
    WANT_TO_READ = "want_to_read"
    READING = "reading"
    READ = "read"
    DNF = "dnf"  # did not finish


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    language: str = Field(default="sk")
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    books: List["UserBook"] = Relationship(back_populates="user")


class Book(SQLModel, table=True):
    """Cached metadata about a book, sourced from Open Library."""

    id: Optional[int] = Field(default=None, primary_key=True)
    ol_key: str = Field(index=True, unique=True)  # e.g. /works/OL45804W
    title: str
    author_names: str = ""  # comma separated
    first_publish_year: Optional[int] = None
    cover_id: Optional[int] = None
    isbn: Optional[str] = None
    series_name: Optional[str] = None
    series_position: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user_entries: List["UserBook"] = Relationship(back_populates="book")

    @property
    def cover_url(self) -> Optional[str]:
        if self.cover_id:
            return f"https://covers.openlibrary.org/b/id/{self.cover_id}-M.jpg"
        return None


class UserBook(SQLModel, table=True):
    """A book in a specific user's personal library."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    book_id: int = Field(foreign_key="book.id", index=True)

    status: ReadStatus = Field(default=ReadStatus.WANT_TO_READ)
    rating: Optional[int] = None  # 1-5
    notes: Optional[str] = None

    # per-user override of series info (in case the auto-detected one is wrong)
    series_name: Optional[str] = None
    series_position: Optional[float] = None

    date_started: Optional[date] = None
    date_finished: Optional[date] = None
    added_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="books")
    book: Optional[Book] = Relationship(back_populates="user_entries")

    def effective_series_name(self) -> Optional[str]:
        return self.series_name or (self.book.series_name if self.book else None)

    def effective_series_position(self) -> Optional[float]:
        if self.series_position is not None:
            return self.series_position
        return self.book.series_position if self.book else None
