import type { NextRequest } from "next/server";

import {
  backendTokenForRole,
  SESSION_COOKIE,
  verifySessionToken,
} from "@/lib/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const backend = process.env.BACKEND_API_URL?.replace(/\/$/, "");
  const session = verifySessionToken(
    request.cookies.get(SESSION_COOKIE)?.value,
  );
  if (!session) {
    return Response.json({ detail: "未登录或会话已过期。" }, { status: 401 });
  }
  let token: string;
  try {
    token = backendTokenForRole(session.role);
  } catch {
    return Response.json(
      { detail: "工作台服务端没有配置当前角色的后端令牌。" },
      { status: 503 },
    );
  }
  if (!backend) {
    return Response.json(
      { detail: "工作台服务端未配置 BACKEND_API_URL。" },
      { status: 503 },
    );
  }
  if (request.method !== "GET" && request.method !== "HEAD") {
    const origin = request.headers.get("origin");
    if (origin && origin !== request.nextUrl.origin) {
      return Response.json({ detail: "跨站请求已被拒绝。" }, { status: 403 });
    }
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
