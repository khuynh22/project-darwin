import os
import sys
import tempfile
from pathlib import Path

# Use a throwaway SQLite DB for tests; never touch the dev Postgres.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_darwin.sqlite")
# Same rule for the traces the turn loop streams: any test that runs a turn
# writes one, and they do not belong in the working tree.
os.environ.setdefault(
    "RUNS_DIR", str(Path(tempfile.gettempdir()) / "darwin-test-runs")
)
# Tests use per-agent provider="stub" (no network), so no API keys are needed.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
