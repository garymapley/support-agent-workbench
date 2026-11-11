from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, ConfigDict, Field

from app.checkpointing import close_checkpointer, get_checkpointer
from app.workflow_repository import apply_approval_decision, get_approval


class ApprovalState(TypedDict, total=False):
    approval_id: str
    decision: str
    reviewer: str
    comment: str


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1)
    comment: str = ""


def human_review(state: ApprovalState) -> ApprovalState:
    approval = get_approval(state["approval_id"])
    if approval is None:
        raise ValueError(f"审批 {state['approval_id']} 不存在")

    response = interrupt(
        {
            "type": "refund_approval",
            "message": "请人工审核退款申请",
            "approval": approval,
        }
    )
    decision = ApprovalDecision.model_validate(response)
    apply_approval_decision(
        state["approval_id"],
        decision.decision,
        decision.reviewer,
        decision.comment,
    )
    return {
        "decision": decision.decision,
        "reviewer": decision.reviewer,
        "comment": decision.comment,
    }


_builder = StateGraph(ApprovalState)
_builder.add_node("human_review", human_review)
_builder.add_edge(START, "human_review")
_builder.add_edge("human_review", END)
approval_graph = _builder.compile(checkpointer=get_checkpointer())


def approval_config(approval_id: str) -> dict:
    return {"configurable": {"thread_id": f"approval:{approval_id}"}}


def start_approval_workflow(approval_id: str) -> dict:
    approval = get_approval(approval_id)
    if approval is None:
        raise ValueError(f"审批 {approval_id} 不存在")
    if approval["status"] != "pending":
        raise ValueError(f"审批 {approval_id} 已处理，不能再次发起")
    normalized_id = approval_id.strip().upper()
    config = approval_config(normalized_id)
    snapshot = approval_graph.get_state(config)
    existing_interrupts = tuple(
        interrupt_item
        for task in snapshot.tasks
        for interrupt_item in task.interrupts
    )
    if existing_interrupts:
        return {**snapshot.values, "__interrupt__": existing_interrupts}

    return approval_graph.invoke(
        {"approval_id": normalized_id},
        config=config,
    )


def resume_approval_workflow(
    approval_id: str,
    decision: Literal["approve", "reject"],
    reviewer: str,
    comment: str = "",
) -> dict:
    return approval_graph.invoke(
        Command(
            resume={
                "decision": decision,
                "reviewer": reviewer,
                "comment": comment,
            }
        ),
        config=approval_config(approval_id.strip().upper()),
    )


def close_approval_workflow() -> None:
    close_checkpointer()
