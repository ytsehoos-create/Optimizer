"""Edgeful market-data API client.

Edgeful provides probability-based trading reports (gap fills, ORB, initial
balance, previous-day levels, etc.) plus a "What's in Play?" live-setup feed.

Authentication: Bearer token via the ``Authorization`` header.
Base URL:       https://api.edgeful.com

All public methods return plain Python dicts / lists so callers don't need to
import anything from this module beyond the client class itself.
"""
from __future__ import annotations

import logging
import os
import time
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
_DEFAULT_TIMEOUT = 15  # seconds per request


class EdgefulClient:
    """Thin HTTP wrapper around the Edgeful REST API.

    Usage::

        client = EdgefulClient(api_key="ef_live_…")

        # What's in play right now?
        live = client.get_live_setups()

        # Historical probability reports
        reports = client.list_reports()
        detail  = client.get_report(reports[0]["id"])

        # Instrument metadata
        instruments = client.list_instruments()
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = _BASE_URL,
        timeout: int = _DEFAULT_TIMEOUT,
    ):
        if not _REQUESTS_AVAILABLE:
            raise ImportError(
                "The 'requests' package is required for Edgeful API access.\n"
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

    # ------------------------------------------------------------------
    # Session setup
    # ------------------------------------------------------------------

    def _build_session(self) -> "requests.Session":
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
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

    # ------------------------------------------------------------------
    # Core request helper
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        log.debug("GET %s  params=%s", url, params)
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Reports — 150+ historical probability reports
    # ------------------------------------------------------------------

    def list_reports(
        self,
        asset_class: Optional[str] = None,
        symbol:      Optional[str] = None,
    ) -> List[Dict]:
        """Return the list of available probability reports.

        Args:
            asset_class: Filter by asset class, e.g. ``"futures"``, ``"stocks"``,
                         ``"forex"``, ``"crypto"``, ``"etf"``.
            symbol:      Filter by ticker symbol, e.g. ``"ES"``, ``"NQ"``, ``"SPY"``.

        Returns:
            List of report dicts, each containing at minimum:
            ``id``, ``name``, ``asset_class``, ``symbol``, ``description``.
        """
        params: Dict[str, str] = {}
        if asset_class:
            params["asset_class"] = asset_class
        if symbol:
            params["symbol"] = symbol
        data = self._get("/v1/reports", params or None)
        return data if isinstance(data, list) else data.get("data", data.get("reports", []))

    def get_report(self, report_id: str, symbol: Optional[str] = None) -> Dict:
        """Fetch the full data for a single report.

        Args:
            report_id: The report identifier returned by :meth:`list_reports`.
            symbol:    Optional symbol override if the report supports multiple
                       instruments (e.g. ``"ES"``, ``"NQ"``).

        Returns:
            Dict with the report payload, typically including:
            ``id``, ``name``, ``symbol``, ``statistics``, ``updated_at``.
        """
        params = {"symbol": symbol} if symbol else None
        return self._get(f"/v1/reports/{report_id}", params)

    def get_report_statistics(
        self,
        report_id: str,
        symbol: Optional[str] = None,
        lookback_days: Optional[int] = None,
    ) -> Dict:
        """Return just the statistical summary for a report.

        Useful for quickly checking probability percentages without the full
        metadata payload.
        """
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        if lookback_days:
            params["lookback_days"] = lookback_days
        return self._get(f"/v1/reports/{report_id}/statistics", params or None)

    # ------------------------------------------------------------------
    # Live data — "What's in Play?" real-time setup feed
    # ------------------------------------------------------------------

    def get_live_setups(
        self,
        asset_class: Optional[str] = None,
        min_probability: Optional[float] = None,
    ) -> List[Dict]:
        """Return the current "What's in Play?" live setups.

        Each setup represents a high-probability trade scenario that is active
        *right now* based on Edgeful's real-time scanning engine.

        Args:
            asset_class:     Optionally filter by ``"futures"``, ``"stocks"``, etc.
            min_probability: Only return setups with probability ≥ this value
                             (0–100).

        Returns:
            List of setup dicts, each containing:
            ``symbol``, ``report_name``, ``setup_type``, ``probability``,
            ``direction``, ``entry_zone``, ``target``, ``stop``, ``timestamp``.
        """
        params: Dict[str, Any] = {}
        if asset_class:
            params["asset_class"] = asset_class
        if min_probability is not None:
            params["min_probability"] = min_probability
        data = self._get("/v1/live/setups", params or None)
        return data if isinstance(data, list) else data.get("data", data.get("setups", []))

    def get_live_summary(self) -> Dict:
        """Return a high-level summary of the current market state.

        Includes counts of active setups per asset class, overall market
        sentiment, and the timestamp of the last data refresh.
        """
        return self._get("/v1/live/summary")

    # ------------------------------------------------------------------
    # Instruments
    # ------------------------------------------------------------------

    def list_instruments(self, asset_class: Optional[str] = None) -> List[Dict]:
        """Return all instruments supported by the Edgeful platform.

        Args:
            asset_class: Optional filter, e.g. ``"futures"``.

        Returns:
            List of instrument dicts with ``symbol``, ``name``, ``asset_class``,
            ``exchange``, and ``active`` fields.
        """
        params = {"asset_class": asset_class} if asset_class else None
        data = self._get("/v1/instruments", params)
        return data if isinstance(data, list) else data.get("data", data.get("instruments", []))

    # ------------------------------------------------------------------
    # Market context — gap fills, ORB, IB, prev-day levels
    # ------------------------------------------------------------------

    def get_gap_fill_probability(self, symbol: str) -> Dict:
        """Fetch today's gap-fill probability for *symbol*.

        Returns a dict with:
        ``symbol``, ``gap_direction``, ``gap_size_pct``, ``probability``,
        ``historical_fill_rate``, ``avg_fill_time_min``, ``as_of``.
        """
        return self._get(f"/v1/market/{symbol}/gap-fill")

    def get_orb_statistics(self, symbol: str, orb_minutes: int = 15) -> Dict:
        """Opening Range Breakout statistics for *symbol*.

        Args:
            symbol:      Ticker symbol, e.g. ``"ES"``.
            orb_minutes: ORB period in minutes (common values: 5, 15, 30, 60).

        Returns:
            Dict with ``breakout_up_probability``, ``breakout_down_probability``,
            ``avg_extension_atr``, ``false_breakout_rate``, ``best_time_window``.
        """
        return self._get(
            f"/v1/market/{symbol}/orb",
            {"minutes": orb_minutes},
        )

    def get_initial_balance(self, symbol: str) -> Dict:
        """Initial Balance levels and extension probabilities for *symbol*.

        Returns:
        ``ib_high``, ``ib_low``, ``ib_range``, ``extension_1_prob``,
        ``extension_2_prob``, ``value_area_high``, ``value_area_low``.
        """
        return self._get(f"/v1/market/{symbol}/initial-balance")

    def get_previous_day_levels(self, symbol: str) -> Dict:
        """Previous-day high, low, close, and reaction probabilities.

        Returns:
        ``pdh``, ``pdl``, ``pdc``, ``pdh_reaction_prob``, ``pdl_reaction_prob``,
        ``overnight_high``, ``overnight_low``.
        """
        return self._get(f"/v1/market/{symbol}/prev-day-levels")

    def get_volume_profile(
        self,
        symbol: str,
        lookback_days: int = 30,
        opening_window_minutes: int = 15,
    ) -> Dict:
        """Per-session contract volume for *symbol*, including opening-window volume.

        Args:
            symbol:                 Ticker symbol, e.g. ``"NQ"``.
            lookback_days:          Number of most recent trading days to include.
            opening_window_minutes: Size of the opening volume window in minutes
                                     (e.g. ``15`` for the first 15 minutes of RTH).

        Returns:
            Dict with ``avg_daily_volume``, ``avg_opening_window_volume``,
            ``opening_window_pct_of_day``, and ``sessions`` — a list of per-day
            dicts each containing ``date``, ``total_volume``, ``opening_window_volume``.
        """
        return self._get(
            f"/v1/market/{symbol}/volume",
            {"lookback_days": lookback_days, "opening_window_minutes": opening_window_minutes},
        )

    def get_market_context(self, symbol: str) -> Dict:
        """Convenience method — fetch all available context for *symbol* in one call.

        Returns a unified dict with keys ``gap_fill``, ``orb``,
        ``initial_balance``, ``prev_day_levels``, and ``live_setups``.
        Falls back gracefully if individual endpoints are unavailable.
        """
        result: Dict[str, Any] = {"symbol": symbol}
        for key, method, kwargs in [
            ("gap_fill",       self.get_gap_fill_probability, {}),
            ("orb",            self.get_orb_statistics,       {}),
            ("initial_balance",self.get_initial_balance,      {}),
            ("prev_day_levels",self.get_previous_day_levels,  {}),
        ]:
            try:
                result[key] = method(symbol, **kwargs)
            except Exception as exc:
                log.warning("Edgeful %s for %s: %s", key, symbol, exc)
                result[key] = None

        try:
            all_setups = self.get_live_setups()
            result["live_setups"] = [s for s in all_setups if s.get("symbol") == symbol]
        except Exception as exc:
            log.warning("Edgeful live setups for %s: %s", symbol, exc)
            result["live_setups"] = []

        return result

    # ------------------------------------------------------------------
    # Account / health
    # ------------------------------------------------------------------

    def get_account_info(self) -> Dict:
        """Return the authenticated account details and subscription tier."""
        return self._get("/v1/account")

    def health_check(self) -> bool:
        """Return True if the API is reachable and the key is valid."""
        try:
            self._get("/v1/health")
            return True
        except Exception:
            return False
