export type Ticket = {
  ticket_id: string;
  order_id: string;
  issue_type: string;
  description: string;
  proposed_action: string;
  risk_level: "low" | "medium" | "high";
  status: string;
  handoff_reason: string | null;
  thread_id: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Approval = {
  approval_id: string;
  ticket_id: string;
  order_id: string;
  thread_id: string | null;
  action_type: string;
  amount: number;
  reason: string;
  status: "pending" | "approved" | "rejected";
  reviewer: string | null;
  review_comment: string | null;
  reviewed_at: string | null;
  requested_at: string | null;
};

export type Order = {
  order_id: string;
  customer_name: string;
  product_name: string;
  amount: number;
  status: string;
  refund_status: string;
  [key: string]: unknown;
};

export type ToolCall = { id?: string; name: string; args: Record<string, unknown> };
export type ToolResult = { tool_call_id?: string; name?: string; content: string };

export type AgentRun = {
  run_id: string | null;
  thread_id: string;
  status: "completed" | "waiting_for_approval";
  waiting_for_approval: boolean;
  approval_id: string | null;
  answer: string;
  tool_calls: ToolCall[];
  tool_results: ToolResult[];
};

export type HistoryMessage = {
  id: string | null;
  type: "human" | "ai" | "tool" | "system";
  content: string | Array<unknown>;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  name?: string;
};

export type RunRecord = {
  run_id: string;
  thread_id: string;
  status: string;
  tools: string[];
  latency_ms: number;
  total_tokens: number;
  created_at: string | null;
};

export type Summary = {
  run_count: number;
  success_rate: number;
  average_latency_ms: number;
  total_tokens: number;
  estimated_cost_cny: number | null;
  tool_usage: Record<string, number>;
};
