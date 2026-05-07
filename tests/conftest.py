from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable for test files that exercise stub domain types.
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
