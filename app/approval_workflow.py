from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.workflow_repository import apply_approval_decision, get_approval


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1)
    comment: str = ""


def build_approval_interrupt(approval_id: str) -> dict[str, Any]:
    approval = get_approval(approval_id)
    if approval is None:
        raise ValueError(f"审批 {approval_id} 不存在")
    return {
        "type": "refund_approval",
        "message": "请人工审核退款申请",
        "approval": approval,
    }


def record_approval_decision(
    approval_id: str,
    response: Any,
) -> dict[str, Any]:
    decision = ApprovalDecision.model_validate(response)
    return apply_approval_decision(
        approval_id,
        decision.decision,
        decision.reviewer,
        decision.comment,
    )
