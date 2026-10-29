"""In-memory limiter for failed owner logins (one worker per deployment for the hackathon).

Keyed by client IP. Behind a reverse proxy, run uvicorn with --proxy-headers so the real client IP is
used; otherwise every visitor shares the proxy's IP and an attacker could lock the owner out.
"""

import time
from collections import deque
from dataclasses import dataclass, field

_MAX_TRACKED_CLIENTS = 10_000


@dataclass
class FailedLoginLimiter:
    max_failures: int = 20
    window_seconds: float = 300.0
    _failures: dict[str, deque[float]] = field(default_factory=dict)

    def retry_after(self, client: str) -> int | None:
        """Seconds until this client may try again, or None if it isn't blocked."""
        recent = self._window(client)
        if len(recent) < self.max_failures:
            return None
        return max(1, int(recent[0] + self.window_seconds - time.monotonic()) + 1)

    def record_failure(self, client: str) -> None:
        if len(self._failures) >= _MAX_TRACKED_CLIENTS:
            self._forget_idle_clients()
        self._window(client).append(time.monotonic())

    def _window(self, client: str) -> deque[float]:
        cutoff = time.monotonic() - self.window_seconds
        window = self._failures.setdefault(client, deque())
        while window and window[0] < cutoff:
            window.popleft()
        return window

    def _forget_idle_clients(self) -> None:
        cutoff = time.monotonic() - self.window_seconds
        idle = [client for client, window in self._failures.items() if not window or window[-1] < cutoff]
        for client in idle:
            del self._failures[client]
