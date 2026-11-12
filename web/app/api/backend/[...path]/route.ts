import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const backend = process.env.BACKEND_API_URL?.replace(/\/$/, "");
  const token = process.env.ADMIN_TOKEN;
  if (!backend || !token) {
    return Response.json(
      { detail: "工作台服务端未配置 BACKEND_API_URL 或 ADMIN_TOKEN。" },
      { status: 503 },
    );
  }

  const { path } = await context.params;
  const upstreamUrl = new URL(
    `${backend}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,
  );
  const headers = new Headers();
  headers.set("X-Admin-Token", token);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const requestId = request.headers.get("x-request-id");
  if (requestId) headers.set("X-Request-ID", requestId);

  try {
    const response = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer(),
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    const responseType = response.headers.get("content-type");
    if (responseType) responseHeaders.set("Content-Type", responseType);
    const upstreamRequestId = response.headers.get("x-request-id");
    if (upstreamRequestId) responseHeaders.set("X-Request-ID", upstreamRequestId);
    return new Response(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      { detail: "工作台无法连接 FastAPI 服务。" },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
