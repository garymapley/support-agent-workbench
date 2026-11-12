import unittest

from app.rate_limit import SlidingWindowRateLimiter


class SlidingWindowRateLimiterTests(unittest.TestCase):
    def test_rejects_requests_over_limit(self) -> None:
        limiter = SlidingWindowRateLimiter()
        self.assertEqual(
            (True, 0),
            limiter.allow("operator", limit=2, window_seconds=60, now=100),
        )
        self.assertEqual(
            (True, 0),
            limiter.allow("operator", limit=2, window_seconds=60, now=101),
        )
        allowed, retry_after = limiter.allow(
            "operator", limit=2, window_seconds=60, now=102
        )
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)

    def test_expired_events_leave_window(self) -> None:
        limiter = SlidingWindowRateLimiter()
        limiter.allow("operator", limit=1, window_seconds=10, now=100)
        self.assertEqual(
            (True, 0),
            limiter.allow("operator", limit=1, window_seconds=10, now=111),
        )


if __name__ == "__main__":
    unittest.main()
