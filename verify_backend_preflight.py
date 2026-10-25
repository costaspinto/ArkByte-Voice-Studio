"""Verify the backend packages using the selected isolated Python runtime."""
from __future__ import annotations

import sys
import traceback


def main() -> int:
    print("Python executable:", sys.executable)
    try:
        import fastapi
        import numpy
        import uvicorn

        print("FastAPI:", fastapi.__version__)
        print("Uvicorn:", uvicorn.__version__)
        print("NumPy:", numpy.__version__)
        print("BACKEND PREFLIGHT: PASS")
        return 0
    except Exception:
        print("BACKEND PREFLIGHT: FAIL", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
