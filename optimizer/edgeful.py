"""Edgeful market-data API client.

Real endpoint structure (confirmed via probing):
  GET /report_calculation/{slug}/{asset_class}/{ticker}
      ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD[&extra_params]

  GET /historic_data_screener?market_type={market_type}&tickers={ticker}

Authentication: Authorization: Bearer <api_key>
Base URL:       https://api.edgeful.com
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

log = logging.getLogger(__name__)

_BASE_URL = "https://api.edgeful.com"
_DEFAULT_TIMEOUT = 15

# Confirmed-working report slugs (daily OHLC reports).
# Intraday-bar reports (ORB, IB, session, engulfing, FVG, etc.) return 404
# and are not yet accessible via the API.
REPORT_SLUGS = [
    "gap-fill-standard",
    "gap-fill-by-close",
    "gap-fill-by-prev-candle",
    "gap-fill-by-weekday",
    "gap-fill-by-size",
    "outside-days-standard",
    "outside-days-by-weekday",
    "outside-days-by-close",
    "previous-days-range-standard",
    "green-and-red-days-by-weekday-standard",
    "green-and-red-streaks-standard",
    "opening-stats-standard",
    "opening-stats-by-weekday",
    "adr-average-daily-range-standard",
    "adr-average-daily-range-by-extension",
    "adr-average-daily-range-by-weekday",
    "adr-average-daily-range-by-streak",
    "adr-average-daily-range-by-range-to-adr-by-weekday",
    "atr-average-true-range-standard",
    "performance-by-weekday-standard",
    "overnight-continuation-standard",
    "overnight-continuation-by-weekday",
    "fibonacci-levels-standard",
    "high-and-low-by-weekday-standard",
    "inside-bars-standard",
    "inside-bars-by-weekday",
    "previous-session-correlation-standard",
    "previous-weeks-range-standard",
    "seasonality-standard",
    "sma-performance-standard",
    "volume-and-range-by-weekday-standard",
    "pivot-points-standard",
]


class EdgefulClient:
    """Thin HTTP wrapper around the Edgeful REST API.

    Usage::

        client = EdgefulClient(api_key="ef_live_…")

        # Fetch a specific report
        data = client.get_report("gap-fill-standard", "futures", "NQ",
                                 start_date="2025-06-01", end_date="2026-06-11")

        # Live screener snapshot
        screener = client.get_screener("futures", tickers=["NQ", "ES"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = _BASE_URL,
        timeout: int = _DEFAULT_TIMEOUT,
    ):
        if not _REQUESTS_AVAILABLE:
            raise ImportError(
                "The 'requests' package is required.\n"
                "Install it with:  pip install requests"
            )

        self.api_key  = api_key or os.getenv("EDGEFUL_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

        if not self.api_key:
            raise ValueError(
                "Edgeful API key not set.\n"
                "Pass api_key= or set the EDGEFUL_API_KEY environment variable."
            )

        self._session = self._build_session()

    def _build_session(self) -> "requests.Session":
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept":        "application/json",
        })
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://",  adapter)
        return session

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        log.debug("GET %s  params=%s", url, params)
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _default_dates(lookback_days: int = 365) -> tuple[str, str]:
        end   = date.today()
        start = end - timedelta(days=lookback_days)
        return start.isoformat(), end.isoformat()

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_report(
        self,
        slug: str,
        asset_class: str,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **extra_params: Any,
    ) -> Dict:
        """Fetch a single probability report.

        Args:
            slug:        Report slug, e.g. ``"gap-fill-standard"``.
            asset_class: ``"futures"``, ``"stocks"``, ``"forex"``, ``"crypto"``.
            symbol:      Ticker, e.g. ``"NQ"``, ``"ES"``, ``"SPY"``.
            start_date:  ISO date string. Defaults to 12 months ago.
            end_date:    ISO date string. Defaults to today.
            **extra_params: Additional query params forwarded to the endpoint.

        Returns:
            Raw JSON dict from the API.
        """
        if not start_date or not end_date:
            start_date, end_date = self._default_dates()
        params: Dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        params.update(extra_params)
        return self._get(f"/report_calculation/{slug}/{asset_class}/{symbol}", params)

    def get_reports(
        self,
        slugs: List[str],
        asset_class: str,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch multiple reports, returning {slug: data_or_error}."""
        if not start_date or not end_date:
            start_date, end_date = self._default_dates()
        results: Dict[str, Any] = {}
        for slug in slugs:
            try:
                results[slug] = self.get_report(slug, asset_class, symbol,
                                                start_date, end_date)
            except Exception as exc:
                log.warning("report %s: %s", slug, exc)
                results[slug] = None
        return results

    # ------------------------------------------------------------------
    # Live screener snapshot
    # ------------------------------------------------------------------

    def get_screener(
        self,
        market_type: str = "futures",
        tickers: Optional[List[str]] = None,
    ) -> Dict:
        """Fetch the most recent screener snapshot (last completed session).

        Args:
            market_type: ``"futures"``, ``"stocks"``, ``"forex"``, ``"crypto"``.
            tickers:     Optional list of tickers to filter, e.g. ``["NQ", "ES"]``.

        Returns:
            Dict keyed by ticker symbol with per-report analysis nested under each.
        """
        params: Dict[str, Any] = {"market_type": market_type}
        if tickers:
            params["tickers"] = ",".join(tickers)
        data = self._get("/historic_data_screener", params)
        return data.get("historic_data", data) if isinstance(data, dict) else data
