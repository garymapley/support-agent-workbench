import json
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage

from app.config import get_settings
from app.run_repository import save_run


SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
logger = logging.getLogger("support_agent")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for key in ("run_id", "thread_id", "status", "latency_ms", "error_type"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    if logger.handlers:
        return
    settings = get_settings()
    log_path = Path(settings.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False


def sanitize_text(value: str, limit: int = 4000) -> str:
    return SECRET_PATTERN.sub("sk-<redacted>", value)[:limit]


def message_metrics(messages: list[Any]) -> dict[str, Any]:
    tools: list[str] = []
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        tools.extend(call["name"] for call in message.tool_calls)
        usage = message.usage_metadata or {}
        input_tokens += int(usage.get("input_tokens", 0) or 0)
        output_tokens += int(usage.get("output_tokens", 0) or 0)
        total_tokens += int(usage.get("total_tokens", 0) or 0)
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    return {
        "tools": tools,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def estimate_cost_cny(input_tokens: int, output_tokens: int) -> float | None:
    settings = get_settings()
    if (
        settings.chat_input_cost_per_million_cny <= 0
        and settings.chat_output_cost_per_million_cny <= 0
    ):
        return None
    return round(
        input_tokens / 1_000_000 * settings.chat_input_cost_per_million_cny
        + output_tokens / 1_000_000 * settings.chat_output_cost_per_million_cny,
        6,
    )


def record_run(
    *,
    thread_id: str,
    run_type: str,
    status: str,
    user_input: str,
    answer: str,
    messages: list[Any],
    latency_ms: float,
    error_type: str | None = None,
) -> str:
    run_id = uuid4().hex
    metrics = message_metrics(messages)
    run_scope = "evaluation" if thread_id.startswith("agent:eval-") else "runtime"
    cost = estimate_cost_cny(
        metrics["input_tokens"], metrics["output_tokens"]
    )
    save_run(
        {
            "run_id": run_id,
            "thread_id": thread_id,
            "run_type": run_type,
            "run_scope": run_scope,
            "status": status,
            "user_input": sanitize_text(user_input),
            "answer": sanitize_text(answer),
            "tools_json": json.dumps(metrics["tools"], ensure_ascii=False),
            "input_tokens": metrics["input_tokens"],
            "output_tokens": metrics["output_tokens"],
            "total_tokens": metrics["total_tokens"],
            "latency_ms": latency_ms,
            "estimated_cost_cny": cost,
            "error_type": error_type,
        }
    )
    logger.info(
        "agent_run",
        extra={
            "run_id": run_id,
            "thread_id": thread_id,
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "error_type": error_type,
        },
    )
    return run_id
