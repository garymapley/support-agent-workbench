import unittest

from app.workflow_repository import assess_risk


class WorkflowRiskTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
