"""Return success only for a supported 64-bit ArkByte Python runtime."""
from __future__ import annotations

import struct
import sys


def main() -> int:
    version = sys.version_info
    bits = struct.calcsize("P") * 8
    print(sys.executable)
    print("PYTHON_VERSION:", f"{version.major}.{version.minor}.{version.micro}")
    print("PYTHON_BITS:", bits)
    if (version.major, version.minor) not in {(3, 12), (3, 13)}:
        print("Unsupported Python version; ArkByte requires Python 3.12 or 3.13.", file=sys.stderr)
        return 2
    if bits != 64:
        print("Unsupported Python architecture; ArkByte requires 64-bit Python.", file=sys.stderr)
        return 3
    print("PYTHON RUNTIME: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
