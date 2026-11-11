from langchain_core.messages import SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.model import get_chat_model
from app.tools.order_tools import ORDER_TOOLS
from app.tools.policy_tools import POLICY_TOOLS


SYSTEM_PROMPT = """
你是一名企业售后工单助手。
当用户提供订单号，或问题的处理依赖订单状态时，必须调用 get_order 查询，不得猜测订单信息。
如果用户没有提供订单号，请先要求对方补充订单号。
当问题涉及退货、退款、换货、保修或物流处理规则时，必须调用 search_policy 检索政策，不得凭记忆编造。
给出政策性结论时，必须在回答中标注检索结果里的 source 和 version。
未满足政策条件或需要审批时，不得直接承诺退款。
请用简洁、专业的中文回答。
""".strip()

AGENT_TOOLS = [*ORDER_TOOLS, *POLICY_TOOLS]


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
            handle_tool_errors="订单查询失败，请核对订单号或转交人工客服。",
        ),
    )
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    return builder.compile()


graph = build_graph()

