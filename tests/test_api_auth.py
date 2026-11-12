"""管理接口鉴权回归测试。

只做只读探测：所有请求要么在鉴权层被拒，要么读现有数据，不写入业务库。
"""

import unittest

from fastapi.testclient import TestClient

from app.api import agent_rate_limiter, app
from app.config import get_settings

TOKEN = "test-admin-token"


class AdminAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = get_settings()
        cls.original_token = cls.settings.admin_token
        cls.original_operator_token = cls.settings.operator_token
        cls.original_reviewer = cls.settings.admin_reviewer
        cls.settings.admin_token = TOKEN
        cls.settings.operator_token = "test-operator-token"
        cls.settings.admin_reviewer = "测试审批人"
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.settings.admin_token = cls.original_token
        cls.settings.operator_token = cls.original_operator_token
        cls.settings.admin_reviewer = cls.original_reviewer
        cls.client.__exit__(None, None, None)

    def test_health_is_public(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)

    def test_management_requires_token(self) -> None:
        for path in (
            "/tickets?limit=5",
            "/orders?limit=5",
            "/approvals?limit=5",
            "/observability/summary?scope=runtime",
            "/agent/threads/demo-1/history",
        ):
            response = self.client.get(path)
            self.assertEqual(401, response.status_code, path)

    def test_wrong_token_is_rejected(self) -> None:
        response = self.client.get(
            "/tickets?limit=5", headers={"X-Admin-Token": "wrong"}
        )
        self.assertEqual(401, response.status_code)

    def test_decision_requires_token(self) -> None:
        response = self.client.post(
            "/approvals/missing/decision",
            json={"decision": "approve", "reviewer": "自报名字", "comment": ""},
        )
        self.assertEqual(401, response.status_code)

    def test_valid_token_passes(self) -> None:
        headers = {"X-Admin-Token": TOKEN}
        response = self.client.get("/tickets?limit=5", headers=headers)
        self.assertEqual(200, response.status_code)
        summary = self.client.get(
            "/observability/summary?scope=runtime", headers=headers
        )
        self.assertEqual(200, summary.status_code)

    def test_operator_can_read_but_cannot_decide(self) -> None:
        headers = {"X-Admin-Token": "test-operator-token"}
        response = self.client.get("/tickets?limit=5", headers=headers)
        self.assertEqual(200, response.status_code)
        decision = self.client.post(
            "/approvals/missing/decision",
            headers=headers,
            json={"decision": "approve", "reviewer": "伪造名字", "comment": ""},
        )
        self.assertEqual(403, decision.status_code)

    def test_unconfigured_token_fails_closed(self) -> None:
        self.settings.admin_token = ""
        response = self.client.get(
            "/tickets?limit=5", headers={"X-Admin-Token": TOKEN}
        )
        self.assertEqual(503, response.status_code)
        self.settings.admin_token = TOKEN

    def test_agent_endpoint_is_rate_limited(self) -> None:
        original_limit = self.settings.agent_rate_limit_requests
        original_window = self.settings.agent_rate_limit_window_seconds
        self.settings.agent_rate_limit_requests = 1
        self.settings.agent_rate_limit_window_seconds = 60
        agent_rate_limiter.clear()
        try:
            headers = {"X-Admin-Token": "invalid-rate-limit-token"}
            first = self.client.post(
                "/agent/runs",
                headers=headers,
                json={"message": "限流探测"},
            )
            second = self.client.post(
                "/agent/runs",
                headers=headers,
                json={"message": "限流探测"},
            )
            self.assertEqual(401, first.status_code)
            self.assertEqual(429, second.status_code)
            self.assertIn("Retry-After", second.headers)
        finally:
            self.settings.agent_rate_limit_requests = original_limit
            self.settings.agent_rate_limit_window_seconds = original_window
            agent_rate_limiter.clear()

    def test_request_body_size_is_limited(self) -> None:
        original_limit = self.settings.max_request_body_bytes
        self.settings.max_request_body_bytes = 32
        try:
            response = self.client.post(
                "/tickets",
                content=b"x" * 33,
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(413, response.status_code)
        finally:
            self.settings.max_request_body_bytes = original_limit


if __name__ == "__main__":
    unittest.main()
