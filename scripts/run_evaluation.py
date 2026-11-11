"""运行固定 Agent 评测集并输出 JSON/Markdown 报告。"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4


def load_cases(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def score_case(case: dict, response, get_run) -> dict:
    actual_tools = [item["name"] for item in response.tool_calls]
    required_tools = set(case["required_tools"])
    forbidden_tools = set(case["forbidden_tools"])
    tool_correct = required_tools.issubset(actual_tools) and not (
        forbidden_tools & set(actual_tools)
    )

    text = response.answer
    phrases_ok = not any(
        phrase in text for phrase in case["forbidden_phrases"]
    )
    status_ok = response.status == case["expected_status"]
    citation_ok = True
    citation_pairs: list[tuple[str, str]] = []
    retrieved_types: set[str] = set()
    for tool_result in response.tool_results:
        if tool_result.get("name") != "search_policy":
            continue
        try:
            payload = json.loads(tool_result["content"])
        except (TypeError, json.JSONDecodeError):
            continue
        for item in payload.get("results", []):
            citation_pairs.append(
                (str(item.get("source", "")), str(item.get("version", "")))
            )
            retrieved_types.add(str(item.get("policy_type", "")))
    if case["requires_policy_citation"]:
        citation_ok = any(
            source in text and version in text
            for source, version in citation_pairs
            if source and version
        )
    approval_ok = (
        response.approval_id is not None
        if case["expected_status"] == "waiting_for_approval"
        else True
    )
    expected_types = set(case.get("expected_policy_types", []))
    relevance_ok = not expected_types or bool(expected_types & retrieved_types)
    forbidden_sources = set(case.get("forbidden_sources", []))
    inactive_filter_ok = not any(
        source in forbidden_sources for source, _ in citation_pairs
    )
    policy_compliant = (
        phrases_ok
        and status_ok
        and citation_ok
        and approval_ok
        and relevance_ok
        and inactive_filter_ok
    )
    run = get_run(response.run_id) if response.run_id else None
    return {
        "id": case["id"],
        "thread_id": response.thread_id,
        "run_id": response.run_id,
        "actual_tools": actual_tools,
        "required_tools": case["required_tools"],
        "tool_correct": tool_correct,
        "status": response.status,
        "status_ok": status_ok,
        "citation_ok": citation_ok,
        "retrieved_citations": citation_pairs,
        "relevance_ok": relevance_ok,
        "inactive_filter_ok": inactive_filter_ok,
        "approval_ok": approval_ok,
        "forbidden_phrases_ok": phrases_ok,
        "policy_compliant": policy_compliant,
        "latency_ms": run["latency_ms"] if run else None,
        "total_tokens": run["total_tokens"] if run else None,
        "estimated_cost_cny": run["estimated_cost_cny"] if run else None,
        "answer": response.answer,
    }


def build_summary(results: list[dict]) -> dict:
    count = len(results)
    latencies = [item["latency_ms"] for item in results if item["latency_ms"] is not None]
    costs = [item["estimated_cost_cny"] for item in results if item["estimated_cost_cny"] is not None]
    return {
        "case_count": count,
        "tool_accuracy": (
            round(sum(item["tool_correct"] for item in results) / count, 4)
            if count else 0.0
        ),
        "policy_compliance_rate": round(
            sum(item["policy_compliant"] for item in results) / count,
            4,
        ) if count else 0.0,
        "average_latency_ms": (
            round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        ),
        "total_tokens": sum(item["total_tokens"] or 0 for item in results),
        "estimated_cost_cny": round(sum(costs), 6) if costs else None,
    }


def write_markdown(path: Path, report: dict) -> None:
    summary = report["summary"]
    cost_text = (
        summary["estimated_cost_cny"]
        if summary["estimated_cost_cny"] is not None
        else "未配置（Token 已统计）"
    )
    lines = [
        "# Agent 评测报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 用例数：{summary['case_count']}",
        f"- 工具正确率：{summary['tool_accuracy']:.1%}",
        f"- 策略合规率：{summary['policy_compliance_rate']:.1%}",
        f"- 风险分级准确率：{summary['risk_accuracy']:.1%}",
        f"- 失败保护通过率：{summary['failure_protection_rate']:.1%}",
        f"- 使用隔离评测数据库：{summary['isolated_evaluation_database']}",
        f"- 平均延迟：{summary['average_latency_ms']} ms",
        f"- 总 Token：{summary['total_tokens']}",
        f"- 估算成本（CNY）：{cost_text}",
        "",
        "| 用例 | 工具正确 | 策略合规 | 状态 | 延迟(ms) | Token |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for item in report["results"]:
        lines.append(
            f"| {item['id']} | {item['tool_correct']} | "
            f"{item['policy_compliant']} | {item['status']} | "
            f"{item['latency_ms']} | {item['total_tokens']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    cases = load_cases(Path("evals/cases.jsonl"))
    if args.limit > 0:
        cases = cases[: args.limit]

    results = []
    suite_id = uuid4().hex[:8]
    Path(".tmp").mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix="support-agent-eval-",
        dir=".tmp",
    ) as temp_dir:
        temp_path = Path(temp_dir)
        os.environ["DATABASE_URL"] = f"sqlite:///{(temp_path / 'eval.db').as_posix()}"
        os.environ["CHECKPOINT_DATABASE_PATH"] = str(temp_path / "checkpoints.db")
        os.environ["LOG_PATH"] = str(temp_path / "eval.jsonl")
        os.environ["CHAT_INPUT_COST_PER_MILLION_CNY"] = "2"
        os.environ["CHAT_OUTPUT_COST_PER_MILLION_CNY"] = "8"

        from fastapi import HTTPException
        from app.api import run_agent
        from app.api_schemas import AgentRunRequest
        from app.checkpointing import close_checkpointer
        from app.database import engine
        from app.qdrant_store import close_qdrant_client
        from app.run_repository import get_run, list_runs
        from app.seed import prepare_database
        from app.workflow_repository import assess_risk

        prepare_database()
        try:
            for case in cases:
                thread_id = f"eval-{suite_id}-{case['id']}"
                responses = []
                inputs = case["turns"] if "turns" in case else [case["input"]]
                for user_input in inputs:
                    responses.append(
                        run_agent(
                            AgentRunRequest(
                                thread_id=thread_id,
                                message=user_input,
                            )
                        )
                    )
                response = responses[-1]
                if len(responses) > 1:
                    response.tool_calls = [
                        item for response_item in responses for item in response_item.tool_calls
                    ]
                    response.tool_results = [
                        item for response_item in responses for item in response_item.tool_results
                    ]
                result = score_case(case, response, get_run)
                results.append(result)
                print(
                    f"{case['id']}: tools={result['tool_correct']} "
                    f"policy={result['policy_compliant']} "
                    f"latency_ms={result['latency_ms']}"
                )

            risk_cases = [
                ({"amount": 499, "refund_status": "none"}, "refund", "medium"),
                ({"amount": 500, "refund_status": "none"}, "refund", "high"),
                ({"amount": 501, "refund_status": "none"}, "refund", "high"),
                ({"amount": 999, "refund_status": "none"}, "diagnose", "low"),
                ({"amount": 299, "refund_status": "none"}, "repair", "medium"),
                ({"amount": 299, "refund_status": "pending"}, "refund", "high"),
            ]
            risk_accuracy = sum(
                assess_risk(order, action) == expected
                for order, action, expected in risk_cases
            ) / len(risk_cases)

            failure_thread = f"eval-{suite_id}-simulated-timeout"
            with patch("app.api.graph.invoke", side_effect=TimeoutError("simulated")):
                try:
                    run_agent(
                        AgentRunRequest(
                            thread_id=failure_thread,
                            message="模拟上游超时",
                        )
                    )
                except HTTPException:
                    pass
            failure_runs = [
                item
                for item in list_runs(20, "evaluation")
                if item["thread_id"] == f"agent:{failure_thread}"
            ]
            failure_protection_rate = (
                1.0 if failure_runs and failure_runs[0]["status"] == "failed" else 0.0
            )
        finally:
            close_qdrant_client()
            close_checkpointer()
            engine.dispose()

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            **build_summary(results),
            "risk_accuracy": risk_accuracy,
            "failure_protection_rate": failure_protection_rate,
            "isolated_evaluation_database": True,
        },
        "pricing": {
            "model": "deepseek-v4.1-flash",
            "rate_type": "busy_hours_upper_bound",
            "input_cny_per_million_tokens": 2,
            "output_cny_per_million_tokens": 8,
            "verified_on": "2026-11-11",
            "source": "https://help.aliyun.com/zh/model-studio/model-pricing",
        },
        "results": results,
    }
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "eval_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(report_dir / "eval_report.md", report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
