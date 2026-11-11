import json
import unittest

from app.tools.workflow_tools import get_approval_status
from app.workflow_repository import assess_risk
from app.seed import prepare_database
from app.workflow_repository import create_support_ticket


class WorkflowRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        prepare_database()

    def test_high_value_refund_is_high_risk(self) -> None:
        order = {"amount": 529, "refund_status": "none"}
        self.assertEqual(assess_risk(order, "refund"), "high")

    def test_existing_refund_state_is_high_risk(self) -> None:
        order = {"amount": 299, "refund_status": "pending_manual_approval"}
        self.assertEqual(assess_risk(order, "refund"), "high")

    def test_small_refund_is_medium_risk(self) -> None:
        order = {"amount": 299, "refund_status": "none"}
        self.assertEqual(assess_risk(order, "refund"), "medium")

    def test_diagnosis_is_low_risk(self) -> None:
        order = {"amount": 999, "refund_status": "none"}
        self.assertEqual(assess_risk(order, "diagnose"), "low")

    def test_refund_ticket_always_creates_approval(self) -> None:
        ticket = create_support_ticket(
            order_id="A1001",
            issue_type="refund",
            description="验证代码层强制审批",
            proposed_action="refund",
            thread_id="agent:test-force-approval",
        )
        self.assertEqual(ticket["status"], "pending_approval")
        self.assertEqual(ticket["approval"]["status"], "pending")
        self.assertEqual(
            ticket["approval"]["thread_id"],
            "agent:test-force-approval",
        )
        status = json.loads(
            get_approval_status.invoke(
                {"ticket_id": ticket["ticket_id"]}
            )
        )
        self.assertTrue(status["found"])
        self.assertEqual(status["approval"]["status"], "pending")

    def test_explicit_refund_text_overrides_model_misclassification(self) -> None:
        ticket = create_support_ticket(
            order_id="A1001",
            issue_type="quality",
            description="客户明确要求退款，但模型误判成检测。",
            proposed_action="diagnose",
            thread_id="agent:test-refund-override",
        )
        self.assertEqual(ticket["issue_type"], "refund")
        self.assertEqual(ticket["proposed_action"], "refund")
        self.assertEqual(ticket["status"], "pending_approval")


if __name__ == "__main__":
    unittest.main()
