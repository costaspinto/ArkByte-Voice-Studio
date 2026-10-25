from __future__ import annotations

import uuid


class AppError(Exception):
    """Expected application error with a safe message for the UI."""

    def __init__(self, message: str, code: str = "APP_ERROR") -> None:
        super().__init__(message)
        self.user_message = message
        self.code = code


def error_reference() -> str:
    return uuid.uuid4().hex[:10].upper()


def friendly_error(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, AppError):
        return exc.user_message, exc.code
    name = type(exc).__name__
    if name in {"OutOfMemoryError", "CudaOutOfMemoryError"}:
        return ("The AI model ran out of GPU memory. Close other GPU applications, use a shorter script, or retry with CPU mode.", "AI_MEMORY")
    if isinstance(exc, FileNotFoundError):
        return ("A required file or executable could not be found. Check FFmpeg and the selected media file.", "FILE_NOT_FOUND")
    if isinstance(exc, PermissionError):
        return ("Windows denied access to a file or folder. Choose a folder you can write to and try again.", "PERMISSION_DENIED")
    if isinstance(exc, TimeoutError):
        return ("The operation took too long and was stopped. Try a shorter video segment or script.", "TIMEOUT")
    return ("The operation failed unexpectedly. Your project data has been preserved. See the application log for details.", "UNEXPECTED")
