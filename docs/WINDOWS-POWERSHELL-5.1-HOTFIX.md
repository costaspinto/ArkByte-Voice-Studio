# Windows PowerShell 5.1 installer hotfix — 1.2.0-HF1

## Root cause fixed

The previous installer invoked Python with `python -c` and embedded quoted string literals inside the inline code, for example `print("PyTorch", torch.__version__)`. Windows PowerShell 5.1's native argument marshalling can remove those inner quotes. Python then receives `print(PyTorch, torch.__version__)` and raises `NameError: name 'PyTorch' is not defined`. The package-import step was therefore reporting a PowerShell argument-quoting failure as if PyTorch itself were broken.

## Changes in HF1

- All installer Python validation and preflight commands now execute `.py` files, not inline `python -c` snippets.
- `verify_python_runtime.py` validates Python 3.12/3.13 and 64-bit architecture and prints the exact executable path. It is used by direct executable discovery and `py.exe` launcher discovery.
- `verify_ai_engine.py` verifies the PyTorch CPU tensor path and imports the exact `ChatterboxMultilingualTTS` class used by `service/arkbyte_voice_studio/engine.py`. CUDA detection is informational; CUDA being unavailable does not fail a valid CPU installation.
- `verify_backend_preflight.py` validates FastAPI, Uvicorn and NumPy with complete tracebacks on failure.
- The diagnostic PowerShell script uses the same file-based probes.
- The Python recovery script also uses a temporary `.py` probe file rather than `python -c`.

## What remains to be validated on the target PC

This build environment cannot execute Windows PowerShell 5.1, the Windows Python wheels, NVIDIA/CUDA, or the user's actual Chatterbox runtime. After HF1 installation, the console should show `AI ENGINE PREFLIGHT: PASS`, followed later by `BACKEND PREFLIGHT: PASS`, before the web build and startup checks. If the AI probe fails, its full Python traceback will identify the actual missing DLL, dependency conflict, or Chatterbox import problem rather than a mangled `python -c` command.
