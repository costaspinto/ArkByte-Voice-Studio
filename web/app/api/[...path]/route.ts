import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED_PATH = /^v1\/(health|models|enrollments|profiles(?:\/[a-f0-9]{32}(?:\/(?:detail|samples|samples\/[a-f0-9]{32}\/(?:transcript|transcribe)|anchor\/[a-f0-9]{32}|pronunciations(?:\/[a-f0-9]{32})?|training-export\/qwen3))?)?|profile-samples\/[a-f0-9]{32}\/audio|projects(?:\/[a-f0-9]{32})?|generations(?:\/[a-f0-9]{32})?|benchmarks\/[a-f0-9]{32}(?:\/speaker-identity)?|history(?:\/[a-f0-9]{32})?|audio\/[a-f0-9]{32})$/;

function localError(message: string, status: number, code: string) {
  return NextResponse.json({ ok: false, error: { code, message } }, { status });
}

function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return true;
  try {
    return new URL(origin).host === request.headers.get("host");
  } catch {
    return false;
  }
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const joined = path.join("/");
  if (!ALLOWED_PATH.test(joined)) return localError("The requested local API route is not available.", 404, "ROUTE_NOT_FOUND");

  if (!isSameOrigin(request)) return localError("Cross-origin requests are not allowed.", 403, "ORIGIN_REJECTED");

  const token = process.env.ARKBYTE_BRIDGE_TOKEN;
  const base = process.env.ARKBYTE_BRIDGE_URL || "http://127.0.0.1:8765";
  if (!token) return localError("Local bridge authentication is not configured. Run the Windows setup script again.", 503, "BRIDGE_NOT_CONFIGURED");

  const target = `${base.replace(/\/$/, "")}/api/${joined}${request.nextUrl.search}`;
  const headers = new Headers();
  headers.set("x-arkbyte-token", token);
  headers.set("x-request-id", crypto.randomUUID());
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);

  const method = request.method.toUpperCase();
  try {
    const init: RequestInit & { duplex?: "half" } = {
      method,
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(method === "POST" && (joined === "profiles" || joined === "enrollments" || /\/samples$/.test(joined) || /\/transcribe$/.test(joined)) ? 15 * 60_000 : 30_000)
    };
    if (method !== "GET" && method !== "HEAD") {
      init.body = request.body;
      init.duplex = "half";
    }

    const upstream = await fetch(target, init);
    const responseHeaders = new Headers();
    for (const key of ["content-type", "content-disposition", "content-length", "cache-control"]) {
      const value = upstream.headers.get(key);
      if (value) responseHeaders.set(key, value);
    }
    responseHeaders.set("Cache-Control", "no-store");
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch (error) {
    const isTimeout = error instanceof Error && error.name === "TimeoutError";
    return localError(
      isTimeout
        ? "The local service took too long to respond. Check its diagnostic log and try again."
        : "The local AI service is not responding. Start ArkByte Voice Studio Local Services and retry.",
      503,
      isTimeout ? "BRIDGE_TIMEOUT" : "BRIDGE_UNAVAILABLE"
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
export const PUT = proxy;
