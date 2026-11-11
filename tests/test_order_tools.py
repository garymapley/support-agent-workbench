import json
import unittest

from app.tools.order_tools import get_order
from app.order_repository import count_orders
from app.seed import prepare_database, seed_orders


class GetOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        prepare_database()

    def test_returns_known_order(self) -> None:
        result = json.loads(get_order.invoke({"order_id": "a1001"}))

        self.assertTrue(result["found"])
        self.assertEqual(result["order"]["order_id"], "A1001")
        self.assertEqual(result["order"]["order_status"], "delivered")

    def test_returns_not_found_for_unknown_order(self) -> None:
        result = json.loads(get_order.invoke({"order_id": "A9999"}))

        self.assertFalse(result["found"])
        self.assertEqual(result["order_id"], "A9999")

    def test_seed_is_idempotent(self) -> None:
        self.assertEqual(seed_orders(), 0)
        self.assertGreaterEqual(count_orders(), 3)


if __name__ == "__main__":
    unittest.main()
