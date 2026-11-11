import unittest

from app.execution_guard import ThreadBusyError, guard_thread


class ExecutionGuardTests(unittest.TestCase):
    def test_rejects_concurrent_run_for_same_thread(self) -> None:
        with guard_thread("agent:same-thread"):
            with self.assertRaises(ThreadBusyError):
                with guard_thread("agent:same-thread"):
                    pass

    def test_allows_different_threads(self) -> None:
        with guard_thread("agent:first"):
            with guard_thread("agent:second"):
                pass


if __name__ == "__main__":
    unittest.main()
