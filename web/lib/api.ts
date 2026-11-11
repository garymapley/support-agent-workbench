import type { AgentRun, Approval, HistoryMessage, Order, RunRecord, Summary, Ticket } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
// 演示级鉴权：令牌随前端包下发，生产应改为登录态（见 README「已知限制」）。
const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(ADMIN_TOKEN ? { "X-Admin-Token": ADMIN_TOKEN } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  tickets: () => request<Ticket[]>("/tickets?limit=100"),
  approvals: () => request<Approval[]>("/approvals?limit=100"),
  orders: () => request<Order[]>("/orders?limit=100"),
  summary: () => request<Summary>("/observability/summary?scope=runtime"),
  runs: () => request<RunRecord[]>("/observability/runs?scope=runtime&limit=20"),
  history: (threadId: string) =>
    request<{ thread_id: string; messages: HistoryMessage[] }>(`/agent/threads/${encodeURIComponent(threadId)}/history`),
  runAgent: (message: string, threadId?: string) =>
    request<AgentRun>("/agent/runs", {
      method: "POST",
      body: JSON.stringify({ message, thread_id: threadId }),
    }),
  decide: (approvalId: string, decision: "approve" | "reject", reviewer: string, comment: string) =>
    request<{ approval: Approval; ticket: Ticket; agent_run: AgentRun }>(`/approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, reviewer, comment }),
    }),
  handoff: (ticketId: string, reason: string) =>
    request<Ticket>(`/tickets/${ticketId}/handoff`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
};
