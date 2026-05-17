"""Selenium-based automation layer for TradingView Strategy Tester."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from .results import BacktestMetrics

log = logging.getLogger(__name__)


# CSS / XPath selectors for TradingView UI elements
_SEL = {
    # Login
    "sign_in_btn": "//button[contains(@class,'user-menu')]//span[text()='Sign in']",
    "email_tab": "//span[text()='Email']",
    "username_input": "input[name='username']",
    "password_input": "input[name='password']",
    "submit_btn": "//button[@type='submit']",

    # Strategy Tester tab
    "strategy_tester_tab": "//div[contains(@class,'tab-label') and contains(.,'Strategy Tester')]",

    # Settings gear on the strategy
    "strategy_settings_gear": "//div[contains(@class,'strategy-controls')]//button[@data-tooltip='Settings']",
    # Fallback: settings button inside the strategy title bar
    "strategy_gear_alt": "//div[contains(@class,'strategyGroup')]//button[@aria-label='Settings']",

    # Inputs tab inside settings dialog
    "inputs_tab": "//button[contains(@id,'inputs') or contains(@class,'tabs-item') and contains(.,'Inputs')]",

    # Performance overview fields (Strategy Tester panel)
    "net_profit_pct": "//div[contains(@class,'performance-item') and .//span[text()='Net Profit']]//span[contains(@class,'positiveValue') or contains(@class,'negativeValue') or contains(@class,'neutralValue')]",
    "overview_table": "//div[contains(@class,'report-overview-wrapper') or contains(@class,'performanceReport')]",
}


def _parse_number(text: str) -> Optional[float]:
    """Convert TradingView display text like '  1,234.56 %' to float."""
    if not text:
        return None
    text = text.strip().replace(",", "").replace(" ", "")
    # Remove trailing % or $ prefix/suffix
    text = re.sub(r"[%$]", "", text)
    try:
        return float(text)
    except ValueError:
        return None


class TradingViewConnector:
    """Drives a TradingView chart, changes strategy inputs, and reads backtest metrics."""

    def __init__(self, config: dict):
        self.config = config
        self.driver: Optional[webdriver.Remote] = None
        self._wait: Optional[WebDriverWait] = None
        self._logged_in = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Launch browser and log in to TradingView."""
        self.driver = self._build_driver()
        self._wait = WebDriverWait(
            self.driver,
            timeout=self.config.get("implicit_wait", 10),
        )
        self._login()

    def stop(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ------------------------------------------------------------------
    # Browser setup
    # ------------------------------------------------------------------

    def _build_driver(self) -> webdriver.Remote:
        browser = self.config.get("browser", "chrome").lower()
        headless = self.config.get("headless", False)

        if browser == "chrome":
            opts = ChromeOptions()
            if headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opts)
        elif browser == "firefox":
            opts = FirefoxOptions()
            if headless:
                opts.add_argument("--headless")
            service = ChromeService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=opts)
        else:
            raise ValueError(f"Unsupported browser: {browser}")

        driver.set_page_load_timeout(self.config.get("page_load_timeout", 30))
        return driver

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _login(self):
        username = self.config.get("username") or os.getenv("TV_USERNAME", "")
        password = self.config.get("password") or os.getenv("TV_PASSWORD", "")
        chart_url = self.config.get("chart_url") or os.getenv("TV_CHART_URL", "")

        if not username or not password:
            raise RuntimeError(
                "TradingView credentials not set. "
                "Set TV_USERNAME and TV_PASSWORD environment variables or edit config.yaml."
            )
        if not chart_url:
            raise RuntimeError(
                "TV_CHART_URL not set. Point it at the chart containing your strategy."
            )

        log.info("Navigating to TradingView…")
        self.driver.get("https://www.tradingview.com")
        time.sleep(2)

        # Click sign-in if not already logged in
        try:
            sign_in = self.driver.find_element(By.XPATH, _SEL["sign_in_btn"])
            sign_in.click()
            time.sleep(1)
        except NoSuchElementException:
            log.debug("Already on a login page or sign-in button not found.")

        # Choose email login
        try:
            email_tab = self._wait_for(By.XPATH, _SEL["email_tab"])
            email_tab.click()
            time.sleep(0.5)
        except TimeoutException:
            pass

        self._fill_input(By.CSS_SELECTOR, _SEL["username_input"], username)
        self._fill_input(By.CSS_SELECTOR, _SEL["password_input"], password)

        submit = self._wait_for(By.XPATH, _SEL["submit_btn"])
        submit.click()
        time.sleep(3)

        log.info("Loading chart: %s", chart_url)
        self.driver.get(chart_url)
        time.sleep(5)

        self._open_strategy_tester()
        self._logged_in = True
        log.info("Login and chart load complete.")

    # ------------------------------------------------------------------
    # Strategy Tester panel
    # ------------------------------------------------------------------

    def _open_strategy_tester(self):
        try:
            tab = self._wait_for(By.XPATH, _SEL["strategy_tester_tab"], timeout=15)
            tab.click()
            time.sleep(2)
            log.debug("Strategy Tester tab opened.")
        except TimeoutException:
            log.warning("Could not find Strategy Tester tab — it may already be open.")

    # ------------------------------------------------------------------
    # Changing strategy inputs
    # ------------------------------------------------------------------

    def set_inputs(self, params: Dict[str, Any]):
        """Open the strategy settings dialog and set all parameter values."""
        self._open_settings_dialog()
        self._navigate_to_inputs_tab()

        for name, value in params.items():
            self._set_input_field(name, value)

        self._click_ok()
        wait_time = self.config.get("backtest_wait", 8)
        log.debug("Waiting %ds for backtest to recalculate…", wait_time)
        time.sleep(wait_time)

    def _open_settings_dialog(self):
        for selector in [_SEL["strategy_settings_gear"], _SEL["strategy_gear_alt"]]:
            try:
                gear = self._wait_for(By.XPATH, selector, timeout=10)
                gear.click()
                time.sleep(1)
                return
            except TimeoutException:
                continue

        # Last resort: find any visible settings gear near the strategy
        try:
            gears = self.driver.find_elements(By.CSS_SELECTOR, "button[data-tooltip='Settings']")
            for g in gears:
                if g.is_displayed():
                    g.click()
                    time.sleep(1)
                    return
        except Exception:
            pass

        raise RuntimeError("Could not find the strategy Settings button.")

    def _navigate_to_inputs_tab(self):
        try:
            tab = self._wait_for(By.XPATH, _SEL["inputs_tab"], timeout=8)
            tab.click()
            time.sleep(0.5)
        except TimeoutException:
            log.debug("Inputs tab click skipped (may already be active).")

    def _set_input_field(self, label: str, value: Any):
        """Find the input field by its label text and update its value."""
        # Build XPath: find the row containing the label, then the input inside it
        xpath = (
            f"//div[contains(@class,'input-wrapper') or contains(@class,'cell-title')]"
            f"[.//label[normalize-space()='{label}'] or "
            f".//span[normalize-space()='{label}']]"
            f"//following-sibling::div//input | "
            # Alternative structure
            f"//tr[.//td[normalize-space()='{label}']]//input | "
            f"//div[@class and .//div[normalize-space()='{label}']]//input[@type='text' or @type='number']"
        )
        try:
            inputs = self.driver.find_elements(By.XPATH, xpath)
            if not inputs:
                # Broader fallback
                inputs = self._find_input_by_label_proximity(label)

            if not inputs:
                log.warning("Input field for '%s' not found — skipping.", label)
                return

            inp = inputs[0]
            self.driver.execute_script("arguments[0].scrollIntoView(true);", inp)
            time.sleep(0.1)
            inp.click()
            inp.send_keys(Keys.CONTROL + "a")
            inp.send_keys(str(value))
            inp.send_keys(Keys.TAB)
            log.debug("Set '%s' = %s", label, value)
        except (StaleElementReferenceException, Exception) as e:
            log.warning("Failed to set input '%s': %s", label, e)

    def _find_input_by_label_proximity(self, label: str):
        """Scan all visible labels and return the sibling/nearby input."""
        all_labels = self.driver.find_elements(
            By.XPATH,
            f"//label[normalize-space()='{label}'] | //span[normalize-space()='{label}']"
        )
        for lbl in all_labels:
            try:
                # Try parent row's input
                row = lbl.find_element(By.XPATH, "./ancestor::tr[1] | ./ancestor::div[@class][1]")
                inputs = row.find_elements(By.TAG_NAME, "input")
                if inputs:
                    return inputs
            except Exception:
                continue
        return []

    def _click_ok(self):
        ok_xpaths = [
            "//button[normalize-space()='OK']",
            "//button[normalize-space()='Apply']",
            "//button[contains(@class,'ok') or contains(@class,'apply')]",
        ]
        for xpath in ok_xpaths:
            try:
                btn = self._wait_for(By.XPATH, xpath, timeout=5)
                btn.click()
                time.sleep(0.5)
                return
            except TimeoutException:
                continue
        log.warning("OK/Apply button not found — dialog may have auto-closed.")

    # ------------------------------------------------------------------
    # Reading backtest metrics
    # ------------------------------------------------------------------

    def read_metrics(self) -> BacktestMetrics:
        """Extract performance metrics from the Strategy Tester overview panel."""
        metrics = BacktestMetrics()

        # Try the structured overview table approach
        try:
            overview = self._wait_for(
                By.XPATH,
                "//div[contains(@class,'report-overview') or contains(@class,'performance')]",
                timeout=10,
            )
            text = overview.text
            metrics = self._parse_overview_text(text)
        except TimeoutException:
            log.warning("Overview panel not found; attempting row-by-row extraction.")
            metrics = self._extract_metrics_row_by_row()

        return metrics

    def _parse_overview_text(self, text: str) -> BacktestMetrics:
        """Parse raw text dumped from the overview panel."""
        m = BacktestMetrics()
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        def after(label: str) -> Optional[str]:
            for i, line in enumerate(lines):
                if label.lower() in line.lower():
                    # Value is usually on next line or same line after label
                    rest = line[line.lower().index(label.lower()) + len(label):].strip()
                    if rest:
                        return rest
                    if i + 1 < len(lines):
                        return lines[i + 1]
            return None

        m.net_profit = _parse_number(after("Net Profit") or "")
        m.profit_factor = _parse_number(after("Profit Factor") or "")
        m.percent_profitable = _parse_number(after("Percent Profitable") or "")
        m.total_trades = int(_parse_number(after("Total Closed Trades") or "") or 0) or None
        m.max_drawdown = _parse_number(after("Max Drawdown") or "")
        m.sharpe_ratio = _parse_number(after("Sharpe Ratio") or "")
        m.sortino_ratio = _parse_number(after("Sortino Ratio") or "")
        m.calmar_ratio = _parse_number(after("Calmar Ratio") or "")
        m.avg_trade = _parse_number(after("Avg Trade") or "")
        m.avg_win = _parse_number(after("Avg Win") or "")
        m.avg_loss = _parse_number(after("Avg Loss") or "")

        if m.avg_win and m.avg_loss and m.avg_loss != 0:
            m.win_loss_ratio = abs(m.avg_win / m.avg_loss)

        return m

    def _extract_metrics_row_by_row(self) -> BacktestMetrics:
        """Fallback: find specific elements by class/aria patterns."""
        m = BacktestMetrics()

        def _get(xpath: str) -> Optional[float]:
            try:
                el = self.driver.find_element(By.XPATH, xpath)
                return _parse_number(el.text)
            except NoSuchElementException:
                return None

        # These selectors target TradingView's strategy tester DOM
        base = "//div[contains(@class,'report-overview-item')]"
        m.net_profit = _get(f"{base}[.//span[text()='Net Profit']]//span[2]")
        m.profit_factor = _get(f"{base}[.//span[text()='Profit Factor']]//span[2]")
        m.percent_profitable = _get(f"{base}[.//span[text()='Percent Profitable']]//span[2]")
        m.max_drawdown = _get(f"{base}[.//span[contains(text(),'Max Drawdown')]]//span[2]")
        m.sharpe_ratio = _get(f"{base}[.//span[text()='Sharpe Ratio']]//span[2]")

        return m

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _wait_for(self, by: str, selector: str, timeout: int = None) -> Any:
        t = timeout or self.config.get("implicit_wait", 10)
        return WebDriverWait(self.driver, t).until(
            EC.element_to_be_clickable((by, selector))
        )

    def _fill_input(self, by: str, selector: str, value: str):
        el = self._wait_for(by, selector)
        el.clear()
        el.send_keys(value)
        time.sleep(0.3)

    def take_screenshot(self, path: str):
        if self.driver:
            self.driver.save_screenshot(path)
