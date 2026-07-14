import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("GEMINI_API_KEY", "test-key")

import auth.models  # noqa: F401
import database.models  # noqa: F401
from database.session import engine
from database.base import Base

Base.metadata.create_all(bind=engine)
