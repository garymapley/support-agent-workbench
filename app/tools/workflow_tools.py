import json
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.workflow_repository import (
    create_refund_approval,
    create_support_ticket as create_ticket_record,
    escalate_ticket,
    get_approval,
    get_latest_approval_for_ticket,
)


@tool
def create_support_ticket(
    order_id: str,
    issue_type: Literal["refund", "warranty", "logistics", "quality", "other"],
    description: str,
    proposed_action: Literal[
        "diagnose", "replace", "repair", "refund", "logistics_check", "human_handoff"
    ],
    config: RunnableConfig,
) -> str:
    """创建售后工单，并依据订单金额、退款状态和建议动作计算风险等级。"""

    thread_id = str(config.get("configurable", {}).get("thread_id", ""))
    ticket = create_ticket_record(
        order_id,
        issue_type,
        description,
        proposed_action,
        thread_id=thread_id or None,
    )
    return json.dumps({"created": True, "ticket": ticket}, ensure_ascii=False)


@tool
def request_refund_approval(
    ticket_id: str,
    reason: str,
    config: RunnableConfig,
) -> str:
    """为退款工单创建人工审批；此工具不会执行退款。"""

    thread_id = str(config.get("configurable", {}).get("thread_id", ""))
    if not thread_id:
        raise ValueError("退款审批缺少 Agent thread_id")
    approval = create_refund_approval(ticket_id, reason, thread_id)
    return json.dumps(
        {
            "created": True,
            "approval": approval,
            "workflow_status": "waiting_for_approval",
            "message": "主 Agent 将暂停，等待人工审批。",
        },
        ensure_ascii=False,
    )


@tool
def get_approval_status(
    approval_id: str = "",
    ticket_id: str = "",
) -> str:
    """根据审批号或工单号查询人工退款审批的真实状态。"""

    approval = None
    if approval_id.strip():
        approval = get_approval(approval_id)
    elif ticket_id.strip():
        approval = get_latest_approval_for_ticket(ticket_id)
    else:
        return json.dumps(
            {"found": False, "message": "请提供 approval_id 或 ticket_id。"},
            ensure_ascii=False,
        )
    return json.dumps(
        {"found": approval is not None, "approval": approval},
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
    get_approval_status,
    escalate_to_human,
]
