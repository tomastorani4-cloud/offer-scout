"""Ports-and-adapters: every data source is an adapter implementing `Collector`.

The pipeline only knows this interface, so adding a source (a licensed vendor API,
a Google Trends export, ...) never touches scoring or reporting code.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..models import RawRecord, Record


class CollectorError(Exception):
    """A source failed. The pipeline records it in source_failures and continues."""


@dataclass
class ParseContext:
    fx: dict[str, float]
    now: datetime
    lookback_days: int


class Collector(ABC):
    name: str = "base"
    source_class: str = "unknown"      # key into evidence.SOURCE_RELIABILITY
    simulated: bool = False
    country_scoped: bool = False       # True only if the source truly filters/labels by country

    @abstractmethod
    def collect(self, query: str, country: str, limit: int) -> list[RawRecord]:
        """Return raw observations for one query in one country."""

    @abstractmethod
    def parse(self, raw: RawRecord, ctx: ParseContext) -> Record | None:
        """Normalize one raw observation. Return None to skip it."""

    def coverage_warnings(self, country: str) -> list[str]:
        """Known gaps of this source for a country (shown in the report, never hidden)."""
        return []


class HttpClient:
    """Polite HTTP: timeout, throttling, retry with backoff, honors Retry-After."""

    def __init__(self, min_interval_s: float = 0.5, retries: int = 3, user_agent: str = "offer-scout/0.1"):
        try:
            import requests  # lazy so offline use and tests need no extra dependency
        except ImportError as exc:  # pragma: no cover
            raise CollectorError("Install live extras: pip install 'offer-scout[live]'") from exc
        self._requests = requests
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.min_interval_s = min_interval_s
        self.retries = retries
        self._last = 0.0

    def get_json(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        for attempt in range(self.retries + 1):
            wait = self.min_interval_s - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=30)
            except self._requests.RequestException as exc:
                if attempt == self.retries:
                    raise CollectorError(f"network error: {exc}") from exc
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self.retries:
                    raise CollectorError(f"HTTP {resp.status_code} from {url}")
                time.sleep(float(resp.headers.get("Retry-After", 2 ** attempt)))
                continue
            if resp.status_code in (401, 403):
                raise CollectorError(f"HTTP {resp.status_code}: credentials missing, expired or not permitted")
            if not resp.ok:
                raise CollectorError(f"HTTP {resp.status_code} from {url}")
            return resp.json()
        raise CollectorError("unreachable")  # pragma: no cover
