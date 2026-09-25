import sqlalchemy as sa
from sqlmodel import SQLModel, create_engine, Session
from app.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def _run_light_migrations() -> None:
    """Tiny hand-rolled migration: add any columns the models define that
    are missing from an already-created table.

    This app deliberately doesn't pull in Alembic to stay lightweight, but
    that means `SQLModel.metadata.create_all()` alone won't add new columns
    to a table that already exists from a previous run. This adds just
    enough to cover that case for simple, additive column changes.
    """
    inspector = sa.inspect(engine)
    if "book" not in inspector.get_table_names():
        return
    existing_cols = {c["name"] for c in inspector.get_columns("book")}
    with engine.begin() as conn:
        if "pages" not in existing_cols:
            conn.execute(sa.text("ALTER TABLE book ADD COLUMN pages INTEGER"))


def init_db() -> None:
    # models must be imported so SQLModel metadata knows about them
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _run_light_migrations()


def get_session():
    with Session(engine) as session:
        yield session
