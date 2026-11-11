"""验证退款审批可以暂停、由人工决定并从检查点恢复。"""

import json

from app.approval_workflow import (
    close_approval_workflow,
    resume_approval_workflow,
    start_approval_workflow,
)
from app.seed import prepare_database
from app.tools.workflow_tools import request_refund_approval
from app.workflow_repository import (
    create_support_ticket,
    get_approval,
    get_ticket,
)


def main() -> None:
    prepare_database()
    ticket = create_support_ticket(
        order_id="A1003",
        issue_type="refund",
        description="客户申请对高金额订单退款，用于审批工作流冒烟测试。",
        proposed_action="refund",
    )
    tool_args = {
        "ticket_id": ticket["ticket_id"],
        "reason": "订单金额较高且已处于人工退款审批状态。",
    }
    first_request = json.loads(request_refund_approval.invoke(tool_args))
    second_request = json.loads(request_refund_approval.invoke(tool_args))
    approval = first_request["approval"]
    if first_request["workflow_status"] != "paused_for_human":
        raise AssertionError("审批工具没有自动启动人工审批工作流")
    if second_request["approval"]["approval_id"] != approval["approval_id"]:
        raise AssertionError("重复调用为同一工单创建了第二条待审批记录")

    paused = start_approval_workflow(
        approval["approval_id"]
    )
    interrupts = paused.get("__interrupt__", ())
    if not interrupts:
        raise AssertionError("审批工作流没有在人工审核节点暂停")

    print(f"TICKET_ID={ticket['ticket_id']}")
    print(f"RISK_LEVEL={ticket['risk_level']}")
    print(f"APPROVAL_ID={approval['approval_id']}")
    print("WORKFLOW_STATUS=PAUSED_FOR_HUMAN")

    resumed = resume_approval_workflow(
        approval["approval_id"],
        decision="approve",
        reviewer="demo_manager",
        comment="演示审批通过；尚未执行真实退款。",
    )
    final_approval = get_approval(approval["approval_id"])
    final_ticket = get_ticket(ticket["ticket_id"])

    if resumed.get("decision") != "approve":
        raise AssertionError("工作流恢复后没有记录审批决定")
    if final_approval is None or final_approval["status"] != "approved":
        raise AssertionError("审批状态未更新为 approved")
    if final_ticket is None or final_ticket["status"] != "approved_pending_execution":
        raise AssertionError("工单状态未更新为 approved_pending_execution")

    print(f"APPROVAL_STATUS={final_approval['status']}")
    print(f"REVIEWER={final_approval['reviewer']}")
    print(f"TICKET_STATUS={final_ticket['status']}")
    print("REFUND_EXECUTED=false")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_approval_workflow()
