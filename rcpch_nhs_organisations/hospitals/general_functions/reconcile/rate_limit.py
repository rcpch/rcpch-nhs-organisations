"""
Token-bucket rate limiter for the ODS reconciliation engine.

The ODS API tolerates at most 5000 requests per 5 minutes (~16.6 req/s). The
engine throttles well below this (default ~10 req/s) so a full one-off deep
scan of a few thousand entities completes in a handful of minutes without ever
approaching the ceiling.

The limiter takes injectable ``now`` and ``sleep`` callables so tests can drive
a fake clock and assert the throttle holds without sleeping in real time.
"""
import time


class TokenBucketRateLimiter:
    """A simple token-bucket limiter.

    ``rate`` tokens are added per second up to ``capacity``. Each call to
    ``acquire()`` consumes one token, blocking (via ``sleep``) until a token is
    available. With ``rate=10`` the limiter admits at most ten calls per second
    on average.
    """

    def __init__(self, rate=10.0, capacity=None, now=None, sleep=None):
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.rate = float(rate)
        # Default the bucket capacity to one second's worth of tokens so bursts
        # never exceed the sustained rate by more than ~1s.
        self.capacity = float(capacity) if capacity is not None else float(rate)
        self._now = now or time.monotonic
        self._sleep = sleep or time.sleep
        self._tokens = self.capacity
        self._last = self._now()

    def _refill(self):
        now = self._now()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last = now

    def acquire(self, tokens=1):
        """Block until ``tokens`` are available, then consume them.

        Sleeps once for exactly the current shortfall and then consumes,
        allowing the bucket to dip marginally negative and self-correct on the
        next call. This avoids a re-check loop that could spin indefinitely
        under floating-point refill rounding.
        """
        self._refill()
        if self._tokens < tokens:
            deficit = tokens - self._tokens
            self._sleep(deficit / self.rate)
            self._refill()
        self._tokens -= tokens
