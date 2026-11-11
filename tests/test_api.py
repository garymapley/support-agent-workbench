import unittest
from unittest.mock import patch

from fastapi import HTTPException
from langchain_core.messages import AIMessage

from app.api import (
    app,
    create_ticket,
    decide_approval,
    get_agent_history,
    get_order,
    health,
    request_refund_approval,
    run_agent,
)
from app.api_schemas import (
    AgentRunRequest,
    ApprovalDecisionRequest,
    RefundApprovalRequest,
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

        approval_result = request_refund_approval(
            ticket["ticket_id"],
            RefundApprovalRequest(reason="高金额退款需要主管审批"),
        )
        self.assertEqual(
            approval_result["workflow_status"], "paused_for_human"
        )
        approval_id = approval_result["approval"]["approval_id"]

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
        self.assertEqual(result.answer, "已收到，我会继续处理。")
        config = invoke.call_args.kwargs["config"]
        self.assertEqual(
            config["configurable"]["thread_id"],
            "agent:api-test-thread",
        )

    def test_empty_thread_history(self) -> None:
        result = get_agent_history("not-started-thread")
        self.assertEqual(result["messages"], [])


if __name__ == "__main__":
    unittest.main()
