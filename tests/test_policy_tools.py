import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.tools.policy_tools import search_policy


class PolicyToolTests(unittest.TestCase):
    @patch("app.tools.policy_tools.embed_query", return_value=[0.1, 0.2])
    @patch("app.tools.policy_tools.get_qdrant_client")
    def test_search_filters_inactive_policies(
        self,
        get_client,
        _embed_query,
    ) -> None:
        client = MagicMock()
        client.collection_exists.return_value = True
        client.query_points.return_value = SimpleNamespace(points=[])
        get_client.return_value = client

        result = json.loads(
            search_policy.invoke(
                {"query": "退款条件", "policy_type": "refund"}
            )
        )

        self.assertFalse(result["found"])
        query_filter = client.query_points.call_args.kwargs["query_filter"]
        conditions = [condition.model_dump() for condition in query_filter.must]
        self.assertTrue(
            any(
                item.get("key") == "is_active"
                and item.get("match", {}).get("value") is True
                for item in conditions
            )
        )


if __name__ == "__main__":
    unittest.main()
