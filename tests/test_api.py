import os
import tempfile
import unittest
from unittest.mock import patch

# 测试使用独立临时库，避免污染 data/app.db
_TEST_DIR = os.path.join(
    tempfile.gettempdir(), f"support-agent-tests-{os.getpid()}"
)
os.makedirs(_TEST_DIR, exist_ok=True)
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{_TEST_DIR.replace(os.sep, '/')}/app.db",
)
os.environ.setdefault(
    "CHECKPOINT_DATABASE_PATH", f"{_TEST_DIR}/checkpoints.db"
)
os.environ.setdefault("LOG_PATH", f"{_TEST_DIR}/agent.jsonl")

from fastapi import HTTPException
from langchain_core.messages import AIMessage

from app.api import (
    app,
    create_ticket,
    decide_approval,
    get_agent_history,
    get_order,
    get_run_records,
    get_run_summary,
    handoff_ticket,
    health,
    run_agent,
)
from app.api_schemas import (
    AgentRunRequest,
    ApprovalDecisionRequest,
    HandoffRequest,
    TicketCreateRequest,
)
from app.seed import prepare_database


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        prepare_database()

    def test_health_and_openapi(self) -> None:
        self.assertEqual(health(), {"status": "ok"})
        openapi = app.openapi()
        self.assertIn("/agent/runs", openapi["paths"])
        self.assertIn("/tickets/{ticket_id}/refund-approval", openapi["paths"])
        self.assertIn("/tickets/{ticket_id}/handoff", openapi["paths"])

    def test_order_lookup(self) -> None:
        self.assertEqual(get_order("A1001")["order_id"], "A1001")
        with self.assertRaises(HTTPException) as context:
            get_order("UNKNOWN")
        self.assertEqual(context.exception.status_code, 404)

    def test_ticket_and_refund_approval_flow(self) -> None:
        ticket = create_ticket(
            TicketCreateRequest(
                order_id="A1003",
                issue_type="refund",
                description="API 自动化测试退款工单",
                proposed_action="refund",
            )
        )
        self.assertEqual(ticket["risk_level"], "high")

        approval_result = {
            "approval": ticket["approval"],
            "agent_run": ticket["agent_run"],
        }
        self.assertEqual(
            approval_result["agent_run"]["status"],
            "waiting_for_approval",
        )
        self.assertTrue(
            approval_result["agent_run"]["waiting_for_approval"]
        )
        waiting_run = run_agent(
            AgentRunRequest(
                thread_id=approval_result["agent_run"]["thread_id"],
                message="审批通过了吗？",
            )
        )
        self.assertEqual(waiting_run.status, "waiting_for_approval")
        approval_id = approval_result["approval"]["approval_id"]

        with self.assertRaises(HTTPException) as handoff_context:
            handoff_ticket(
                ticket["ticket_id"],
                HandoffRequest(reason="审批期间不应直接转人工"),
            )
        self.assertEqual(handoff_context.exception.status_code, 409)

        decision = decide_approval(
            approval_id,
            ApprovalDecisionRequest(
                decision="reject",
                reviewer="api_test_manager",
                comment="测试拒绝",
            ),
        )
        self.assertEqual(decision["approval"]["status"], "rejected")
        self.assertEqual(decision["ticket"]["status"], "approval_rejected")
        self.assertEqual(decision["agent_run"]["status"], "completed")
        self.assertFalse(decision["agent_run"]["waiting_for_approval"])

        with self.assertRaises(HTTPException) as context:
            decide_approval(
                approval_id,
                ApprovalDecisionRequest(
                    decision="approve",
                    reviewer="another_manager",
                ),
            )
        self.assertEqual(context.exception.status_code, 409)

    @patch("app.api.graph.invoke")
    def test_agent_run_contract(self, invoke) -> None:
        invoke.return_value = {
            "messages": [AIMessage(content="已收到，我会继续处理。")]
        }
        result = run_agent(
            AgentRunRequest(
                thread_id="api-test-thread",
                message="查询订单",
            )
        )
        self.assertEqual(result.thread_id, "api-test-thread")
        self.assertEqual(result.status, "completed")
        self.assertFalse(result.waiting_for_approval)
        self.assertEqual(result.answer, "已收到，我会继续处理。")
        self.assertIsNotNone(result.run_id)
        config = invoke.call_args.kwargs["config"]
        self.assertEqual(
            config["configurable"]["thread_id"],
            "agent:api-test-thread",
        )

    def test_empty_thread_history(self) -> None:
        result = get_agent_history("not-started-thread")
        self.assertEqual(result["messages"], [])

    def test_ticket_can_be_handed_to_a_person(self) -> None:
        ticket = create_ticket(
            TicketCreateRequest(
                order_id="A1001",
                issue_type="other",
                description="需要人工复核的演示工单",
                proposed_action="human_handoff",
            )
        )
        result = handoff_ticket(
            ticket["ticket_id"],
            HandoffRequest(reason="客户要求人工专员回电"),
        )
        self.assertEqual(result["status"], "human_handoff")
        self.assertEqual(result["handoff_reason"], "客户要求人工专员回电")

    def test_observability_endpoints(self) -> None:
        summary = get_run_summary(scope="runtime")
        self.assertGreaterEqual(summary["run_count"], 1)
        self.assertIn("average_latency_ms", summary)
        runs = get_run_records(limit=10, scope="runtime")
        self.assertTrue(runs)
        self.assertIn("run_id", runs[0])


if __name__ == "__main__":
    unittest.main()
