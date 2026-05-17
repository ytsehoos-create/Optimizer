#!/usr/bin/env python3
"""
PineScript Strategy Optimizer — Mac Desktop UI
Run with:  python app.py
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import json
import os
import importlib.util
import webbrowser
from datetime import datetime
from typing import Optional, List, Dict, Any

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ALGORITHMS  = ["random", "grid", "genetic", "bayesian"]
METRICS     = ["net_profit", "profit_factor", "percent_profitable",
               "sharpe_ratio", "sortino_ratio", "calmar_ratio",
               "max_drawdown", "composite"]
PARAM_TYPES = ["Int", "Float", "Categorical"]
CONFIG_FILE = "ui_config.json"
_MONO       = ("Menlo", 12)
_MONO_SM    = ("Menlo", 11)


def _apply_tree_style(name: str):
    s = ttk.Style()
    s.theme_use("clam")
    s.configure(f"{name}.Treeview",
                background="#161b22", foreground="#c9d1d9",
                fieldbackground="#161b22", rowheight=28, font=_MONO)
    s.configure(f"{name}.Treeview.Heading",
                background="#21262d", foreground="#58a6ff",
                relief="flat", font=(*_MONO_SM[:1], _MONO_SM[1], "bold"))
    s.map(f"{name}.Treeview", background=[("selected", "#1f6feb")])


# ── Add / Edit Parameter Dialog ────────────────────────────────────────────

class ParamDialog(ctk.CTkToplevel):
    """Modal dialog for adding or editing one parameter."""

    def __init__(self, parent, existing: Optional[Dict] = None):
        super().__init__(parent)
        self.title("Edit Parameter" if existing else "Add Parameter")
        self.geometry("480x390")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.result: Optional[Dict] = None

        self._start_var: Optional[ctk.StringVar] = None
        self._stop_var:  Optional[ctk.StringVar] = None
        self._step_var:  Optional[ctk.StringVar] = None
        self._opts_var:  Optional[ctk.StringVar] = None

        self._build(existing or {})

    def _build(self, d: Dict):
        p = {"padx": 20, "pady": (8, 0)}

        ctk.CTkLabel(self, text="Type", font=ctk.CTkFont(weight="bold")).pack(**p, anchor="w")
        self.type_var = ctk.StringVar(value=d.get("type", "Int"))
        ctk.CTkSegmentedButton(
            self, values=PARAM_TYPES, variable=self.type_var,
            command=lambda _: self._refresh_dynamic({})
        ).pack(padx=20, pady=(4, 0), fill="x")

        ctk.CTkLabel(self, text="Internal name  (no spaces)").pack(**p, anchor="w")
        self.name_var = ctk.StringVar(value=d.get("name", ""))
        ctk.CTkEntry(self, textvariable=self.name_var,
                     placeholder_text="e.g.  fast_length").pack(padx=20, pady=(3, 0), fill="x")

        ctk.CTkLabel(
            self, text="TradingView label  (Settings → Inputs, exact text)"
        ).pack(**p, anchor="w")
        self.label_var = ctk.StringVar(value=d.get("label", ""))
        ctk.CTkEntry(self, textvariable=self.label_var,
                     placeholder_text="e.g.  Fast Length").pack(padx=20, pady=(3, 0), fill="x")

        self._dyn = ctk.CTkFrame(self, fg_color="transparent")
        self._dyn.pack(padx=20, pady=(12, 0), fill="x")
        self._refresh_dynamic(d)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(side="bottom", fill="x", padx=20, pady=16)
        ctk.CTkButton(btns, text="Cancel", fg_color="gray30",
                      command=self.destroy).pack(side="left", expand=True, padx=(0, 6))
        ctk.CTkButton(btns, text="Save",
                      command=self._save).pack(side="right", expand=True, padx=(6, 0))

    def _refresh_dynamic(self, d: Dict):
        for w in self._dyn.winfo_children():
            w.destroy()
        ptype = self.type_var.get()
        if ptype in ("Int", "Float"):
            defaults = (5, 50, 1) if ptype == "Int" else (0.1, 5.0, 0.1)
            self._start_var = ctk.StringVar(value=str(d.get("start", defaults[0])))
            self._stop_var  = ctk.StringVar(value=str(d.get("stop",  defaults[1])))
            self._step_var  = ctk.StringVar(value=str(d.get("step",  defaults[2])))
            for lbl, var in [("Start", self._start_var),
                              ("Stop",  self._stop_var),
                              ("Step",  self._step_var)]:
                row = ctk.CTkFrame(self._dyn, fg_color="transparent")
                row.pack(fill="x", pady=3)
                ctk.CTkLabel(row, text=f"{lbl}:", width=52).pack(side="left")
                ctk.CTkEntry(row, textvariable=var, width=160).pack(side="left")
        else:
            ctk.CTkLabel(self._dyn, text="Options (comma-separated)").pack(anchor="w")
            self._opts_var = ctk.StringVar(
                value=", ".join(str(x) for x in d.get("options", []))
            )
            ctk.CTkEntry(self._dyn, textvariable=self._opts_var,
                         placeholder_text="close, hl2, hlc3").pack(fill="x", pady=(4, 0))

    def _save(self):
        name  = self.name_var.get().strip()
        label = self.label_var.get().strip()
        ptype = self.type_var.get()

        if not name or not label:
            messagebox.showerror("Required", "Name and Label cannot be empty.", parent=self)
            return
        if " " in name:
            messagebox.showerror("Invalid name", "Internal name cannot contain spaces.", parent=self)
            return

        d: Dict[str, Any] = {"type": ptype, "name": name, "label": label}
        try:
            if ptype == "Int":
                d.update(start=int(self._start_var.get()),
                         stop= int(self._stop_var.get()),
                         step= int(self._step_var.get()))
                if d["step"] <= 0:
                    raise ValueError("Step must be > 0")
            elif ptype == "Float":
                d.update(start=float(self._start_var.get()),
                         stop= float(self._stop_var.get()),
                         step= float(self._step_var.get()))
                if d["step"] <= 0:
                    raise ValueError("Step must be > 0")
            else:
                opts = [o.strip() for o in self._opts_var.get().split(",") if o.strip()]
                if not opts:
                    raise ValueError("Provide at least one option.")
                d["options"] = opts
        except ValueError as e:
            messagebox.showerror("Validation error", str(e), parent=self)
            return

        self.result = d
        self.destroy()


# ── Main App ───────────────────────────────────────────────────────────────

class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("PineScript Strategy Optimizer")
        self.geometry("1180x780")
        self.minsize(960, 640)

        self.parameters: List[Dict]          = []
        self._result_q: queue.Queue          = queue.Queue()
        self._stop_event: threading.Event    = threading.Event()
        self._running                        = False
        self._trial_count                    = 0
        self._start_time: Optional[datetime] = None
        self._last_html: Optional[str]       = None

        _apply_tree_style("Param")
        _apply_tree_style("Result")

        self._build_ui()
        self._load_config()
        self._poll_queue()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self._build_sidebar()
        self._build_main()
        self._build_statusbar()

    # ── Sidebar ─────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sb = ctk.CTkScrollableFrame(self, width=262, corner_radius=0, label_text="")
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_columnconfigure(0, weight=1)

        def section(text):
            ctk.CTkLabel(sb, text=text, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#58a6ff").pack(padx=16, pady=(14, 2), anchor="w")

        def labeled_entry(parent, text, var, show=None, placeholder=""):
            ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11)).pack(
                padx=16, pady=(4, 0), anchor="w")
            kw: Dict[str, Any] = {"textvariable": var, "placeholder_text": placeholder}
            if show:
                kw["show"] = show
            ctk.CTkEntry(parent, **kw).pack(padx=16, pady=(2, 0), fill="x")

        ctk.CTkLabel(sb, text="⚙  Settings",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 4), padx=16, anchor="w")

        section("TradingView")
        self._url_var  = ctk.StringVar()
        self._user_var = ctk.StringVar()
        self._pass_var = ctk.StringVar()
        labeled_entry(sb, "Chart URL", self._url_var,
                      placeholder="https://www.tradingview.com/chart/…")
        labeled_entry(sb, "Username / Email", self._user_var,
                      placeholder="username or email")
        labeled_entry(sb, "Password", self._pass_var, show="●",
                      placeholder="password")

        self._headless_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sb, text="Headless browser (no window)",
                        variable=self._headless_var).pack(padx=16, pady=(8, 0), anchor="w")

        section("Optimization")
        ctk.CTkLabel(sb, text="Algorithm", font=ctk.CTkFont(size=11)).pack(
            padx=16, pady=(4, 0), anchor="w")
        self._algo_var = ctk.StringVar(value="random")
        ctk.CTkOptionMenu(sb, values=ALGORITHMS,
                          variable=self._algo_var).pack(padx=16, pady=(2, 0), fill="x")

        ctk.CTkLabel(sb, text="Metric", font=ctk.CTkFont(size=11)).pack(
            padx=16, pady=(8, 0), anchor="w")
        self._metric_var = ctk.StringVar(value="net_profit")
        ctk.CTkOptionMenu(sb, values=METRICS,
                          variable=self._metric_var).pack(padx=16, pady=(2, 0), fill="x")

        self._maximize_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(sb, text="Maximize metric",
                        variable=self._maximize_var).pack(padx=16, pady=(8, 0), anchor="w")

        labeled_entry(sb, "Random trials", (self._trials_var := ctk.StringVar(value="100")),
                      placeholder="100")
        labeled_entry(sb, "Backtest wait (seconds)", (self._wait_var := ctk.StringVar(value="8")),
                      placeholder="8")

        section("Genetic Algorithm")
        labeled_entry(sb, "Population size", (self._pop_var := ctk.StringVar(value="30")),
                      placeholder="30")
        labeled_entry(sb, "Generations", (self._gen_var := ctk.StringVar(value="20")),
                      placeholder="20")

        btns = ctk.CTkFrame(sb, fg_color="transparent")
        btns.pack(padx=16, pady=16, fill="x")
        ctk.CTkButton(btns, text="Save Config", command=self._save_config).pack(
            side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(btns, text="Load Config", fg_color="gray30",
                      command=self._load_config_dialog).pack(side="right", expand=True, padx=(4, 0))

    # ── Main (tabbed) ────────────────────────────────────────────────────

    def _build_main(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        tabs = ctk.CTkTabview(frame)
        tabs.pack(fill="both", expand=True, padx=8, pady=8)
        tabs.add("Parameters")
        tabs.add("Run & Results")

        self._build_params_tab(tabs.tab("Parameters"))
        self._build_run_tab(tabs.tab("Run & Results"))

    # ── Parameters tab ───────────────────────────────────────────────────

    def _build_params_tab(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(parent, fg_color="transparent")
        tb.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        ctk.CTkButton(tb, text="+ Add",  width=80,
                      command=self._add_param).pack(side="left", padx=(0, 4))
        ctk.CTkButton(tb, text="✎ Edit", width=80, fg_color="gray30",
                      command=self._edit_param).pack(side="left", padx=4)
        ctk.CTkButton(tb, text="✕ Remove", width=90, fg_color="gray30",
                      command=self._remove_param).pack(side="left", padx=4)
        ctk.CTkButton(tb, text="↑", width=38, fg_color="gray30",
                      command=lambda: self._move_param(-1)).pack(side="left", padx=2)
        ctk.CTkButton(tb, text="↓", width=38, fg_color="gray30",
                      command=lambda: self._move_param(1)).pack(side="left", padx=2)
        ctk.CTkButton(tb, text="Load Strategy File (.py)", fg_color="#21262d",
                      border_color="#30363d", border_width=1,
                      command=self._load_strategy_file).pack(side="right")

        # Tree
        frm = ctk.CTkFrame(parent)
        frm.grid(row=1, column=0, sticky="nsew")
        frm.grid_rowconfigure(0, weight=1)
        frm.grid_columnconfigure(0, weight=1)

        cols = ("name", "label", "type", "range")
        self._param_tree = ttk.Treeview(frm, columns=cols, show="headings",
                                        style="Param.Treeview", selectmode="browse")
        for col, hdr, w in [("name",  "Internal Name",       180),
                             ("label", "TradingView Label",   230),
                             ("type",  "Type",                100),
                             ("range", "Range / Options",     320)]:
            self._param_tree.heading(col, text=hdr)
            self._param_tree.column(col, width=w, anchor="w")

        vsb = ttk.Scrollbar(frm, orient="vertical", command=self._param_tree.yview)
        self._param_tree.configure(yscrollcommand=vsb.set)
        self._param_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self._param_tree.bind("<Double-1>", lambda _: self._edit_param())

        # Combo count
        self._combo_lbl = ctk.CTkLabel(parent, text="", font=ctk.CTkFont(size=11),
                                        text_color="#8b949e")
        self._combo_lbl.grid(row=2, column=0, sticky="w", pady=(4, 0))

    # ── Run & Results tab ────────────────────────────────────────────────

    def _build_run_tab(self, parent):
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Control row
        ctrl = ctk.CTkFrame(parent, fg_color="transparent")
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self._run_btn = ctk.CTkButton(
            ctrl, text="▶  Run Optimization", width=190, height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._toggle_run)
        self._run_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(ctrl, text="Dry Run", fg_color="gray30", height=42,
                      command=self._dry_run).pack(side="left", padx=4)

        self._report_btn = ctk.CTkButton(
            ctrl, text="Open HTML Report", fg_color="gray30", height=42,
            state="disabled", command=self._open_report)
        self._report_btn.pack(side="right")

        # Progress
        prog = ctk.CTkFrame(parent)
        prog.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        prog.grid_columnconfigure(1, weight=1)

        self._prog_lbl = ctk.CTkLabel(prog, text="Ready", width=130,
                                       font=ctk.CTkFont(size=11))
        self._prog_lbl.grid(row=0, column=0, padx=10, pady=8)
        self._prog_bar = ctk.CTkProgressBar(prog)
        self._prog_bar.grid(row=0, column=1, sticky="ew", padx=4)
        self._prog_bar.set(0)
        self._trial_lbl = ctk.CTkLabel(prog, text="0 / 0", width=90,
                                        font=ctk.CTkFont(size=11), text_color="#8b949e")
        self._trial_lbl.grid(row=0, column=2, padx=10)

        # Results container (rebuilt each run to add parameter columns)
        self._results_frame = ctk.CTkFrame(parent)
        self._results_frame.grid(row=2, column=0, sticky="nsew")
        self._result_tree: Optional[ttk.Treeview] = None
        self._result_cols: List[str] = []
        self._build_result_tree([])  # empty initial tree

    def _build_result_tree(self, param_names: List[str]):
        """Destroy and recreate the result treeview with current parameter columns."""
        for w in self._results_frame.winfo_children():
            w.destroy()
        self._results_frame.grid_rowconfigure(0, weight=1)
        self._results_frame.grid_columnconfigure(0, weight=1)

        metric_cols = [
            ("score",               "Score",        78),
            ("net_profit",          "Net Profit%",  100),
            ("profit_factor",       "Prof.Factor",  95),
            ("percent_profitable",  "Win%",         68),
            ("total_trades",        "Trades",       68),
            ("max_drawdown",        "Drawdown%",    92),
            ("sharpe_ratio",        "Sharpe",       74),
        ]
        param_col_specs = [(n, n.replace("_", " ").title(), 88) for n in param_names]
        all_specs = [("rank", "#", 40)] + param_col_specs + metric_cols
        self._result_cols = [s[0] for s in all_specs]

        tree = ttk.Treeview(self._results_frame,
                            columns=self._result_cols, show="headings",
                            style="Result.Treeview", selectmode="browse")
        for col_id, hdr, w in all_specs:
            tree.heading(col_id, text=hdr,
                         command=lambda c=col_id: self._sort_col(c))
            anc = "center" if col_id == "rank" else "e"
            tree.column(col_id, width=w, anchor=anc, minwidth=w)

        vsb = ttk.Scrollbar(self._results_frame, orient="vertical",  command=tree.yview)
        hsb = ttk.Scrollbar(self._results_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._result_tree = tree
        self._sort_asc = True
        self._sort_by  = "rank"

    # ── Status bar ───────────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=26, corner_radius=0, fg_color="#0d1117")
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._status_var = ctk.StringVar(value="Ready")
        ctk.CTkLabel(bar, textvariable=self._status_var,
                     font=ctk.CTkFont(size=11), text_color="#8b949e").pack(side="left", padx=12)
        self._clock_lbl = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(size=11),
                                        text_color="#8b949e")
        self._clock_lbl.pack(side="right", padx=12)
        self._tick_clock()

    def _tick_clock(self):
        self._clock_lbl.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    # ── Parameter management ──────────────────────────────────────────────

    def _add_param(self):
        dlg = ParamDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self.parameters.append(dlg.result)
            self._refresh_param_tree()

    def _edit_param(self):
        sel = self._param_tree.selection()
        if not sel:
            return
        idx = self._param_tree.index(sel[0])
        dlg = ParamDialog(self, existing=self.parameters[idx])
        self.wait_window(dlg)
        if dlg.result:
            self.parameters[idx] = dlg.result
            self._refresh_param_tree()

    def _remove_param(self):
        sel = self._param_tree.selection()
        if not sel:
            return
        idx = self._param_tree.index(sel[0])
        del self.parameters[idx]
        self._refresh_param_tree()

    def _move_param(self, direction: int):
        sel = self._param_tree.selection()
        if not sel:
            return
        idx = self._param_tree.index(sel[0])
        new_idx = idx + direction
        if 0 <= new_idx < len(self.parameters):
            self.parameters[idx], self.parameters[new_idx] = (
                self.parameters[new_idx], self.parameters[idx])
            self._refresh_param_tree()
            kids = self._param_tree.get_children()
            if kids:
                self._param_tree.selection_set(kids[new_idx])

    def _refresh_param_tree(self):
        self._param_tree.delete(*self._param_tree.get_children())
        total = 1
        for p in self.parameters:
            ptype = p["type"]
            if ptype == "Int":
                n = max(1, len(range(p["start"], p["stop"] + 1, max(1, p["step"]))))
                rng = f"{p['start']} → {p['stop']}  step {p['step']}"
            elif ptype == "Float":
                n = max(1, round((p["stop"] - p["start"]) / max(1e-9, p["step"])) + 1)
                rng = f"{p['start']} → {p['stop']}  step {p['step']}"
            else:
                opts = p.get("options", [])
                n   = max(1, len(opts))
                rng = ",  ".join(str(o) for o in opts)
            total *= n
            self._param_tree.insert("", "end",
                                    values=(p["name"], p["label"], ptype, rng))
        self._combo_lbl.configure(text=f"  {total:,} total combinations")

    def _load_strategy_file(self):
        path = filedialog.askopenfilename(
            title="Open Strategy Parameter File",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
            initialdir=os.path.join(os.path.dirname(__file__), "examples"),
        )
        if not path:
            return
        try:
            spec = importlib.util.spec_from_file_location("_strat", path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            space = mod.PARAMETER_SPACE
            self.parameters = []
            for p in space.parameters:
                cls = type(p).__name__
                if cls == "IntParameter":
                    self.parameters.append(
                        {"type": "Int", "name": p.name, "label": p.label,
                         "start": p.start, "stop": p.stop, "step": p.step})
                elif cls == "FloatParameter":
                    self.parameters.append(
                        {"type": "Float", "name": p.name, "label": p.label,
                         "start": p.start, "stop": p.stop, "step": p.step})
                else:
                    self.parameters.append(
                        {"type": "Categorical", "name": p.name, "label": p.label,
                         "options": list(p.options)})
            self._refresh_param_tree()
            self._status("Loaded: " + os.path.basename(path))
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc), parent=self)

    # ── Run / Stop ────────────────────────────────────────────────────────

    def _toggle_run(self):
        if self._running:
            self._stop_event.set()
            self._running = False
            self._run_btn.configure(text="▶  Run Optimization",
                                    fg_color=["#3b8ed0", "#1f6feb"])
            self._status("Stopping…")
        else:
            self._start_run()

    def _start_run(self):
        if not self.parameters:
            messagebox.showwarning("No Parameters",
                                   "Add at least one parameter before running.", parent=self)
            return
        if not self._url_var.get().strip():
            messagebox.showwarning("No Chart URL",
                                   "Enter your TradingView chart URL in the sidebar.",
                                   parent=self)
            return

        # Reset state
        self._running      = True
        self._trial_count  = 0
        self._start_time   = datetime.now()
        self._stop_event.clear()

        self._run_btn.configure(text="⏹  Stop", fg_color="#f85149")
        self._prog_bar.set(0)
        self._prog_lbl.configure(text="Starting…")
        self._trial_lbl.configure(text="0 / ?")
        self._report_btn.configure(state="disabled")

        # Rebuild result table with current parameter columns
        self._build_result_tree([p["name"] for p in self.parameters])

        cfg   = self._build_config()
        space = self._build_space()
        q     = self._result_q
        stop  = self._stop_event

        def run():
            try:
                from optimizer import StrategyOptimizer

                def on_result(result):
                    if stop.is_set():
                        raise InterruptedError("Stopped by user")
                    q.put(("result", result))

                opt = StrategyOptimizer(space=space, config=cfg, on_result=on_result)
                results = opt.run()
                results.rank()
                opt.report(results)
                # Find latest HTML report
                rep_dir   = cfg.get("reporting", {}).get("output_dir", "reports")
                html_list = sorted(
                    [f for f in os.listdir(rep_dir) if f.endswith(".html")], reverse=True
                )
                html_path = os.path.join(rep_dir, html_list[0]) if html_list else None
                q.put(("done", (results, html_path)))
            except InterruptedError:
                q.put(("stopped", None))
            except Exception as exc:
                import traceback
                q.put(("error", traceback.format_exc()))

        threading.Thread(target=run, daemon=True).start()

    def _dry_run(self):
        if not self.parameters:
            messagebox.showwarning("No Parameters", "Add at least one parameter first.",
                                   parent=self)
            return
        space = self._build_space()
        cfg   = self._build_config()
        alg   = cfg["optimization"]["algorithm"]
        n     = self._estimate_total(alg)
        messagebox.showinfo(
            "Dry Run — No TradingView connection",
            f"Algorithm    : {alg}\n"
            f"Metric       : {cfg['optimization']['metric']}\n"
            f"Parameters   : {len(self.parameters)}\n"
            f"Combinations : {space.total_combinations:,}\n"
            f"Trials       : {n:,}\n\n"
            "Everything looks good. Remove --dry-run and fill in your\n"
            "credentials to run the real optimization.",
            parent=self,
        )

    # ── Result queue polling ──────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self._result_q.get_nowait()
                if kind == "result":
                    self._on_result(payload)
                elif kind == "done":
                    self._on_done(*payload)
                elif kind == "stopped":
                    self._on_stopped()
                elif kind == "error":
                    self._on_error(payload)
        except queue.Empty:
            pass
        self.after(350, self._poll_queue)

    def _on_result(self, result):
        self._trial_count += 1
        n     = self._trial_count
        total = self._estimate_total(self._algo_var.get())
        pct   = min(n / total, 1.0) if total else 0
        self._prog_bar.set(pct)
        self._trial_lbl.configure(text=f"{n} / {total or '?'}")
        elapsed = int((datetime.now() - self._start_time).total_seconds())
        self._prog_lbl.configure(text=f"{elapsed}s elapsed")
        self._status(f"Trial {n}  —  score {result.score:.4f}")
        self._insert_row(result, n)

    def _on_done(self, results_collection, html_path: Optional[str]):
        self._running = False
        self._run_btn.configure(text="▶  Run Optimization",
                                fg_color=["#3b8ed0", "#1f6feb"])
        self._prog_bar.set(1.0)
        n       = self._trial_count
        elapsed = int((datetime.now() - self._start_time).total_seconds())
        self._prog_lbl.configure(text=f"Done — {elapsed}s")
        self._trial_lbl.configure(text=f"{n} / {n}")
        self._status(f"Complete — {n} trials in {elapsed}s")
        self._last_html = html_path
        if html_path:
            self._report_btn.configure(state="normal")
        # Rebuild table in ranked order
        self._rebuild_results(results_collection)

    def _on_stopped(self):
        self._running = False
        self._run_btn.configure(text="▶  Run Optimization",
                                fg_color=["#3b8ed0", "#1f6feb"])
        self._prog_lbl.configure(text="Stopped")
        self._status("Stopped by user.")

    def _on_error(self, tb: str):
        self._running = False
        self._run_btn.configure(text="▶  Run Optimization",
                                fg_color=["#3b8ed0", "#1f6feb"])
        self._prog_lbl.configure(text="Error")
        self._status("Error — see dialog")
        messagebox.showerror("Optimizer Error", tb[:1200], parent=self)

    # ── Results table helpers ─────────────────────────────────────────────

    def _fmt(self, val, decimals=2, suffix="") -> str:
        if val is None:
            return "—"
        try:
            return f"{float(val):.{decimals}f}{suffix}"
        except (TypeError, ValueError):
            return str(val)

    def _row_values(self, result, rank: int) -> tuple:
        m   = result.metrics
        row = [rank]
        for p in self.parameters:
            row.append(result.params.get(p["name"], ""))
        row += [
            self._fmt(result.score, 4),
            self._fmt(m.net_profit,         2, "%"),
            self._fmt(m.profit_factor,       3),
            self._fmt(m.percent_profitable,  1, "%"),
            str(m.total_trades or "—"),
            self._fmt(m.max_drawdown,        2, "%"),
            self._fmt(m.sharpe_ratio,        3),
        ]
        return tuple(row)

    def _insert_row(self, result, n: int):
        if self._result_tree is None:
            return
        self._result_tree.insert("", 0, values=self._row_values(result, n))

    def _rebuild_results(self, rc):
        if self._result_tree is None:
            return
        self._result_tree.delete(*self._result_tree.get_children())
        for r in rc.top_n(500):
            self._result_tree.insert("", "end", values=self._row_values(r, r.rank))

    def _sort_col(self, col: str):
        if self._result_tree is None:
            return
        items = [(self._result_tree.set(i, col), i)
                 for i in self._result_tree.get_children()]
        reverse = (self._sort_by == col and self._sort_asc)
        try:
            items.sort(key=lambda x: float(x[0].rstrip("%").replace("—", "nan")),
                       reverse=reverse)
        except ValueError:
            items.sort(key=lambda x: x[0], reverse=reverse)
        for pos, (_, iid) in enumerate(items):
            self._result_tree.move(iid, "", pos)
        self._sort_asc = not reverse
        self._sort_by  = col

    def _open_report(self):
        if self._last_html and os.path.exists(self._last_html):
            webbrowser.open(f"file://{os.path.abspath(self._last_html)}")

    # ── Config helpers ────────────────────────────────────────────────────

    def _build_config(self) -> Dict:
        try:
            from optimizer.config import load_config
            cfg = load_config("config.yaml")
        except Exception:
            cfg = {"tradingview": {}, "optimization": {}, "reporting": {}, "logging": {}}

        tv = cfg.setdefault("tradingview", {})
        tv["chart_url"]    = self._url_var.get().strip()
        tv["username"]     = self._user_var.get().strip()
        tv["password"]     = self._pass_var.get()
        tv["headless"]     = self._headless_var.get()
        try:
            tv["backtest_wait"] = int(self._wait_var.get())
        except ValueError:
            pass

        opt = cfg.setdefault("optimization", {})
        opt["algorithm"] = self._algo_var.get()
        opt["metric"]    = self._metric_var.get()
        opt["maximize"]  = self._maximize_var.get()
        try:
            opt.setdefault("random_search", {})["n_trials"] = int(self._trials_var.get())
        except ValueError:
            pass
        try:
            g = opt.setdefault("genetic", {})
            g["population_size"] = int(self._pop_var.get())
            g["generations"]     = int(self._gen_var.get())
        except ValueError:
            pass

        return cfg

    def _build_space(self):
        from optimizer import (ParameterSpace, IntParameter,
                               FloatParameter, CategoricalParameter)
        params = []
        for p in self.parameters:
            t = p["type"]
            if t == "Int":
                params.append(IntParameter(
                    p["name"], p["label"],
                    start=p["start"], stop=p["stop"], step=p["step"]))
            elif t == "Float":
                params.append(FloatParameter(
                    p["name"], p["label"],
                    start=p["start"], stop=p["stop"], step=p["step"]))
            else:
                params.append(CategoricalParameter(
                    p["name"], p["label"], options=p.get("options", [])))
        return ParameterSpace(params)

    def _estimate_total(self, alg: str) -> int:
        total = 1
        for p in self.parameters:
            t = p["type"]
            if t == "Int":
                total *= max(1, len(range(p["start"], p["stop"] + 1, max(1, p["step"]))))
            elif t == "Float":
                total *= max(1, round((p["stop"] - p["start"]) / max(1e-9, p["step"])) + 1)
            else:
                total *= max(1, len(p.get("options", [])))
        if alg == "random":
            try:
                return min(total, int(self._trials_var.get()))
            except ValueError:
                pass
        if alg == "genetic":
            try:
                pop = int(self._pop_var.get())
                gen = int(self._gen_var.get())
                return pop + pop * gen
            except ValueError:
                pass
        return total

    # ── Persistence ───────────────────────────────────────────────────────

    def _save_config(self):
        data = {
            "chart_url":    self._url_var.get(),
            "username":     self._user_var.get(),
            "headless":     self._headless_var.get(),
            "algorithm":    self._algo_var.get(),
            "metric":       self._metric_var.get(),
            "maximize":     self._maximize_var.get(),
            "trials":       self._trials_var.get(),
            "backtest_wait": self._wait_var.get(),
            "pop_size":     self._pop_var.get(),
            "generations":  self._gen_var.get(),
            "parameters":   self.parameters,
            # password intentionally omitted — set via .env
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        self._status(f"Config saved → {CONFIG_FILE}")

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE) as f:
                d = json.load(f)
            self._apply_saved(d)
        except Exception as exc:
            self._status(f"Config load error: {exc}")

    def _load_config_dialog(self):
        path = filedialog.askopenfilename(
            title="Load Saved Config",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path) as f:
                d = json.load(f)
            self._apply_saved(d)
            self._status(f"Loaded: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc), parent=self)

    def _apply_saved(self, d: Dict):
        self._url_var.set(d.get("chart_url", ""))
        self._user_var.set(d.get("username", ""))
        self._headless_var.set(d.get("headless", False))
        self._algo_var.set(d.get("algorithm", "random"))
        self._metric_var.set(d.get("metric", "net_profit"))
        self._maximize_var.set(d.get("maximize", True))
        self._trials_var.set(str(d.get("trials", "100")))
        self._wait_var.set(str(d.get("backtest_wait", "8")))
        self._pop_var.set(str(d.get("pop_size", "30")))
        self._gen_var.set(str(d.get("generations", "20")))
        self.parameters = d.get("parameters", [])
        self._refresh_param_tree()

    def _status(self, msg: str):
        self._status_var.set(msg)


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App().mainloop()
