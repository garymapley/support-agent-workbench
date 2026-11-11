import json
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, status
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from app.api_schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ApprovalDecisionRequest,
    RefundApprovalRequest,
    TicketCreateRequest,
)
from app.checkpointing import close_checkpointer
from app.execution_guard import ThreadBusyError, guard_thread
from app.graph import graph
from app.order_repository import find_order_by_id, list_orders
from app.qdrant_store import close_qdrant_client
from app.seed import prepare_database
from app.workflow_repository import (
    create_support_ticket,
    create_refund_approval,
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


def _stored_thread_config(stored_thread_id: str) -> dict[str, Any]:
    return {
        "recursion_limit": 12,
        "configurable": {"thread_id": stored_thread_id},
    }


def _public_thread_id(stored_thread_id: str) -> str:
    return stored_thread_id.removeprefix("agent:")


def _message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _format_agent_result(
    result: dict[str, Any],
    thread_id: str,
) -> AgentRunResponse:
    interrupts = result.get("__interrupt__", ())
    interrupt_payload = interrupts[0].value if interrupts else None
    approval = (
        interrupt_payload.get("approval") if interrupt_payload else None
    )
    waiting = bool(interrupts)

    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    for message in result.get("messages", []):
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

    if waiting:
        answer = "退款申请正在等待人工审批。"
    elif result.get("messages"):
        answer = _message_content(result["messages"][-1].content)
    else:
        answer = "处理完成。"
    return AgentRunResponse(
        thread_id=thread_id,
        status="waiting_for_approval" if waiting else "completed",
        waiting_for_approval=waiting,
        approval_id=approval.get("approval_id") if approval else None,
        interrupt=interrupt_payload,
        answer=answer,
        tool_calls=tool_calls,
        tool_results=tool_results,
    )


def _snapshot_result(snapshot) -> dict[str, Any]:
    interrupts = tuple(
        item
        for task in snapshot.tasks
        for item in task.interrupts
    )
    return {**snapshot.values, "__interrupt__": interrupts}


def _ensure_approval_waiting(approval: dict[str, Any]) -> dict[str, Any]:
    stored_thread_id = approval.get("thread_id")
    if not stored_thread_id:
        raise ValueError("审批没有关联 Agent thread_id")
    config = _stored_thread_config(stored_thread_id)
    with guard_thread(stored_thread_id):
        snapshot = graph.get_state(config)
        current = _snapshot_result(snapshot)
        if current["__interrupt__"]:
            return current
        return graph.invoke(
            {
                "messages": [],
                "pending_approval_id": approval["approval_id"],
                "resume_to_agent": False,
            },
            config=config,
        )


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
        stored_thread_id = f"agent:{thread_id}"
        with guard_thread(stored_thread_id):
            config = _agent_config(thread_id)
            snapshot = graph.get_state(config)
            current = _snapshot_result(snapshot)
            if current["__interrupt__"]:
                result = current
            else:
                result = graph.invoke(
                    {"messages": [HumanMessage(content=payload.message)]},
                    config=config,
                )
    except ThreadBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该对话正在处理另一条请求，请稍后重试。",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent 运行失败，请稍后重试或转交人工。",
        ) from exc

    return _format_agent_result(result, thread_id)


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
        data = payload.model_dump()
        public_thread_id = data.pop("thread_id") or uuid4().hex
        stored_thread_id = f"agent:{public_thread_id}"
        ticket = create_support_ticket(
            **data,
            thread_id=(
                stored_thread_id
                if data["proposed_action"] == "refund"
                else None
            ),
        )
        approval = ticket.get("approval")
        if approval:
            result = _ensure_approval_waiting(approval)
            ticket["agent_run"] = _format_agent_result(
                result, public_thread_id
            ).model_dump()
        return ticket
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ThreadBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
        public_thread_id = payload.thread_id or uuid4().hex
        approval = create_refund_approval(
            ticket_id,
            payload.reason,
            f"agent:{public_thread_id}",
        )
        result = _ensure_approval_waiting(approval)
        return {
            "approval": approval,
            "agent_run": _format_agent_result(
                result, public_thread_id
            ).model_dump(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ThreadBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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

    stored_thread_id = approval.get("thread_id")
    if not stored_thread_id:
        raise HTTPException(
            status_code=409,
            detail="旧审批没有关联 Agent 对话，无法恢复。",
        )
    try:
        with guard_thread(stored_thread_id):
            snapshot = graph.get_state(
                _stored_thread_config(stored_thread_id)
            )
            current = _snapshot_result(snapshot)
            if not current["__interrupt__"]:
                raise HTTPException(
                    status_code=409,
                    detail="原 Agent 对话当前没有等待中的审批节点。",
                )
            result = graph.invoke(
                Command(resume=payload.model_dump()),
                config=_stored_thread_config(stored_thread_id),
            )
    except ThreadBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated = get_approval(approval_id)
    ticket = get_ticket(approval["ticket_id"])
    return {
        "approval": updated,
        "ticket": ticket,
        "agent_run": _format_agent_result(
            result,
            _public_thread_id(stored_thread_id),
        ).model_dump(),
    }
