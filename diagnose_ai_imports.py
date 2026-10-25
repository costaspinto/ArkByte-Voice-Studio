import sys
import traceback
import importlib
import importlib.metadata

print("PYTHON:", sys.version)
print("EXECUTABLE:", sys.executable)

for package in ["torch", "chatterbox-tts", "transformers", "torchaudio"]:
    try:
        print("PACKAGE:", package, importlib.metadata.version(package))
    except Exception as exc:
        print("PACKAGE MISSING:", package, repr(exc))

for module in ["torch", "chatterbox", "chatterbox.mtl_tts"]:
    print("\nTESTING IMPORT:", module)
    try:
        imported = importlib.import_module(module)
        print("IMPORT SUCCESS:", module)
        if module == "torch":
            print("TORCH VERSION:", imported.__version__)
            print("CUDA AVAILABLE:", imported.cuda.is_available())
    except Exception:
        print("IMPORT FAILED:", module)
        traceback.print_exc()
