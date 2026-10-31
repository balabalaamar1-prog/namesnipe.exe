"""Availability backends. The engine only needs `.check(name) -> Result`.

Checkpoint 1 ships only DemoBackend (no network). Checkpoint 2 adds the
real Discord backend with the same interface.
"""
import hashlib
import time
from typing import Protocol

from .models import Result, Status


class Backend(Protocol):
    def check(self, name: str) -> Result: ...


class DemoBackend:
    """Fake, deterministic backend so the UI can be tried without any network."""

    def check(self, name: str) -> Result:
        time.sleep(0.15)
        taken = hashlib.md5(name.encode()).digest()[0] % 3 != 0
        return Result(name, Status.TAKEN if taken else Status.AVAILABLE, "demo")


class DiscordBackend:
    """Real check via Discord's public (unauthenticated) username-attempt endpoint.

    No account token is used or needed. Discord rate-limits this endpoint
    aggressively, so keep the delay >= ~1.5s; 429s are reported as
    RATE_LIMITED with `retry_after` and the engine waits and retries.
    """

    URL = "https://discord.com/api/v9/unique-username/username-attempt-unauthed"

    def __init__(self, url: str | None = None, timeout: float = 15.0):
        import requests  # imported lazily so the demo needs no network libs

        self._requests = requests
        self.url = url or self.URL
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        })

    def check(self, name: str) -> Result:
        try:
            resp = self.session.post(self.url, json={"username": name}, timeout=self.timeout)
        except self._requests.RequestException as exc:
            return Result(name, Status.ERROR, f"network: {exc.__class__.__name__}")

        if resp.status_code == 429:
            try:
                retry = float(resp.json().get("retry_after", 5))
            except Exception:
                retry = float(resp.headers.get("Retry-After", 5))
            return Result(name, Status.RATE_LIMITED, "rate limited", retry_after=retry)

        try:
            data = resp.json()
        except ValueError:
            return Result(name, Status.ERROR, f"HTTP {resp.status_code}: bad response")

        if resp.status_code == 200 and isinstance(data, dict) and "taken" in data:
            return Result(name, Status.TAKEN if data["taken"] else Status.AVAILABLE)

        if resp.status_code == 400:
            if "captcha_key" in data:
                return Result(name, Status.ERROR, "Discord asked for a captcha - slow down / retry later")
            return Result(name, Status.INVALID, "rejected by Discord")

        return Result(name, Status.ERROR, f"HTTP {resp.status_code}")
