from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class AgentRunRequest(ApiModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class AgentRunResponse(ApiModel):
    thread_id: str
    answer: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]


class TicketCreateRequest(ApiModel):
    order_id: str = Field(min_length=1, max_length=32)
    issue_type: Literal[
        "refund", "warranty", "logistics", "quality", "other"
    ]
    description: str = Field(min_length=1, max_length=4000)
    proposed_action: Literal[
        "diagnose",
        "replace",
        "repair",
        "refund",
        "logistics_check",
        "human_handoff",
    ]


class RefundApprovalRequest(ApiModel):
    reason: str = Field(min_length=1, max_length=2000)


class ApprovalDecisionRequest(ApiModel):
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str = Field(default="", max_length=2000)
