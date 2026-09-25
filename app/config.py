import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/booktracker.db")
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "sk")
SUPPORTED_LANGUAGES = ["sk", "en"]

OPEN_LIBRARY_BASE = "https://openlibrary.org"
OPEN_LIBRARY_COVERS = "https://covers.openlibrary.org"

ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true").lower() == "true"
