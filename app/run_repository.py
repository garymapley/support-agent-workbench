import json
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select

from app.database import session_scope
from app.db_models import AgentRunRecord


def save_run(data: dict[str, Any]) -> None:
    with session_scope() as session:
        session.add(AgentRunRecord(**data))


def _run_to_dict(run: AgentRunRecord) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "thread_id": run.thread_id,
        "run_type": run.run_type,
        "status": run.status,
        "user_input": run.user_input,
        "answer": run.answer,
        "tools": json.loads(run.tools_json),
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "total_tokens": run.total_tokens,
        "latency_ms": round(run.latency_ms, 2),
        "estimated_cost_cny": run.estimated_cost_cny,
        "error_type": run.error_type,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    with session_scope() as session:
        runs = session.scalars(
            select(AgentRunRecord)
            .order_by(desc(AgentRunRecord.created_at), desc(AgentRunRecord.id))
            .limit(limit)
        )
        return [_run_to_dict(run) for run in runs]


def get_run(run_id: str) -> dict[str, Any] | None:
    with session_scope() as session:
        run = session.scalar(
            select(AgentRunRecord).where(AgentRunRecord.run_id == run_id)
        )
        return _run_to_dict(run) if run else None


def summarize_runs() -> dict[str, Any]:
    with session_scope() as session:
        runs = list(session.scalars(select(AgentRunRecord)))
    if not runs:
        return {
            "run_count": 0,
            "success_rate": 0.0,
            "average_latency_ms": 0.0,
            "total_tokens": 0,
            "estimated_cost_cny": None,
            "tool_usage": {},
        }

    successful = sum(run.status != "failed" for run in runs)
    tool_usage: dict[str, int] = {}
    for run in runs:
        for tool_name in json.loads(run.tools_json):
            tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
    priced_costs = [
        run.estimated_cost_cny
        for run in runs
        if run.estimated_cost_cny is not None
    ]
    return {
        "run_count": len(runs),
        "success_rate": round(successful / len(runs), 4),
        "average_latency_ms": round(
            sum(run.latency_ms for run in runs) / len(runs), 2
        ),
        "total_tokens": sum(run.total_tokens for run in runs),
        "estimated_cost_cny": (
            round(sum(priced_costs), 6) if priced_costs else None
        ),
        "tool_usage": dict(sorted(tool_usage.items())),
    }
