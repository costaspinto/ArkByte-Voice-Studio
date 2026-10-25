import type { ApiError } from "./types";

export class StudioApiError extends Error {
  readonly code: string;
  readonly status: number;
  constructor(message: string, code = "REQUEST_FAILED", status = 500) {
    super(message);
    this.name = "StudioApiError";
    this.code = code;
    this.status = status;
  }
}

function isApiError(value: unknown): value is ApiError {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ApiError>;
  return candidate.ok === false && Boolean(candidate.error && typeof candidate.error.message === "string");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init.headers);
    response = await fetch(path, {
      ...init,
      headers,
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new StudioApiError(
      "The local AI service could not be reached. Start ArkByte Voice Studio Local Services and retry.",
      "LOCAL_SERVICE_OFFLINE",
      503
    );
  }

  const contentType = response.headers.get("content-type") || "";
  const payload: unknown = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : null;

  if (!response.ok) {
    if (isApiError(payload)) {
      throw new StudioApiError(payload.error.message, payload.error.code, response.status);
    }
    throw new StudioApiError(
      `The local service returned HTTP ${response.status}. Check its diagnostic log.`,
      "REQUEST_FAILED",
      response.status
    );
  }

  if (payload === null) {
    throw new StudioApiError(
      "The local service returned an unreadable response. Restart the local services and retry.",
      "INVALID_RESPONSE",
      502
    );
  }
  return payload as T;
}
