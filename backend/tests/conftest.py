import os
import sys
from pathlib import Path

# Use a throwaway SQLite DB for tests; never touch the dev Postgres.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_darwin.sqlite")
# Tests use per-agent provider="stub" (no network), so no API keys are needed.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
