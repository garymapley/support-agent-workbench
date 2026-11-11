"""真实验证模型、工具、主图 interrupt 与人工恢复的完整链路。"""

from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from app.checkpointing import close_checkpointer
from app.graph import graph
from app.qdrant_store import close_qdrant_client
from app.seed import prepare_database
from app.workflow_repository import get_approval


def main() -> None:
    prepare_database()
    public_thread_id = f"smoke-main-{uuid4().hex}"
    stored_thread_id = f"agent:{public_thread_id}"
    config = {
        "recursion_limit": 12,
        "configurable": {"thread_id": stored_thread_id},
    }
    paused = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "订单 A1003 的商品存在质量问题，我确认要申请退款。"
                        "请查询订单和政策，创建退款工单并提交人工审批。"
                    )
                )
            ]
        },
        config=config,
    )
    interrupts = paused.get("__interrupt__", ())
    if not interrupts:
        raise AssertionError("真实 Agent 没有在主图暂停等待审批")
    approval = interrupts[0].value["approval"]
    if approval["thread_id"] != stored_thread_id:
        raise AssertionError("审批没有关联原 Agent thread_id")

    called_tools = [
        call["name"]
        for message in paused["messages"]
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]
    resumed = graph.invoke(
        Command(
            resume={
                "decision": "reject",
                "reviewer": "smoke_manager",
                "comment": "演示拒绝：需要补充商品故障视频。",
            }
        ),
        config=config,
    )
    final_approval = get_approval(approval["approval_id"])
    if final_approval is None or final_approval["status"] != "rejected":
        raise AssertionError("审批拒绝结果没有保存")
    if resumed.get("__interrupt__"):
        raise AssertionError("恢复后仍停在 interrupt")

    print(f"THREAD_ID={public_thread_id}")
    print(f"CALLED_TOOLS={called_tools}")
    print(f"APPROVAL_ID={approval['approval_id']}")
    print("PAUSED_IN_MAIN_GRAPH=true")
    print(f"APPROVAL_STATUS={final_approval['status']}")
    print("FINAL_ANSWER_START")
    print(resumed["messages"][-1].content)
    print("FINAL_ANSWER_END")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_qdrant_client()
        close_checkpointer()
