import json
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from app.api_schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ApprovalDecisionRequest,
    HandoffRequest,
    RefundApprovalRequest,
    TicketCreateRequest,
)
from app.checkpointing import close_checkpointer
from app.config import get_settings
from app.execution_guard import ThreadBusyError, guard_thread
from app.graph import graph
from app.order_repository import find_order_by_id, list_orders
from app.qdrant_store import close_qdrant_client
from app.run_repository import list_runs, summarize_runs
from app.security import require_operator, require_reviewer
from app.seed import prepare_database
from app.telemetry import configure_logging, logger, record_run
from app.workflow_repository import (
    PendingApprovalError,
    create_support_ticket,
    create_refund_approval,
    get_approval,
    get_ticket,
    list_approvals,
    list_tickets,
    escalate_ticket,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    prepare_database()
    configure_logging()
    yield
    close_qdrant_client()
    close_checkpointer()


app = FastAPI(
    title="企业售后工单 Agent API",
    version="1.0.0",
    description="订单查询、售后 Agent、工单与人工退款审批接口。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID", "X-Admin-Token"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "http_request_failed",
            extra={
                "run_id": request_id,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http_request",
        extra={
            "run_id": request_id,
            "status": str(response.status_code),
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        },
    )
    return response


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
    dependencies=[Depends(require_operator)],
)
def run_agent(payload: AgentRunRequest) -> AgentRunResponse:
    from langchain_core.messages import HumanMessage

    thread_id = payload.thread_id or uuid4().hex
    started = perf_counter()
    starting_message_count = 0
    try:
        stored_thread_id = f"agent:{thread_id}"
        with guard_thread(stored_thread_id):
            config = _agent_config(thread_id)
            snapshot = graph.get_state(config)
            starting_message_count = len(
                snapshot.values.get("messages", [])
            )
            current = _snapshot_result(snapshot)
            if current["__interrupt__"]:
                result = current
            else:
                result = graph.invoke(
                    {
                        "messages": [HumanMessage(content=payload.message)],
                        "resume_to_agent": True,
                        "approval_notice": None,
                    },
                    config=config,
                )
    except ThreadBusyError as exc:
        record_run(
            thread_id=stored_thread_id,
            run_type="agent_message",
            status="failed",
            user_input=payload.message,
            answer="该对话正在处理另一条请求。",
            messages=[],
            latency_ms=(perf_counter() - started) * 1000,
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该对话正在处理另一条请求，请稍后重试。",
        ) from exc
    except Exception as exc:
        record_run(
            thread_id=f"agent:{thread_id}",
            run_type="agent_message",
            status="failed",
            user_input=payload.message,
            answer="Agent 运行失败。",
            messages=[],
            latency_ms=(perf_counter() - started) * 1000,
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent 运行失败，请稍后重试或转交人工。",
        ) from exc

    response = _format_agent_result(result, thread_id)
    new_messages = result.get("messages", [])[starting_message_count:]
    response.run_id = record_run(
        thread_id=f"agent:{thread_id}",
        run_type="agent_message",
        status=response.status,
        user_input=payload.message,
        answer=response.answer,
        messages=new_messages,
        latency_ms=(perf_counter() - started) * 1000,
    )
    return response


@app.get(
    "/agent/threads/{thread_id}/history",
    tags=["agent"],
    dependencies=[Depends(require_operator)],
)
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


@app.get("/orders", tags=["orders"], dependencies=[Depends(require_operator)])
def get_orders(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    return list_orders(limit)


@app.get("/orders/{order_id}", tags=["orders"], dependencies=[Depends(require_operator)])
def get_order(order_id: str) -> dict[str, Any]:
    order = find_order_by_id(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@app.post(
    "/tickets",
    status_code=201,
    tags=["tickets"],
    dependencies=[Depends(require_operator)],
)
def create_ticket(payload: TicketCreateRequest) -> dict[str, Any]:
    try:
        data = payload.model_dump()
        public_thread_id = data.pop("thread_id") or uuid4().hex
        stored_thread_id = f"agent:{public_thread_id}"
        ticket = create_support_ticket(
            **data,
            thread_id=stored_thread_id,
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


@app.get("/tickets", tags=["tickets"], dependencies=[Depends(require_operator)])
def get_tickets(
    limit: int = Query(50, ge=1, le=200),
    ticket_status: str | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    return list_tickets(limit, ticket_status)


@app.get("/tickets/{ticket_id}", tags=["tickets"], dependencies=[Depends(require_operator)])
def get_ticket_by_id(ticket_id: str) -> dict[str, Any]:
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    return ticket


@app.post(
    "/tickets/{ticket_id}/handoff",
    tags=["tickets"],
    dependencies=[Depends(require_operator)],
)
def handoff_ticket(
    ticket_id: str,
    payload: HandoffRequest,
) -> dict[str, Any]:
    try:
        return escalate_ticket(ticket_id, payload.reason)
    except PendingApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        code = 404 if "不存在" in detail else 400
        raise HTTPException(status_code=code, detail=detail) from exc


@app.post(
    "/tickets/{ticket_id}/refund-approval",
    status_code=201,
    tags=["approvals"],
    dependencies=[Depends(require_operator)],
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


@app.get("/approvals", tags=["approvals"], dependencies=[Depends(require_operator)])
def get_approvals(
    limit: int = Query(50, ge=1, le=200),
    approval_status: str | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    return list_approvals(limit, approval_status)


@app.get("/observability/runs", tags=["observability"], dependencies=[Depends(require_operator)])
def get_run_records(
    limit: int = Query(50, ge=1, le=200),
    scope: str = Query("runtime", pattern="^(runtime|evaluation|test)$"),
) -> list[dict[str, Any]]:
    return list_runs(limit, scope)


@app.get("/observability/summary", tags=["observability"], dependencies=[Depends(require_operator)])
def get_run_summary(
    scope: str = Query("runtime", pattern="^(runtime|evaluation|test)$"),
) -> dict[str, Any]:
    return summarize_runs(scope)


@app.get("/approvals/{approval_id}", tags=["approvals"], dependencies=[Depends(require_operator)])
def get_approval_by_id(approval_id: str) -> dict[str, Any]:
    approval = get_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="审批不存在")
    return approval


@app.post(
    "/approvals/{approval_id}/decision",
    tags=["approvals"],
    dependencies=[Depends(require_reviewer)],
)
def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
) -> dict[str, Any]:
    admin_reviewer = get_settings().admin_reviewer
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
    started = perf_counter()
    starting_message_count = 0
    try:
        with guard_thread(stored_thread_id):
            snapshot = graph.get_state(
                _stored_thread_config(stored_thread_id)
            )
            current = _snapshot_result(snapshot)
            starting_message_count = len(
                snapshot.values.get("messages", [])
            )
            if not current["__interrupt__"]:
                raise HTTPException(
                    status_code=409,
                    detail="原 Agent 对话当前没有等待中的审批节点。",
                )
            result = graph.invoke(
                Command(
                    resume={
                        **payload.model_dump(),
                        "reviewer": admin_reviewer,
                    }
                ),
                config=_stored_thread_config(stored_thread_id),
            )
    except ThreadBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated = get_approval(approval_id)
    ticket = get_ticket(approval["ticket_id"])
    agent_response = _format_agent_result(
        result,
        _public_thread_id(stored_thread_id),
    )
    agent_response.run_id = record_run(
        thread_id=stored_thread_id,
        run_type="approval_resume",
        status=agent_response.status,
        user_input=f"{approval_id}:{payload.decision}",
        answer=agent_response.answer,
        messages=result.get("messages", [])[starting_message_count:],
        latency_ms=(perf_counter() - started) * 1000,
    )
    return {
        "approval": updated,
        "ticket": ticket,
        "agent_run": agent_response.model_dump(),
    }
