"""Selenium-based automation layer for TradingView Strategy Tester."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

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


def _label_to_name(label: str) -> str:
    """Convert a human-readable TV label into a valid Python identifier."""
    name = label.lower()
    name = re.sub(r"[%$#@!]", "pct", name)
    name = re.sub(r"[^a-z0-9_\s]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "param"


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
        username  = self.config.get("username")  or os.getenv("TV_USERNAME", "")
        password  = self.config.get("password")  or os.getenv("TV_PASSWORD", "")
        chart_url = self.config.get("chart_url") or os.getenv("TV_CHART_URL", "")

        if not chart_url:
            raise RuntimeError(
                "Chart URL not set. Paste your TradingView chart URL in the Settings sidebar."
            )

        manual = self.config.get("manual_login", False)

        if manual:
            # ── Manual login mode ────────────────────────────────────────
            # Open the signin page and wait up to 3 minutes for the user
            # to log in themselves, then take over.
            log.info("Manual login mode — waiting for you to sign in to TradingView…")
            self.driver.get("https://www.tradingview.com/accounts/signin/")
            print("\n" + "="*60)
            print("  ACTION REQUIRED")
            print("  Please log in to TradingView in the Chrome window.")
            print("  You have 3 minutes.")
            print("="*60 + "\n")
            # Wait until we leave the signin page (up to 180s)
            for _ in range(180):
                time.sleep(1)
                if "accounts/signin" not in self.driver.current_url:
                    break
            else:
                raise RuntimeError("Timed out waiting for manual login (3 minutes).")
        else:
            # ── Automated login ──────────────────────────────────────────
            if not username or not password:
                raise RuntimeError(
                    "Credentials not set. Enter username and password in the sidebar,\n"
                    "or enable Manual Login mode."
                )
            log.info("Navigating to TradingView sign-in page…")
            self.driver.get("https://www.tradingview.com/accounts/signin/")
            time.sleep(3)

            self._click_email_option()
            time.sleep(2)

            if not self._fill_credential_field(["username", "email"], username):
                self.take_screenshot("login_debug.png")
                raise RuntimeError(
                    "Could not fill the username/email field.\n"
                    "Screenshot saved as login_debug.png — send it for debugging,\n"
                    "or enable Manual Login mode in the sidebar."
                )

            self._click_continue_if_present()

            if not self._fill_credential_field(["password"], password):
                self.take_screenshot("login_debug.png")
                raise RuntimeError(
                    "Could not fill the password field.\n"
                    "Screenshot saved as login_debug.png."
                )

            self._submit_login()
            time.sleep(4)

            if "accounts/signin" in self.driver.current_url:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "captcha" in page_text or "robot" in page_text:
                    raise RuntimeError(
                        "TradingView is showing a CAPTCHA.\n"
                        "Enable Manual Login mode in the sidebar to complete it yourself."
                    )
                raise RuntimeError(
                    "Login failed — check your TradingView username and password."
                )

        log.info("Login successful. Loading chart: %s", chart_url)
        self.driver.get(chart_url)
        time.sleep(5)
        self._open_strategy_tester()
        self._logged_in = True
        log.info("Chart loaded.")

    def _click_email_option(self):
        """Click whichever 'continue with email' button TradingView is showing."""
        candidates = [
            (By.XPATH, "//button[.//span[normalize-space()='Email']]"),
            (By.XPATH, "//button[normalize-space()='Email']"),
            (By.XPATH, "//*[contains(normalize-space(),'Continue with email')]"),
            (By.XPATH, "//*[contains(normalize-space(),'Sign in with email')]"),
            (By.XPATH, "//*[contains(normalize-space(),'Sign in with Email')]"),
            (By.XPATH, "//a[contains(normalize-space(),'Email')]"),
            (By.XPATH, "//span[normalize-space()='Email']"),
            (By.XPATH, "//*[contains(@class,'email') and (self::button or self::a)]"),
        ]
        for by, sel in candidates:
            try:
                el = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((by, sel))
                )
                # Use JS click — more reliable on React/SPA pages
                self.driver.execute_script("arguments[0].click();", el)
                time.sleep(1.5)
                log.debug("Clicked email option via: %s", sel)
                return
            except (TimeoutException, NoSuchElementException):
                continue
        log.debug("No 'Email' option found — assuming already on the email form.")

    def _fill_credential_field(self, field_names: list, value: str) -> bool:
        """
        Find a visible input whose name/type/autocomplete matches any of field_names
        and fill it using JS (triggers React state) + send_keys (ensures browser value).
        """
        selectors = []
        for f in field_names:
            selectors += [
                (By.CSS_SELECTOR, f"input[name='{f}']"),
                (By.CSS_SELECTOR, f"input[autocomplete='{f}']"),
                (By.CSS_SELECTOR, f"input[type='{f}']"),
                (By.XPATH,        f"//input[@name='{f}' or @autocomplete='{f}' or @type='{f}']"),
            ]

        for by, sel in selectors:
            try:
                els = self.driver.find_elements(by, sel)
                for el in els:
                    if not el.is_displayed():
                        continue
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", el)
                    time.sleep(0.15)
                    # JS native value setter — works with React controlled inputs
                    self.driver.execute_script("""
                        var el = arguments[0], val = arguments[1];
                        var setter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value').set;
                        setter.call(el, val);
                        el.dispatchEvent(new Event('input',  {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        el.dispatchEvent(new Event('blur',   {bubbles: true}));
                    """, el, value)
                    time.sleep(0.2)
                    # send_keys as belt-and-braces — click first so focus is right
                    el.click()
                    el.send_keys(Keys.CONTROL + "a")
                    el.send_keys(value)
                    time.sleep(0.2)
                    if el.get_attribute("value"):
                        log.debug("Filled field %s via %s", field_names, sel)
                        return True
            except Exception:
                continue
        return False

    def _click_continue_if_present(self):
        """Click a Continue / Next button if TradingView uses a two-step email flow."""
        candidates = [
            (By.XPATH, "//button[normalize-space()='Continue']"),
            (By.XPATH, "//button[normalize-space()='Next']"),
            (By.XPATH, "//button[contains(normalize-space(),'Continue')]"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]
        # Only click if the password field is NOT already visible
        try:
            pwd = self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            if any(p.is_displayed() for p in pwd):
                return  # already on the password step
        except Exception:
            pass

        for by, sel in candidates:
            try:
                el = WebDriverWait(self.driver, 4).until(
                    EC.element_to_be_clickable((by, sel))
                )
                self.driver.execute_script("arguments[0].click();", el)
                time.sleep(1.5)
                log.debug("Clicked Continue/Next button.")
                return
            except (TimeoutException, NoSuchElementException):
                continue

    def _submit_login(self):
        """Click the submit / Sign in button."""
        candidates = [
            (By.XPATH, "//button[@type='submit']"),
            (By.XPATH, "//button[normalize-space()='Sign in']"),
            (By.XPATH, "//button[contains(normalize-space(),'Sign in')]"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]
        for by, sel in candidates:
            try:
                el = WebDriverWait(self.driver, 6).until(
                    EC.element_to_be_clickable((by, sel))
                )
                el.click()
                log.debug("Submitted login via: %s", sel)
                return
            except (TimeoutException, NoSuchElementException):
                continue
        log.warning("Could not find submit button — trying Enter key.")
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.RETURN)
        except Exception:
            pass

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
    # Auto-detect strategy inputs
    # ------------------------------------------------------------------

    def detect_inputs(self) -> List[Dict]:
        """
        Open the strategy Settings → Inputs dialog, read every editable parameter,
        and return a list of dicts ready to populate the optimizer UI.

        Each dict has keys:
          type        "Int" | "Float" | "Categorical" | "Bool"
          label       exact TV label text
          name        auto-generated Python identifier
          current     current value as string
          start/stop/step   (Int and Float only)
          options     (Categorical only)
        """
        self._open_settings_dialog()
        self._navigate_to_inputs_tab()
        time.sleep(1.5)  # let React finish rendering

        try:
            detected = self._scrape_inputs_dialog()
        finally:
            self._dismiss_dialog()

        log.info("Detected %d inputs from strategy.", len(detected))
        return detected

    def _scrape_inputs_dialog(self) -> List[Dict]:
        detected: List[Dict] = []
        seen: set = set()

        # ── Number inputs (input.int / input.float) ─────────────────────
        for inp in self.driver.find_elements(By.CSS_SELECTOR, "input[type='number']"):
            if not inp.is_displayed():
                continue
            label = self._label_for_element(inp)
            if not label or label in seen:
                continue
            seen.add(label)

            raw_val  = inp.get_attribute("value") or "0"
            raw_min  = inp.get_attribute("min")
            raw_max  = inp.get_attribute("max")
            raw_step = inp.get_attribute("step") or "1"

            try:
                step_f   = float(raw_step)
                is_float = (step_f != round(step_f)) or ("." in raw_step and raw_step != "1.0")
            except ValueError:
                step_f, is_float = 1.0, False

            if is_float:
                try:
                    cur = float(raw_val)
                    mn  = float(raw_min) if raw_min not in (None, "", "null") else round(max(0.01, cur * 0.1), 4)
                    mx  = float(raw_max) if raw_max not in (None, "", "null") else round(cur * 4.0, 4)
                    detected.append({"type": "Float", "label": label, "name": _label_to_name(label),
                                     "current": raw_val,
                                     "start": round(mn, 4), "stop": round(mx, 4),
                                     "step": round(step_f, 4)})
                except (ValueError, TypeError):
                    detected.append({"type": "Float", "label": label, "name": _label_to_name(label),
                                     "current": raw_val, "start": 0.1, "stop": 10.0, "step": 0.1})
            else:
                try:
                    cur  = int(float(raw_val))
                    mn   = int(float(raw_min)) if raw_min not in (None, "", "null") else max(1, cur // 4)
                    mx   = int(float(raw_max)) if raw_max not in (None, "", "null") else max(cur * 4, cur + 20)
                    step = max(1, int(step_f))
                    detected.append({"type": "Int", "label": label, "name": _label_to_name(label),
                                     "current": str(cur),
                                     "start": mn, "stop": mx, "step": step})
                except (ValueError, TypeError):
                    detected.append({"type": "Int", "label": label, "name": _label_to_name(label),
                                     "current": raw_val, "start": 1, "stop": 100, "step": 1})

        # ── Checkbox inputs (input.bool) ─────────────────────────────────
        for inp in self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
            if not inp.is_displayed():
                continue
            label = self._label_for_element(inp)
            if not label or label in seen:
                continue
            seen.add(label)
            checked = inp.get_attribute("checked") or inp.get_attribute("aria-checked") or "false"
            detected.append({"type": "Bool", "label": label, "name": _label_to_name(label),
                             "current": "true" if checked in ("true", "1") else "false",
                             "options": ["true", "false"]})

        # ── Dropdown inputs (input.string with options) ───────────────────
        # TradingView uses custom dropdown components; also check native <select>
        for sel_css in ["select",
                        "[data-role='listbox']",
                        "[class*='dropdown'][class*='control']",
                        "[class*='select-control']"]:
            for el in self.driver.find_elements(By.CSS_SELECTOR, sel_css):
                if not el.is_displayed():
                    continue
                label = self._label_for_element(el)
                if not label or label in seen:
                    continue
                opts = self._read_dropdown_options(el)
                if not opts:
                    continue
                seen.add(label)
                detected.append({"type": "Categorical", "label": label,
                                 "name": _label_to_name(label),
                                 "current": opts[0], "options": opts})

        return detected

    def _label_for_element(self, element) -> Optional[str]:
        """Find the human-readable label associated with a form element."""
        # 1. aria-label / title / placeholder on the element
        for attr in ("aria-label", "title"):
            v = element.get_attribute(attr)
            if v and 2 <= len(v.strip()) <= 80:
                return v.strip()

        # 2. <label for="id">
        el_id = element.get_attribute("id")
        if el_id:
            try:
                lbl = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{el_id}']")
                txt = lbl.text.strip()
                if txt:
                    return txt
            except NoSuchElementException:
                pass

        # 3. Walk up 1-5 ancestor levels; find short non-numeric text sibling
        for depth in range(1, 6):
            try:
                ancestor = element.find_element(By.XPATH, f"./ancestor::*[{depth}]")
            except Exception:
                break
            for tag in ("label", "span", "div", "td"):
                try:
                    for c in ancestor.find_elements(By.TAG_NAME, tag):
                        if not c.is_displayed():
                            continue
                        txt = c.text.strip()
                        cur_val = element.get_attribute("value") or ""
                        if (2 <= len(txt) <= 60
                                and txt != cur_val
                                and not txt.replace(".", "").replace("-", "").isdigit()):
                            return txt
                except StaleElementReferenceException:
                    break
                except Exception:
                    continue
            # Stop climbing past a table row or list item boundary
            try:
                if ancestor.tag_name in ("tr", "li"):
                    break
            except Exception:
                break

        return None

    def _read_dropdown_options(self, element) -> List[str]:
        """Extract option strings from a native <select> or TradingView custom dropdown."""
        if element.tag_name == "select":
            return [o.text.strip()
                    for o in element.find_elements(By.TAG_NAME, "option")
                    if o.text.strip()]
        # Custom dropdown: click to open, scrape items, close
        options: List[str] = []
        try:
            element.click()
            time.sleep(0.4)
            for xpath in [
                "//div[contains(@class,'option') and not(contains(@class,'disabled'))]",
                "//li[contains(@class,'item') and not(contains(@class,'disabled'))]",
            ]:
                items = self.driver.find_elements(By.XPATH, xpath)
                for item in items[:60]:
                    txt = item.text.strip()
                    if txt:
                        options.append(txt)
                if options:
                    break
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.3)
        except Exception:
            pass
        return list(dict.fromkeys(options))

    def _dismiss_dialog(self):
        """Close the Settings dialog without applying any changes."""
        for xpath in ["//button[normalize-space()='Cancel']",
                      "//button[normalize-space()='Close']",
                      "//button[@aria-label='Close']",
                      "//button[@data-name='close']"]:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(0.5)
                    return
            except NoSuchElementException:
                continue
        try:
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass

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
