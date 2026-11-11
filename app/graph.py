from langchain_core.messages import SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

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
任何退款建议都必须将 proposed_action 设为 refund，并调用 request_refund_approval 创建人工审批。
退款审批只表示等待人工决定，绝不能声称退款已经执行。
信息冲突、政策无依据或无法可靠判断时，调用 escalate_to_human 转交人工。
请用简洁、专业的中文回答。
""".strip()

AGENT_TOOLS = [*ORDER_TOOLS, *POLICY_TOOLS, *WORKFLOW_TOOLS]


def answer_ticket(state: MessagesState) -> dict:
    """LangGraph 的第一个节点：调用千问回答用户。"""

    model = get_chat_model().bind_tools(AGENT_TOOLS)
    response = model.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    )
    return {"messages": [response]}


def build_graph():
    builder = StateGraph(MessagesState)
    builder.add_node("agent", answer_ticket)
    builder.add_node(
        "tools",
        ToolNode(
            AGENT_TOOLS,
            handle_tool_errors="工具执行失败，请检查输入或转交人工客服。",
        ),
    )
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=get_checkpointer())


graph = build_graph()

