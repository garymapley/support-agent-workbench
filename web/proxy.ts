import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE, verifySessionToken } from "@/lib/session";

export function proxy(request: NextRequest) {
  const session = verifySessionToken(
    request.cookies.get(SESSION_COOKIE)?.value,
  );
  if (session) return NextResponse.next();
  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json(
      { detail: "未登录或会话已过期。" },
      { status: 401 },
    );
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: ["/", "/api/backend/:path*"],
};
