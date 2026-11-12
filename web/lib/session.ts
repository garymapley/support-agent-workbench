import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export type WorkbenchRole = "operator" | "admin";

export type WorkbenchSession = {
  username: string;
  role: WorkbenchRole;
  exp: number;
};

export const SESSION_COOKIE = "support_agent_session";
export const SESSION_MAX_AGE_SECONDS = 8 * 60 * 60;

function sessionSecret() {
  const value = process.env.WORKBENCH_SESSION_SECRET ?? "";
  if (value.length < 32) {
    throw new Error("WORKBENCH_SESSION_SECRET 必须至少 32 个字符。");
  }
  return value;
}

function signature(payload: string) {
  return createHmac("sha256", sessionSecret())
    .update(payload)
    .digest("base64url");
}

function safeEqual(left: string, right: string) {
  const leftHash = createHash("sha256").update(left).digest();
  const rightHash = createHash("sha256").update(right).digest();
  return timingSafeEqual(leftHash, rightHash);
}

export function authenticateWorkbenchUser(
  username: string,
  password: string,
): WorkbenchSession | null {
  const accounts: Array<{
    username: string;
    password: string;
    role: WorkbenchRole;
  }> = [
    {
      username: process.env.WORKBENCH_OPERATOR_USERNAME ?? "operator",
      password: process.env.WORKBENCH_OPERATOR_PASSWORD ?? "",
      role: "operator",
    },
    {
      username: process.env.WORKBENCH_ADMIN_USERNAME ?? "admin",
      password: process.env.WORKBENCH_ADMIN_PASSWORD ?? "",
      role: "admin",
    },
  ];
  const account = accounts.find(
    (item) => item.password.length >= 12
      && safeEqual(username, item.username)
      && safeEqual(password, item.password),
  );
  if (!account) return null;
  return {
    username: account.username,
    role: account.role,
    exp: Math.floor(Date.now() / 1000) + SESSION_MAX_AGE_SECONDS,
  };
}

export function createSessionToken(session: WorkbenchSession) {
  const payload = Buffer.from(JSON.stringify(session)).toString("base64url");
  return `${payload}.${signature(payload)}`;
}

export function verifySessionToken(
  value: string | undefined,
): WorkbenchSession | null {
  if (!value) return null;
  try {
    const [payload, providedSignature] = value.split(".");
    if (!payload || !providedSignature) return null;
    if (!safeEqual(providedSignature, signature(payload))) return null;
    const session = JSON.parse(
      Buffer.from(payload, "base64url").toString("utf8"),
    ) as WorkbenchSession;
    if (
      !session.username
      || !["operator", "admin"].includes(session.role)
      || session.exp <= Math.floor(Date.now() / 1000)
    ) {
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function backendTokenForRole(role: WorkbenchRole) {
  const value = role === "admin"
    ? process.env.ADMIN_TOKEN
    : process.env.OPERATOR_TOKEN;
  if (!value) throw new Error(`未配置 ${role === "admin" ? "ADMIN_TOKEN" : "OPERATOR_TOKEN"}。`);
  return value;
}

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "strict" as const,
    secure: process.env.WORKBENCH_COOKIE_SECURE === "true",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  };
}
