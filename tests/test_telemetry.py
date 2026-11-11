import unittest

from langchain_core.messages import AIMessage

from app.telemetry import message_metrics, sanitize_text


class TelemetryTests(unittest.TestCase):
    def test_redacts_api_keys(self) -> None:
        value = sanitize_text("key=sk-abcdefghijklmnopqrstuvwxyz123456")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", value)
        self.assertIn("sk-<redacted>", value)

    def test_collects_tokens_and_tools(self) -> None:
        message = AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call-1",
                    "name": "get_order",
                    "args": {"order_id": "A1001"},
                }
            ],
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        )
        metrics = message_metrics([message])
        self.assertEqual(metrics["tools"], ["get_order"])
        self.assertEqual(metrics["total_tokens"], 120)


if __name__ == "__main__":
    unittest.main()
