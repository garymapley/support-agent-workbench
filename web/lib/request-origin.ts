import type { NextRequest } from "next/server";

export function hasTrustedOrigin(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (!origin) return true;
  try {
    const originUrl = new URL(origin);
    const forwardedHost = request.headers.get("x-forwarded-host")
      ?.split(",")[0]
      ?.trim();
    const requestHost = forwardedHost || request.headers.get("host");
    if (!requestHost || originUrl.host !== requestHost) return false;
    const forwardedProtocol = request.headers.get("x-forwarded-proto")
      ?.split(",")[0]
      ?.trim();
    return !forwardedProtocol
      || originUrl.protocol === `${forwardedProtocol}:`;
  } catch {
    return false;
  }
}
