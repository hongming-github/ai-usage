"""Fetch Claude Pro/Max subscription usage from claude.ai's internal API.

Endpoint (unofficial, no public docs):
    GET https://claude.ai/api/organizations/{org}/usage
returns per-window utilization, e.g.
    {"five_hour": {"utilization": 42.0, "resets_at": "...Z"},
     "seven_day": {"utilization": 4.0,  "resets_at": "...Z"}, ...}

`utilization` is the percentage *used* (0-100); remaining = 100 - utilization.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import requests

from .cookies import get_session_key
from .errors import AppError, ErrorKind

BASE_URL = "https://claude.ai/api"
# Capabilities that mark a subscription (chat) org rather than the API org.
_SUBSCRIPTION_CAPS = {"chat", "claude_pro", "claude_max", "claude_team"}
_PLAN_NAMES = {"claude_max": "Claude Max", "claude_pro": "Claude Pro", "claude_team": "Claude Team"}
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Windows we surface, in display order: (API key, stable label used across the app).
_WINDOWS = (("five_hour", "5-hour"), ("seven_day", "7-day"))


@dataclass(frozen=True)
class Window:
    """One rate-limit window."""

    label: str  # stable key, e.g. "5-hour"; the UI localizes it
    utilization: float  # percent used, 0-100
    resets_at: datetime | None

    @property
    def remaining(self) -> int:
        return max(0, round(100 - self.utilization))


@dataclass(frozen=True)
class Usage:
    plan: str
    windows: list[Window]

    @property
    def primary(self) -> Window:
        """The most-consumed window."""
        return max(self.windows, key=lambda w: w.utilization)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class ClaudeClient:
    """Thin client over claude.ai's internal usage endpoint."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": _USER_AGENT, "Accept": "application/json"})
        self._org: str | None = None
        self._plan: str = "Claude"

    def get_usage(self) -> Usage:
        """Fetch current usage. Re-reads the cookie each call so it survives re-logins."""
        self._authenticate()
        if self._org is None:
            self._org = self._discover_org()
        data = self._get_json(f"/organizations/{self._org}/usage")
        windows = self._parse_windows(data)
        if not windows:
            raise AppError(ErrorKind.SERVER, "usage response had no recognizable windows")
        return Usage(self._plan, windows)

    # --- internals ---------------------------------------------------------

    def _authenticate(self) -> None:
        self._session.cookies.set("sessionKey", get_session_key(), domain=".claude.ai")

    def _get_json(self, path: str) -> object:
        try:
            response = self._session.get(f"{BASE_URL}{path}", timeout=20)
        except requests.RequestException as e:
            raise AppError(ErrorKind.NETWORK, str(e)) from e
        if response.status_code == 401:
            raise AppError(ErrorKind.SESSION_EXPIRED, path)
        if response.status_code != 200:
            raise AppError(ErrorKind.SERVER, f"HTTP {response.status_code} on {path}")
        try:
            return response.json()
        except ValueError as e:
            raise AppError(ErrorKind.SERVER, f"invalid JSON from {path}: {e}") from e

    def _discover_org(self) -> str:
        orgs = self._get_json("/organizations")
        for org in orgs:
            caps = set(org.get("capabilities") or [])
            if caps & _SUBSCRIPTION_CAPS:
                self._plan = next((_PLAN_NAMES[c] for c in _PLAN_NAMES if c in caps), "Claude")
                return org["uuid"]
        raise AppError(ErrorKind.NO_SUBSCRIPTION)

    @staticmethod
    def _parse_windows(data: object) -> list[Window]:
        windows: list[Window] = []
        for api_key, label in _WINDOWS:
            window = data.get(api_key) if isinstance(data, dict) else None
            if isinstance(window, dict) and window.get("utilization") is not None:
                windows.append(
                    Window(label, float(window["utilization"]), _parse_dt(window.get("resets_at")))
                )
        return windows
