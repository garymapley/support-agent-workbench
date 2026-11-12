"use client";

import {
  Activity,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleUserRound,
  Clock3,
  Database,
  Handshake,
  Inbox,
  LoaderCircle,
  LogOut,
  MessageSquareText,
  RefreshCw,
  Search,
  ShieldCheck,
  Wrench,
  UserRoundCheck,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { api, type WorkbenchSession } from "@/lib/api";
import type { AgentRun, Approval, HistoryMessage, Order, RunRecord, Summary, Ticket } from "@/lib/types";

type Filter = "all" | "pending" | "handoff";
type LoadState = "loading" | "full" | "empty" | "error";

const statusLabels: Record<string, string> = {
  open: "待处理",
  pending_approval: "待审批",
  approved_pending_execution: "已通过",
  approval_rejected: "已驳回",
  human_handoff: "人工接管",
};

const riskLabels: Record<string, string> = { low: "低风险", medium: "中风险", high: "高风险" };

function formatTime(value: string | null) {
  if (!value) return "时间未记录";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function formatContent(content: HistoryMessage["content"]) {
  return typeof content === "string" ? content : JSON.stringify(content, null, 2);
}

function ticketThreadKey(ticketId: string) {
  return `support-agent-thread:${ticketId}`;
}

export default function WorkbenchPage() {
  const router = useRouter();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryMessage[]>([]);
  const [lastRun, setLastRun] = useState<AgentRun | null>(null);
  const [message, setMessage] = useState("");
  const [agentBusy, setAgentBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [reviewer, setReviewer] = useState("售后值班主管");
  const [comment, setComment] = useState("");
  const [handoffReason, setHandoffReason] = useState("需要人工专员核实客户诉求并跟进。");
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [session, setSession] = useState<WorkbenchSession | null>(null);

  const loadWorkspace = useCallback(async () => {
    try {
      const [ticketData, approvalData, orderData, summaryData, runData] = await Promise.all([
        api.tickets(), api.approvals(), api.orders(), api.summary(), api.runs(),
      ]);
      setTickets(ticketData);
      setApprovals(approvalData);
      setOrders(orderData);
      setSummary(summaryData);
      setRuns(runData);
      setLoadState(ticketData.length ? "full" : "empty");
      const preferredId = new URLSearchParams(window.location.search).get("ticket");
      setSelectedId((current) => {
        if (current && ticketData.some((ticket) => ticket.ticket_id === current)) return current;
        if (preferredId && ticketData.some((ticket) => ticket.ticket_id === preferredId)) return preferredId;
        return ticketData[0]?.ticket_id ?? null;
      });
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "工作台数据加载失败。");
      setLoadState("error");
    }
  }, []);

  useEffect(() => {
    void api.session().then((current) => {
      setSession(current);
      setReviewer(current.username);
    }).catch(() => router.replace("/login"));
  }, [router]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadWorkspace(), 0);
    return () => window.clearTimeout(timer);
  }, [loadWorkspace]);

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        await api.health();
        if (!cancelled) setApiOnline(true);
      } catch {
        if (!cancelled) setApiOnline(false);
      }
    };
    void probe();
    const timer = window.setInterval(() => void probe(), 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const filteredTickets = useMemo(() => tickets.filter((ticket) => {
    const matchesFilter = filter === "all"
      || (filter === "pending" && ticket.status === "pending_approval")
      || (filter === "handoff" && ticket.status === "human_handoff");
    const needle = query.trim().toLowerCase();
    const matchesQuery = !needle || [ticket.ticket_id, ticket.order_id, ticket.description].some((value) => value.toLowerCase().includes(needle));
    return matchesFilter && matchesQuery;
  }), [filter, query, tickets]);

  const selectedTicket = tickets.find((ticket) => ticket.ticket_id === selectedId) ?? null;
  const selectedOrder = orders.find((order) => order.order_id === selectedTicket?.order_id) ?? null;
  const selectedApproval = approvals.find((approval) => approval.ticket_id === selectedId) ?? null;

  const loadHistory = useCallback(async (ticketId: string) => {
    const approval = approvals.find((item) => item.ticket_id === ticketId);
    const stored = window.localStorage.getItem(ticketThreadKey(ticketId));
    const ticketThread = tickets.find((ticket) => ticket.ticket_id === ticketId)?.thread_id;
    const rawThread = stored ?? ticketThread ?? approval?.thread_id ?? "";
    const threadId = rawThread.replace(/^agent:/, "");
    if (!threadId) {
      setHistory([]);
      return;
    }
    try {
      const result = await api.history(threadId);
      setHistory(result.messages.filter((item) => item.type !== "system"));
    } catch {
      setHistory([]);
    }
  }, [approvals, tickets]);

  useEffect(() => {
    if (selectedId) {
      window.history.replaceState(null, "", `?ticket=${encodeURIComponent(selectedId)}`);
      const timer = window.setTimeout(() => void loadHistory(selectedId), 0);
      return () => window.clearTimeout(timer);
    }
  }, [loadHistory, selectedId]);

  function selectTicket(ticketId: string) {
    setSelectedId(ticketId);
    setHistory([]);
    setLastRun(null);
    setNotice("");
    setActionError("");
  }

  function refreshWorkspace() {
    setLoadState("loading");
    setLoadError("");
    void loadWorkspace();
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!message.trim() || agentBusy || !selectedTicket) return;
    setAgentBusy(true);
    setActionError("");
    setNotice("");
    try {
      const storedThread = window.localStorage.getItem(ticketThreadKey(selectedTicket.ticket_id));
      const context = `当前工单 ${selectedTicket.ticket_id}，订单 ${selectedTicket.order_id}。${message.trim()}`;
      const result = await api.runAgent(context, storedThread ?? undefined);
      window.localStorage.setItem(ticketThreadKey(selectedTicket.ticket_id), result.thread_id);
      setLastRun(result);
      setMessage("");
      setNotice(result.waiting_for_approval ? "Agent 已暂停，正在等待人工审批。" : "Agent 已完成本轮处理。");
      await Promise.all([loadHistory(selectedTicket.ticket_id), loadWorkspace()]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Agent 调用失败。");
    } finally {
      setAgentBusy(false);
    }
  }

  async function decide(decision: "approve" | "reject") {
    if (!selectedApproval || actionBusy || !reviewer.trim() || session?.role !== "admin") return;
    setActionBusy(true);
    setActionError("");
    setNotice("");
    try {
      const result = await api.decide(selectedApproval.approval_id, decision, reviewer.trim(), comment.trim());
      setLastRun(result.agent_run);
      setNotice(decision === "approve" ? "审批已通过，Agent 已恢复处理。" : "审批已驳回，Agent 已收到结果。");
      setComment("");
      await loadWorkspace();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "审批提交失败。");
    } finally {
      setActionBusy(false);
    }
  }

  async function logout() {
    try {
      await api.logout();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  async function handoff() {
    if (!selectedTicket || actionBusy || !handoffReason.trim()) return;
    setActionBusy(true);
    setActionError("");
    setNotice("");
    try {
      await api.handoff(selectedTicket.ticket_id, handoffReason.trim());
      setNotice("工单已转交人工队列。");
      await loadWorkspace();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "转人工失败。");
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <main className="workbench" id="main">
      <a className="skip-link" href="#ticket-detail">跳到工单详情</a>
      <header className="topbar">
        <div className="brand" aria-label="售后工单工作台">
          <span className="brand-mark" aria-hidden="true"><ShieldCheck size={20} /></span>
          <div><strong>售后工单工作台</strong><span>Agent 处理与人工审批</span></div>
        </div>
        <div className="topbar-status" role="status">
          <span className="connection" data-error={apiOnline === false}><span aria-hidden="true" />{apiOnline === null ? "正在连接 FastAPI" : apiOnline ? "FastAPI 已连接" : "FastAPI 未连接"}</span>
          {session && <span className="session-badge"><strong>{session.username}</strong><small>{session.role === "admin" ? "审批管理员" : "操作员"}</small></span>}
          <button className="icon-button" type="button" onClick={refreshWorkspace} aria-label="刷新工作台" disabled={loadState === "loading"}>
            <RefreshCw size={18} className={loadState === "loading" ? "spin" : ""} />
          </button>
          <button className="icon-button" type="button" onClick={() => void logout()} aria-label="退出登录">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <section className="metric-strip" aria-label="实时运行指标">
        <Metric label="运行次数" value={summary ? String(summary.run_count) : "…"} />
        <Metric label="成功率" value={summary ? `${(summary.success_rate * 100).toFixed(0)}%` : "…"} />
        <Metric label="平均延迟" value={summary ? `${Math.round(summary.average_latency_ms)} ms` : "…"} />
        <Metric label="待人工审批" value={String(approvals.filter((item) => item.status === "pending").length)} emphasis />
      </section>

      <div className="workspace-grid">
        <aside className="queue-panel" aria-label="工单队列">
          <div className="panel-heading">
            <div><h1>工单队列</h1><p>{tickets.length} 条工单</p></div>
            <Inbox size={20} aria-hidden="true" />
          </div>
          <label className="search-field">
            <span className="visually-hidden">搜索工单</span>
            <Search size={17} aria-hidden="true" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="工单号、订单号或问题" type="search" name="ticket-search" autoComplete="off" />
          </label>
          <div className="filter-tabs" role="tablist" aria-label="工单筛选">
            {([['all', '全部'], ['pending', '待审批'], ['handoff', '已转人工']] as const).map(([value, label]) => (
              <button type="button" role="tab" aria-selected={filter === value} key={value} onClick={() => setFilter(value)}>{label}</button>
            ))}
          </div>
          <div className="ticket-list">
            {loadState === "loading" && <QueueSkeleton />}
            {loadState === "error" && <StatePanel icon={<X size={22} />} title="工单没有加载" detail={loadError} action="重新加载" onAction={refreshWorkspace} />}
            {loadState === "empty" && <StatePanel icon={<Inbox size={22} />} title="队列还是空的" detail="当 Agent 创建工单后，它会出现在这里。" />}
            {loadState === "full" && filteredTickets.length === 0 && <StatePanel icon={<Search size={22} />} title="没有匹配工单" detail="调整搜索词或切换筛选条件。" />}
            {filteredTickets.map((ticket) => (
              <button className="ticket-row" data-selected={selectedId === ticket.ticket_id} type="button" key={ticket.ticket_id} onClick={() => selectTicket(ticket.ticket_id)}>
                <span className="ticket-row-top"><strong>{ticket.ticket_id}</strong><span className={`status status-${ticket.status}`}>{statusLabels[ticket.status] ?? ticket.status}</span></span>
                <span className="ticket-description">{ticket.description}</span>
                <span className="ticket-meta"><span>{ticket.order_id}</span><time>{formatTime(ticket.created_at)}</time><ChevronRight size={16} aria-hidden="true" /></span>
              </button>
            ))}
          </div>
        </aside>

        <section className="detail-panel" id="ticket-detail">
          {selectedTicket ? (
            <>
              <header className="detail-header">
                <div>
                  <div className="detail-title-line"><h2>{selectedTicket.ticket_id}</h2><span className={`risk risk-${selectedTicket.risk_level}`}>{riskLabels[selectedTicket.risk_level]}</span></div>
                  <p>{selectedTicket.description}</p>
                </div>
                <span className={`status status-${selectedTicket.status}`}>{statusLabels[selectedTicket.status] ?? selectedTicket.status}</span>
              </header>

              <dl className="order-ledger">
                <div><dt>订单</dt><dd className="mono">{selectedTicket.order_id}</dd></div>
                <div><dt>客户</dt><dd>{selectedOrder?.customer_name ?? "未读取"}</dd></div>
                <div><dt>商品</dt><dd>{selectedOrder?.product_name ?? "未读取"}</dd></div>
                <div><dt>金额</dt><dd className="mono">{selectedOrder ? `¥${selectedOrder.amount.toFixed(2)}` : "未读取"}</dd></div>
              </dl>

              <div className="trace-heading"><div><h2>工单处理轨迹</h2><p>对话、工具调用和人工决策在同一条时间线中。</p></div><Activity size={20} aria-hidden="true" /></div>
              <div className="trace" aria-live="polite">
                <TraceEvent icon={<MessageSquareText size={17} />} title="客户问题" meta={formatTime(selectedTicket.created_at)} body={selectedTicket.description} />
                {history.map((item, index) => (
                  <TraceEvent
                    key={item.id ?? `${item.type}-${index}`}
                    icon={item.type === "human" ? <CircleUserRound size={17} /> : item.type === "tool" ? <Wrench size={17} /> : <Bot size={17} />}
                    title={item.type === "human" ? "客户补充" : item.type === "tool" ? `工具结果：${item.name ?? "tool"}` : "Agent 回复"}
                    body={formatContent(item.content)}
                    toolCalls={item.tool_calls}
                  />
                ))}
                {lastRun?.tool_calls.map((tool) => <TraceEvent key={tool.id ?? tool.name} icon={<Database size={17} />} title={`调用工具：${tool.name}`} body={JSON.stringify(tool.args, null, 2)} code />)}
                {selectedApproval && <TraceEvent icon={<UserRoundCheck size={17} />} title="人工审批" meta={selectedApproval.status === "pending" ? "等待决策" : `已${selectedApproval.status === "approved" ? "通过" : "驳回"}`} body={selectedApproval.review_comment ?? selectedApproval.reason} />}
                {selectedTicket.status === "human_handoff" && <TraceEvent icon={<Handshake size={17} />} title="人工接管" body={selectedTicket.handoff_reason ?? "工单已转人工处理。"} />}
              </div>

              <form className="agent-composer" onSubmit={sendMessage}>
                <label htmlFor="agent-message">给 Agent 下达处理指令</label>
                <div className="composer-row">
                  <textarea id="agent-message" name="agent-message" value={message} onChange={(event) => setMessage(event.target.value)} placeholder="例如：查询该订单退款政策，并给出下一步。" rows={2} disabled={agentBusy} />
                  <button className="primary-button" type="submit" disabled={agentBusy || !message.trim()} aria-busy={agentBusy}>
                    {agentBusy ? <><LoaderCircle className="spin" size={18} />处理中</> : <><Bot size={18} />运行 Agent</>}
                  </button>
                </div>
              </form>
            </>
          ) : <StatePanel icon={<Inbox size={24} />} title="选择一条工单" detail="工单详情、Agent 轨迹和审批会显示在这里。" />}
        </section>

        <aside className="review-panel" aria-label="人工处理">
          <div className="panel-heading"><div><h2>人工决策</h2><p>审批或接管当前工单</p></div><UserRoundCheck size={20} aria-hidden="true" /></div>
          {selectedApproval ? (
            <section className="approval-sheet">
              <div className="approval-title"><span className="approval-seal"><ShieldCheck size={20} /></span><div><strong>{selectedApproval.approval_id}</strong><span>{selectedApproval.status === "pending" ? "需要人工决策" : "审批已完成"}</span></div></div>
              <dl className="approval-facts">
                <div><dt>操作</dt><dd>退款</dd></div>
                <div><dt>金额</dt><dd className="mono">¥{selectedApproval.amount.toFixed(2)}</dd></div>
                <div><dt>请求时间</dt><dd>{formatTime(selectedApproval.requested_at)}</dd></div>
              </dl>
              <p className="approval-reason">{selectedApproval.reason}</p>
              {selectedApproval.status === "pending" && session?.role === "admin" ? (
                <div className="decision-form">
                  <label htmlFor="reviewer">审批人</label>
                  <input id="reviewer" name="reviewer" value={reviewer} readOnly aria-readonly="true" />
                  <label htmlFor="review-comment">审批意见</label>
                  <textarea id="review-comment" name="review-comment" value={comment} onChange={(event) => setComment(event.target.value)} rows={3} placeholder="说明通过或驳回依据" disabled={actionBusy} />
                  <div className="decision-actions">
                    <button className="secondary-button" type="button" onClick={() => void decide("reject")} disabled={actionBusy || !reviewer.trim()}><X size={17} />驳回</button>
                    <button className="primary-button" type="button" onClick={() => void decide("approve")} disabled={actionBusy || !reviewer.trim()} aria-busy={actionBusy}><Check size={17} />通过</button>
                  </div>
                </div>
              ) : selectedApproval.status === "pending" ? (
                <div className="permission-note"><ShieldCheck size={20} /><div><strong>等待审批管理员处理</strong><span>操作员可以查看申请，但不能批准或驳回退款。</span></div></div>
              ) : (
                <div className="decision-result"><CheckCircle2 size={20} /><div><strong>{selectedApproval.status === "approved" ? "已通过" : "已驳回"}</strong><span>{selectedApproval.reviewer ?? "未记录审批人"}</span></div></div>
              )}
            </section>
          ) : (
            <StatePanel icon={<ShieldCheck size={22} />} title="当前无审批" detail="退款工单会由代码规则强制进入人工审批。" />
          )}

          {selectedTicket && selectedTicket.status !== "human_handoff" && selectedApproval?.status !== "pending" && (
            <section className="handoff-box">
              <div><h3>转人工接管</h3><p>Agent 无法继续时，将工单交给人工队列。</p></div>
              <label htmlFor="handoff-reason">接管原因</label>
              <textarea id="handoff-reason" name="handoff-reason" value={handoffReason} onChange={(event) => setHandoffReason(event.target.value)} rows={3} disabled={actionBusy} />
              <button className="secondary-button full-button" type="button" onClick={() => void handoff()} disabled={actionBusy || !handoffReason.trim()}><Handshake size={17} />转人工</button>
            </section>
          )}

          {(notice || actionError) && <div className={actionError ? "inline-message error-message" : "inline-message success-message"} role="status">{actionError || notice}</div>}

          <section className="recent-runs">
            <div className="recent-runs-heading"><h3>最近运行</h3><Clock3 size={17} aria-hidden="true" /></div>
            {runs.length ? runs.slice(0, 4).map((run) => (
              <div className="run-row" key={run.run_id}><span><strong>{run.status === "failed" ? "失败" : "完成"}</strong><small>{formatTime(run.created_at)}</small></span><span className="mono">{Math.round(run.latency_ms)} ms</span></div>
            )) : <p className="quiet-copy">还没有运行记录。</p>}
          </section>
        </aside>
      </div>
    </main>
  );
}

function Metric({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return <div className={emphasis ? "metric metric-emphasis" : "metric"}><span>{label}</span><strong className="mono">{value}</strong></div>;
}

function StatePanel({ icon, title, detail, action, onAction }: { icon: React.ReactNode; title: string; detail: string; action?: string; onAction?: () => void }) {
  return <div className="state-panel">{icon}<strong>{title}</strong><p>{detail}</p>{action && <button className="secondary-button" type="button" onClick={onAction}>{action}</button>}</div>;
}

function QueueSkeleton() {
  return <div className="skeleton-list" aria-label="正在加载工单">{[0, 1, 2, 3].map((item) => <div className="skeleton-row" key={item}><span /><span /><span /></div>)}</div>;
}

function TraceEvent({ icon, title, meta, body, code = false, toolCalls }: { icon: React.ReactNode; title: string; meta?: string; body: string; code?: boolean; toolCalls?: Array<{ name: string; args: Record<string, unknown> }> }) {
  return (
    <article className="trace-event">
      <span className="trace-icon" aria-hidden="true">{icon}</span>
      <div className="trace-content"><header><strong>{title}</strong>{meta && <span>{meta}</span>}</header>{code ? <pre>{body}</pre> : <p>{body}</p>}{toolCalls?.map((tool, index) => <pre key={`${tool.name}-${index}`}>{tool.name}{"\n"}{JSON.stringify(tool.args, null, 2)}</pre>)}</div>
    </article>
  );
}
