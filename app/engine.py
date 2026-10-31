"""Background checking engine (GUI-independent, thread based).

The GUI never blocks: it polls `engine.events` (a thread-safe queue) and
receives tuples:
    ("result", Result)
    ("progress", done, total)
    ("info", message)
    ("done", stopped: bool)
"""
import queue
import threading
from typing import List

from .backends import Backend
from .models import Result, Status
from .validation import validate

MAX_RETRIES = 5


class CheckEngine:
    def __init__(self, backend: Backend, delay: float = 1.0):
        self.backend = backend
        self.delay = delay
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self._stop = threading.Event()
        self._running = threading.Event()  # set = running, clear = paused
        self._running.set()
        self._thread: threading.Thread | None = None

    # -- control -----------------------------------------------------
    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, names: List[str]) -> None:
        if self.active:
            return
        self._stop.clear()
        self._running.set()
        self._thread = threading.Thread(target=self._run, args=(list(names),), daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    def stop(self) -> None:
        self._stop.set()
        self._running.set()  # wake if paused

    # -- worker ------------------------------------------------------
    def _sleep(self, seconds: float) -> None:
        """Interruptible sleep."""
        self._stop.wait(seconds)

    def _run(self, names: List[str]) -> None:
        total = len(names)
        for i, name in enumerate(names):
            self._running.wait()
            if self._stop.is_set():
                break

            err = validate(name)
            if err:
                result = Result(name, Status.INVALID, err)
            else:
                result = self._check_with_retry(name)
                if self._stop.is_set() and result.status is Status.RATE_LIMITED:
                    break

            self.events.put(("result", result))
            self.events.put(("progress", i + 1, total))

            if err is None and i < total - 1:
                self._sleep(self.delay)

        self.events.put(("done", self._stop.is_set()))

    def _check_with_retry(self, name: str) -> Result:
        result = Result(name, Status.ERROR, "no attempt")
        for _ in range(MAX_RETRIES):
            try:
                result = self.backend.check(name)
            except Exception as exc:  # backend bug / network
                return Result(name, Status.ERROR, str(exc))
            if result.status is not Status.RATE_LIMITED:
                return result
            wait = max(result.retry_after, 1.0)
            self.events.put(("info", f"Rate limited - waiting {wait:.0f}s"))
            self._sleep(wait)
            if self._stop.is_set():
                return result
        return result
