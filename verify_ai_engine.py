"""Verify the exact Chatterbox/PyTorch imports used by ArkByte's runtime.

Run this file with the application's isolated Python interpreter. Using a .py
file (rather than PowerShell's native `python -c` argument) avoids Windows
PowerShell 5.1 stripping quotes inside Python source strings.
"""
from __future__ import annotations

import platform
import sys
import traceback


def main() -> int:
    print("Python executable:", sys.executable)
    print("Python version:", sys.version.replace("\n", " "))
    print("Platform:", platform.platform())
    print("Architecture:", platform.architecture()[0])

    try:
        import torch

        print("PyTorch:", torch.__version__)
        # Exercise a small CPU tensor operation; import success alone does not
        # catch every broken native-library installation.
        test_value = torch.tensor([1.0, 2.0], device="cpu").sum().item()
        if test_value != 3.0:
            raise RuntimeError("PyTorch CPU tensor smoke test returned an unexpected value")
        print("PyTorch CPU tensor smoke test: OK")
        try:
            cuda_available = bool(torch.cuda.is_available())
            print("CUDA available:", cuda_available)
            if not cuda_available:
                print("CUDA is unavailable; ArkByte will use its supported CPU path.")
        except Exception as exc:  # CUDA probe failure must not invalidate CPU mode.
            print("CUDA probe warning:", repr(exc))
            print("CPU mode remains available if the PyTorch CPU smoke test passed.")

        # Match the class that service/arkbyte_voice_studio/engine.py imports.
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        if not callable(getattr(ChatterboxMultilingualTTS, "from_pretrained", None)):
            raise RuntimeError(
                "ChatterboxMultilingualTTS is present but has no callable from_pretrained method"
            )
        print("Chatterbox multilingual runtime import: OK")
        print("AI ENGINE PREFLIGHT: PASS")
        return 0
    except Exception:
        print("AI ENGINE PREFLIGHT: FAIL", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
