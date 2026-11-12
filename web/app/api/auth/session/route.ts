import { type NextRequest } from "next/server";

import { SESSION_COOKIE, verifySessionToken } from "@/lib/session";

export function GET(request: NextRequest) {
  const session = verifySessionToken(
    request.cookies.get(SESSION_COOKIE)?.value,
  );
  if (!session) {
    return Response.json({ detail: "未登录或会话已过期。" }, { status: 401 });
  }
  return Response.json({ username: session.username, role: session.role });
}
