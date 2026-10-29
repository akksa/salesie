"""Keeps agent load bounded. Waiting happens here, in memory, before a database connection is taken:
turns for one shopper run one at a time, at most N turns run at once (well below the connection pool),
and a shopper who burns through the daily turn budget is handed to the owner instead of costing more."""

import asyncio
import time
import weakref
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

_DAY_SECONDS = 86_400.0


class AgentGate:
    def __init__(self, *, max_concurrent_turns: int, turns_per_contact_per_day: int) -> None:
        self._slots = asyncio.Semaphore(max_concurrent_turns)
        self._contact_locks: weakref.WeakValueDictionary[int, asyncio.Lock] = weakref.WeakValueDictionary()
        self._turns: dict[int, deque[float]] = {}
        self._budget = turns_per_contact_per_day

    @asynccontextmanager
    async def turn(self, contact_id: int) -> AsyncIterator[None]:
        lock = self._contact_locks.get(contact_id)
        if lock is None:
            lock = asyncio.Lock()
            self._contact_locks[contact_id] = lock
        async with lock, self._slots:
            yield

    def spend(self, contact_id: int) -> bool:
        """Count one model turn for this shopper; False once today's budget is used up."""
        now = time.monotonic()
        window = self._turns.setdefault(contact_id, deque())
        while window and window[0] < now - _DAY_SECONDS:
            window.popleft()
        if len(window) >= self._budget:
            return False
        window.append(now)
        return True
