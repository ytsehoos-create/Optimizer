"""Fill report_template.html with the series from repdata.json and write the dashboard page."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(here, "repdata.json")))
keep = {k: D[k] for k in ("eq_rec", "eq_lx", "eq_gm", "exp", "monthly", "t3")}
s = open(os.path.join(here, "report_template.html"), encoding="utf-8").read()
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "..", "output", "2026.11.13-mnq-t2-review", "dashboard.html")
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
open(out, "w", encoding="utf-8").write(s.replace("__DATA__", json.dumps(keep, separators=(",", ":"))))
print("wrote", out)
