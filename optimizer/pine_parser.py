"""
Parse a PineScript (.pine / .txt) source file and extract all input.*() declarations.

Supports Pine v5 style:
    fast = input.int(12, "Fast Length", minval=1, maxval=200, step=1)
    mult = input.float(1.5, "ATR Mult", minval=0.1, step=0.1)
    show = input.bool(true, "Show Signals")
    src  = input.string("EMA", "MA Type", options=["EMA","SMA","WMA"])

And the legacy v3/v4 style:
    length = input(14, title="RSI Length", type=input.integer, minval=2, maxval=50)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# Positional argument order for each input type (Pine v5)
_POSITIONAL = {
    "int":       ["defval", "title", "minval", "maxval", "step", "group", "tooltip"],
    "float":     ["defval", "title", "minval", "maxval", "step", "group", "tooltip"],
    "bool":      ["defval", "title", "group", "tooltip"],
    "string":    ["defval", "title", "options", "group", "tooltip"],
    "timeframe": ["defval", "title", "options", "group", "tooltip"],
    # legacy v3/v4 input()
    "legacy":    ["defval", "title", "type", "minval", "maxval", "step", "group", "tooltip"],
}

# Types skipped entirely (not optimizable as numbers/categories)
_SKIP_TYPES = {"color", "source", "price", "symbol", "session", "text_area"}


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        return s[1:-1]
    return s


def _try_float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    try:
        return float(s.strip())
    except (ValueError, TypeError):
        return None


def _label_to_name(label: str) -> str:
    name = label.lower()
    name = re.sub(r"[%$#@!]", "pct", name)
    name = re.sub(r"[^a-z0-9_\s]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "param"


def _split_args(args_str: str) -> List[str]:
    """Split by comma, honouring string literals, parentheses, and brackets."""
    parts: List[str] = []
    depth = 0
    in_str = False
    str_ch = ""
    cur: List[str] = []

    for ch in args_str:
        if in_str:
            cur.append(ch)
            if ch == str_ch:
                in_str = False
        elif ch in ('"', "'"):
            in_str = True
            str_ch = ch
            cur.append(ch)
        elif ch in ("(", "[", "{"):
            depth += 1
            cur.append(ch)
        elif ch in (")", "]", "}"):
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)

    if cur:
        parts.append("".join(cur))

    return parts


def _parse_options_array(raw: str) -> List[str]:
    """Parse Pine array literal like ["EMA", "SMA", "WMA"] into a Python list."""
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [_strip_quotes(o) for o in _split_args(raw) if _strip_quotes(o)]


def _find_input_calls(source: str) -> List[Tuple[Optional[str], str, str]]:
    """
    Find every input.*() call in source.
    Returns (var_name | None, input_type, raw_args_string).
    """
    results = []

    # Pattern matches:  [var_name =] input.TYPE( or just input(
    pattern = re.compile(
        r"(?:(\w+)\s*=\s*)?"                              # optional: var_name =
        r"input(?:\.(int|float|bool|string|timeframe|color|source|price|symbol|session|text_area))?"
        r"\s*\(",
        re.MULTILINE,
    )

    for m in pattern.finditer(source):
        var_name   = m.group(1)
        input_type = m.group(2) or "legacy"  # bare input() → legacy

        # Walk forward from opening paren to find the matching close paren
        start = m.end()
        depth = 1
        pos   = start
        while pos < len(source) and depth > 0:
            ch = source[pos]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            pos += 1

        args_str = source[start : pos - 1]
        results.append((var_name, input_type, args_str))

    return results


def _merge_args(raw_args: List[str], pos_names: List[str]) -> Dict[str, str]:
    """Merge positional + keyword arguments into a single dict."""
    merged: Dict[str, str] = {}
    pos_idx = 0

    for raw in raw_args:
        raw = raw.strip()
        # Keyword argument: key = value  (key must be a bare identifier)
        kw = re.match(r"^([a-zA-Z_]\w*)\s*=\s*(.+)$", raw, re.DOTALL)
        if kw:
            merged[kw.group(1).strip()] = kw.group(2).strip()
        else:
            if pos_idx < len(pos_names):
                merged[pos_names[pos_idx]] = raw
            pos_idx += 1

    return merged


class PineScriptParser:
    """Parse .pine / .txt source and return optimizer-ready parameter dicts."""

    def parse_file(self, path: str) -> List[Dict]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        return self.parse_source(source)

    def parse_source(self, source: str) -> List[Dict]:
        results: List[Dict] = []
        seen: set = set()

        for var_name, input_type, args_str in _find_input_calls(source):
            if input_type in _SKIP_TYPES:
                continue

            raw_args  = _split_args(args_str)
            pos_names = _POSITIONAL.get(input_type, _POSITIONAL["legacy"])
            merged    = _merge_args(raw_args, pos_names)

            # Handle legacy type= keyword mapping
            if input_type == "legacy":
                tv = merged.get("type", "")
                if "integer" in tv or "int" in tv:
                    input_type = "int"
                elif "float" in tv:
                    input_type = "float"
                elif "bool" in tv:
                    input_type = "bool"
                elif "string" in tv:
                    input_type = "string"
                else:
                    input_type = "int"  # sensible default

            label = _strip_quotes(merged.get("title", ""))
            if not label:
                label = var_name.replace("_", " ").title() if var_name else ""
            if not label or label in seen:
                continue
            seen.add(label)

            name = var_name if var_name else _label_to_name(label)

            param = self._build_param(input_type, label, name, merged)
            if param:
                results.append(param)

        return results

    # ── Type builders ──────────────────────────────────────────────────

    def _build_param(self, input_type: str, label: str,
                     name: str, m: Dict[str, str]) -> Optional[Dict]:
        if input_type == "int":
            return self._build_int(label, name, m)
        if input_type == "float":
            return self._build_float(label, name, m)
        if input_type == "bool":
            return self._build_bool(label, name, m)
        if input_type in ("string", "timeframe"):
            return self._build_categorical(label, name, m)
        return None

    def _build_int(self, label: str, name: str, m: Dict) -> Dict:
        defval = int(_try_float(m.get("defval", "1")) or 1)
        minval = _try_float(m.get("minval"))
        maxval = _try_float(m.get("maxval"))
        step   = int(_try_float(m.get("step", "1")) or 1)

        start = int(minval) if minval is not None else max(1, defval // 4)
        stop  = int(maxval) if maxval is not None else max(defval * 4, defval + 20)
        step  = max(1, step)

        return {"type": "Int", "label": label, "name": name,
                "current": str(defval), "start": start, "stop": stop, "step": step,
                "_has_bounds": minval is not None or maxval is not None}

    def _build_float(self, label: str, name: str, m: Dict) -> Dict:
        defval = _try_float(m.get("defval", "1.0")) or 1.0
        minval = _try_float(m.get("minval"))
        maxval = _try_float(m.get("maxval"))
        step   = _try_float(m.get("step", "0.1")) or 0.1

        start = round(minval, 6) if minval is not None else round(max(0.01, defval * 0.1), 6)
        stop  = round(maxval, 6) if maxval is not None else round(defval * 4.0, 6)
        step  = round(abs(step), 6)

        return {"type": "Float", "label": label, "name": name,
                "current": str(defval), "start": start, "stop": stop, "step": step,
                "_has_bounds": minval is not None or maxval is not None}

    def _build_bool(self, label: str, name: str, m: Dict) -> Dict:
        defval = m.get("defval", "true").strip().lower()
        return {"type": "Bool", "label": label, "name": name,
                "current": defval, "options": ["true", "false"],
                "_has_bounds": True}

    def _build_categorical(self, label: str, name: str, m: Dict) -> Optional[Dict]:
        opts_raw = m.get("options", "")
        options  = _parse_options_array(opts_raw)
        defval   = _strip_quotes(m.get("defval", ""))

        if not options and defval:
            options = [defval]
        if not options:
            return None

        return {"type": "Categorical", "label": label, "name": name,
                "current": defval or options[0], "options": options,
                "_has_bounds": True}
