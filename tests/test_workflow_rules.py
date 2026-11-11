import json
import os
import tempfile
import unittest

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

from app.tools.workflow_tools import get_approval_status
from app.workflow_repository import assess_risk
from app.seed import prepare_database
from app.workflow_repository import create_support_ticket


class WorkflowRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        prepare_database()

    def test_ticket_records_agent_thread(self) -> None:
        ticket = create_support_ticket(
            "A1001",
            "other",
            "验证工单与会话的关联",
            "diagnose",
            thread_id="agent:test-thread",
        )
        self.assertEqual(ticket["thread_id"], "agent:test-thread")

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

    def test_refund_issue_type_overrides_action_misclassification(self) -> None:
        ticket = create_support_ticket(
            order_id="A1001",
            issue_type="refund",
            description="客户明确申请退款。",
            proposed_action="diagnose",
            thread_id="agent:test-refund-override",
        )
        self.assertEqual(ticket["issue_type"], "refund")
        self.assertEqual(ticket["proposed_action"], "refund")
        self.assertEqual(ticket["status"], "pending_approval")


if __name__ == "__main__":
    unittest.main()
