import { NextResponse, type NextRequest } from "next/server";

import {
  authenticateWorkbenchUser,
  createSessionToken,
  SESSION_COOKIE,
  sessionCookieOptions,
} from "@/lib/session";
import { hasTrustedOrigin } from "@/lib/request-origin";

const attempts = new Map<string, number[]>();
const LOGIN_WINDOW_MS = 10 * 60 * 1000;
const LOGIN_ATTEMPTS = 5;

function loginAllowed(key: string) {
  const now = Date.now();
  const recent = (attempts.get(key) ?? []).filter(
    (timestamp) => timestamp > now - LOGIN_WINDOW_MS,
  );
  if (recent.length >= LOGIN_ATTEMPTS) return false;
  recent.push(now);
  attempts.set(key, recent);
  return true;
}

export async function POST(request: NextRequest) {
  if (!hasTrustedOrigin(request)) {
    return NextResponse.json({ detail: "跨站登录请求已被拒绝。" }, { status: 403 });
  }
  const client = request.headers.get("x-forwarded-for")?.split(",")[0]
    ?? "unknown";
  if (!loginAllowed(client)) {
    return NextResponse.json(
      { detail: "登录尝试过多，请稍后再试。" },
      { status: 429, headers: { "Retry-After": "600" } },
    );
  }
  const body = await request.json().catch(() => null) as {
    username?: unknown;
    password?: unknown;
  } | null;
  if (
    typeof body?.username !== "string"
    || typeof body.password !== "string"
    || body.username.length > 100
    || body.password.length > 200
  ) {
    return NextResponse.json({ detail: "登录信息格式不正确。" }, { status: 400 });
  }
  const session = authenticateWorkbenchUser(body.username, body.password);
  if (!session) {
    return NextResponse.json({ detail: "用户名或密码错误。" }, { status: 401 });
  }
  const response = NextResponse.json({
    username: session.username,
    role: session.role,
  });
  response.cookies.set(
    SESSION_COOKIE,
    createSessionToken(session),
    sessionCookieOptions(),
  );
  return response;
}
