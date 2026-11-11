"""验证主 Agent 图可以暂停并从同一 thread 恢复人工审批。"""

from uuid import uuid4

from langgraph.types import Command

from app.checkpointing import close_checkpointer
from app.graph import graph
from app.seed import prepare_database
from app.workflow_repository import (
    create_support_ticket,
    get_approval,
    get_ticket,
)


def main() -> None:
    prepare_database()
    public_thread_id = f"smoke-approval-{uuid4().hex}"
    stored_thread_id = f"agent:{public_thread_id}"
    config = {"configurable": {"thread_id": stored_thread_id}}

    ticket = create_support_ticket(
        order_id="A1003",
        issue_type="refund",
        description="主图人工审批冒烟测试。",
        proposed_action="refund",
        thread_id=stored_thread_id,
    )
    approval = ticket["approval"]
    paused = graph.invoke(
        {
            "messages": [],
            "pending_approval_id": approval["approval_id"],
            "resume_to_agent": False,
        },
        config=config,
    )
    if not paused.get("__interrupt__"):
        raise AssertionError("主 Agent 图没有暂停等待人工审批")

    resumed = graph.invoke(
        Command(
            resume={
                "decision": "approve",
                "reviewer": "demo_manager",
                "comment": "主图恢复测试通过；未执行真实退款。",
            }
        ),
        config=config,
    )
    final_approval = get_approval(approval["approval_id"])
    final_ticket = get_ticket(ticket["ticket_id"])
    if resumed.get("__interrupt__"):
        raise AssertionError("审批后主图仍处于暂停状态")
    if final_approval is None or final_approval["status"] != "approved":
        raise AssertionError("审批状态未更新为 approved")
    if final_ticket is None or final_ticket["status"] != "approved_pending_execution":
        raise AssertionError("工单状态未更新")

    print(f"THREAD_ID={public_thread_id}")
    print(f"TICKET_ID={ticket['ticket_id']}")
    print(f"APPROVAL_ID={approval['approval_id']}")
    print("MAIN_GRAPH_STATUS=RESUMED")
    print(f"APPROVAL_STATUS={final_approval['status']}")
    print(f"TICKET_STATUS={final_ticket['status']}")
    print("REFUND_EXECUTED=false")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_checkpointer()
