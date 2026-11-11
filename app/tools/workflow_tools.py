import json
from typing import Literal

from langchain_core.tools import tool

from app.approval_workflow import request_refund_approval_workflow
from app.workflow_repository import (
    create_support_ticket as create_ticket_record,
    escalate_ticket,
)


@tool
def create_support_ticket(
    order_id: str,
    issue_type: Literal["refund", "warranty", "logistics", "quality", "other"],
    description: str,
    proposed_action: Literal[
        "diagnose", "replace", "repair", "refund", "logistics_check", "human_handoff"
    ],
) -> str:
    """创建售后工单，并依据订单金额、退款状态和建议动作计算风险等级。"""

    ticket = create_ticket_record(
        order_id, issue_type, description, proposed_action
    )
    return json.dumps({"created": True, "ticket": ticket}, ensure_ascii=False)


@tool
def request_refund_approval(ticket_id: str, reason: str) -> str:
    """为退款工单创建人工审批；此工具不会执行退款。"""

    result = request_refund_approval_workflow(ticket_id, reason)
    return json.dumps(
        {
            "created": True,
            **result,
            "message": "退款尚未执行，必须由人工审批并恢复工作流。",
        },
        ensure_ascii=False,
    )


@tool
def escalate_to_human(ticket_id: str, reason: str) -> str:
    """将低置信度、冲突或异常工单转交人工客服。"""

    ticket = escalate_ticket(ticket_id, reason)
    return json.dumps({"escalated": True, "ticket": ticket}, ensure_ascii=False)


WORKFLOW_TOOLS = [
    create_support_ticket,
    request_refund_approval,
    escalate_to_human,
]
