from __future__ import annotations

import sys
from pathlib import Path

# Allow running uvicorn from inside backend/app during local development.
REPO_DIR = Path(__file__).resolve().parents[2]
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from backend.app.main import app
