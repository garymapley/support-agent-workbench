import json

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt

from app.approval_workflow import (
    build_approval_interrupt,
    record_approval_decision,
)
from app.checkpointing import get_checkpointer
from app.model import get_chat_model
from app.tools.order_tools import ORDER_TOOLS
from app.tools.policy_tools import POLICY_TOOLS
from app.tools.workflow_tools import WORKFLOW_TOOLS


SYSTEM_PROMPT = """
你是一名企业售后工单助手。
当用户提供订单号，或问题的处理依赖订单状态时，必须调用 get_order 查询，不得猜测订单信息。
如果用户没有提供订单号，请先要求对方补充订单号。
当问题涉及退货、退款、换货、保修或物流处理规则时，必须调用 search_policy 检索政策，不得凭记忆编造。
给出政策性结论时，必须在回答中标注检索结果里的 source 和 version。
未满足政策条件或需要审批时，不得直接承诺退款。
当用户诉求需要实际跟进时，先查询订单和政策，再调用 create_support_ticket 创建工单。
创建退款工单时必须将 proposed_action 设为 refund；系统会自动创建人工审批并暂停对话。
对已有退款工单，可以调用 request_refund_approval 发起审批。
用户询问审批进度时，必须调用 get_approval_status 查询，不得猜测。
退款审批只表示等待人工决定，绝不能声称退款已经执行。
信息冲突、政策无依据或无法可靠判断时，调用 escalate_to_human 转交人工。
请用简洁、专业的中文回答。
""".strip()

AGENT_TOOLS = [*ORDER_TOOLS, *POLICY_TOOLS, *WORKFLOW_TOOLS]


class SupportState(MessagesState, total=False):
    pending_approval_id: str | None
    approval_status: str | None
    resume_to_agent: bool


def answer_ticket(state: SupportState) -> dict:
    """LangGraph 的第一个节点：调用千问回答用户。"""

    model = get_chat_model().bind_tools(AGENT_TOOLS)
    response = model.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    )
    return {"messages": [response]}


def _current_approval_id(state: SupportState) -> str | None:
    if state.get("pending_approval_id"):
        return state["pending_approval_id"]

    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break
        try:
            payload = json.loads(str(message.content))
        except (TypeError, json.JSONDecodeError):
            continue
        approval = payload.get("approval")
        if approval is None:
            approval = payload.get("ticket", {}).get("approval")
        if approval and approval.get("status") == "pending":
            return str(approval["approval_id"])
    return None


def route_from_start(state: SupportState) -> str:
    return "await_approval" if state.get("pending_approval_id") else "agent"


def route_after_tools(state: SupportState) -> str:
    return "await_approval" if _current_approval_id(state) else "agent"


def await_approval(state: SupportState) -> dict:
    approval_id = _current_approval_id(state)
    if not approval_id:
        raise ValueError("主图进入审批节点，但没有找到 approval_id")

    decision = interrupt(build_approval_interrupt(approval_id))
    approval = record_approval_decision(approval_id, decision)
    status_text = "已通过" if approval["status"] == "approved" else "已拒绝"
    return {
        "pending_approval_id": None,
        "approval_status": approval["status"],
        "messages": [
            SystemMessage(
                content=(
                    f"人工审批 {approval_id} {status_text}；"
                    f"审核人：{approval['reviewer']}。"
                    "退款仍未自动执行，请根据审批结果向用户说明下一步。"
                )
            )
        ],
    }


def route_after_approval(state: SupportState) -> str:
    return "agent" if state.get("resume_to_agent", True) else END


def build_graph():
    builder = StateGraph(SupportState)
    builder.add_node("agent", answer_ticket)
    builder.add_node("await_approval", await_approval)
    builder.add_node(
        "tools",
        ToolNode(
            AGENT_TOOLS,
            handle_tool_errors="工具执行失败，请检查输入或转交人工客服。",
        ),
    )
    builder.add_conditional_edges(
        START,
        route_from_start,
        {"agent": "agent", "await_approval": "await_approval"},
    )
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_conditional_edges(
        "tools",
        route_after_tools,
        {"agent": "agent", "await_approval": "await_approval"},
    )
    builder.add_conditional_edges(
        "await_approval",
        route_after_approval,
        {"agent": "agent", END: END},
    )
    return builder.compile(checkpointer=get_checkpointer())


graph = build_graph()

