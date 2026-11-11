import json
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, status
from langchain_core.messages import AIMessage, ToolMessage

from app.api_schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ApprovalDecisionRequest,
    RefundApprovalRequest,
    TicketCreateRequest,
)
from app.approval_workflow import (
    request_refund_approval_workflow,
    resume_approval_workflow,
    start_approval_workflow,
)
from app.checkpointing import close_checkpointer
from app.graph import graph
from app.order_repository import find_order_by_id, list_orders
from app.qdrant_store import close_qdrant_client
from app.seed import prepare_database
from app.workflow_repository import (
    create_support_ticket,
    get_approval,
    get_ticket,
    list_approvals,
    list_tickets,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    prepare_database()
    yield
    close_qdrant_client()
    close_checkpointer()


app = FastAPI(
    title="企业售后工单 Agent API",
    version="0.7.0",
    description="订单查询、售后 Agent、工单与人工退款审批接口。",
    lifespan=lifespan,
)


def _agent_config(thread_id: str) -> dict[str, Any]:
    return {
        "recursion_limit": 12,
        "configurable": {"thread_id": f"agent:{thread_id}"},
    }


def _message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/agent/runs",
    response_model=AgentRunResponse,
    tags=["agent"],
)
def run_agent(payload: AgentRunRequest) -> AgentRunResponse:
    from langchain_core.messages import HumanMessage

    thread_id = payload.thread_id or uuid4().hex
    try:
        result = graph.invoke(
            {"messages": [HumanMessage(content=payload.message)]},
            config=_agent_config(thread_id),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent 运行失败，请稍后重试或转交人工。",
        ) from exc

    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    for message in result["messages"]:
        if isinstance(message, AIMessage):
            tool_calls.extend(
                {
                    "id": item.get("id"),
                    "name": item["name"],
                    "args": item["args"],
                }
                for item in message.tool_calls
            )
        elif isinstance(message, ToolMessage):
            tool_results.append(
                {
                    "tool_call_id": message.tool_call_id,
                    "name": message.name,
                    "content": _message_content(message.content),
                }
            )

    return AgentRunResponse(
        thread_id=thread_id,
        answer=_message_content(result["messages"][-1].content),
        tool_calls=tool_calls,
        tool_results=tool_results,
    )


@app.get("/agent/threads/{thread_id}/history", tags=["agent"])
def get_agent_history(thread_id: str) -> dict[str, Any]:
    snapshot = graph.get_state(_agent_config(thread_id))
    history = []
    for message in snapshot.values.get("messages", []):
        item: dict[str, Any] = {
            "id": message.id,
            "type": message.type,
            "content": message.content,
        }
        if isinstance(message, AIMessage):
            item["tool_calls"] = message.tool_calls
        elif isinstance(message, ToolMessage):
            item["tool_call_id"] = message.tool_call_id
            item["name"] = message.name
        history.append(item)
    return {"thread_id": thread_id, "messages": history}


@app.get("/orders", tags=["orders"])
def get_orders(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    return list_orders(limit)


@app.get("/orders/{order_id}", tags=["orders"])
def get_order(order_id: str) -> dict[str, Any]:
    order = find_order_by_id(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@app.post("/tickets", status_code=201, tags=["tickets"])
def create_ticket(payload: TicketCreateRequest) -> dict[str, Any]:
    try:
        return create_support_ticket(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/tickets", tags=["tickets"])
def get_tickets(
    limit: int = Query(50, ge=1, le=200),
    ticket_status: str | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    return list_tickets(limit, ticket_status)


@app.get("/tickets/{ticket_id}", tags=["tickets"])
def get_ticket_by_id(ticket_id: str) -> dict[str, Any]:
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    return ticket


@app.post(
    "/tickets/{ticket_id}/refund-approval",
    status_code=201,
    tags=["approvals"],
)
def request_refund_approval(
    ticket_id: str,
    payload: RefundApprovalRequest,
) -> dict[str, Any]:
    try:
        return request_refund_approval_workflow(ticket_id, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/approvals", tags=["approvals"])
def get_approvals(
    limit: int = Query(50, ge=1, le=200),
    approval_status: str | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    return list_approvals(limit, approval_status)


@app.get("/approvals/{approval_id}", tags=["approvals"])
def get_approval_by_id(approval_id: str) -> dict[str, Any]:
    approval = get_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="审批不存在")
    return approval


@app.post("/approvals/{approval_id}/decision", tags=["approvals"])
def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
) -> dict[str, Any]:
    approval = get_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="审批不存在")
    if approval["status"] != "pending":
        raise HTTPException(status_code=409, detail="审批已经处理")

    try:
        start_approval_workflow(approval_id)
        resume_approval_workflow(
            approval_id,
            payload.decision,
            payload.reviewer,
            payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated = get_approval(approval_id)
    ticket = get_ticket(approval["ticket_id"])
    return {"approval": updated, "ticket": ticket}
