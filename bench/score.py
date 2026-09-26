#!/usr/bin/env python3
"""The scorecard: the same measures, computed the same way, for every evaluation run.

  python3 bench/score.py bench/results/eval-A                  the scorecard and the gates
  python3 bench/score.py bench/results/eval-A bench/results/eval-B    before and after

Measures are counts (passed, out of). The gates in gates.json are the bar a case, a model or a
prompt change must meet before it is approved. Standard library only.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

# name, what it means, higher is better
MEASURES = [
    ("protocol",        "Patient replies that follow the protocol", True),
    ("facts_given",     "Facts given when asked", True),
    ("denials",         "Clean no to things not in the case", True),
    ("open_no_leak",    "Open questions without a leak", True),
    ("inaccurate",      "Replies that contradict the file", False),
    ("invented",        "Replies that add a fact", False),
    ("leaked",          "Replies that leak a hidden fact", False),
    ("withheld",        "Replies that hold back an asked fact", False),
    ("checklist",       "Checklist questions counted, varied words", True),
    ("checklist_reach", "Checklist items reachable by the script", True),
    ("exams",           "Examinations found, varied words", True),
    ("correct_notes",   "Correct notes that pass", True),
    ("wrong_notes",     "Wrong notes that fail", True),
    ("dx_words",        "Diagnosis wordings counted", True),
    ("test_words",      "Test wordings counted (information only)", True),
    ("student_pass",    "Student passes (information only, about the student)", True),
]

def load_rows(d):
    return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(d, "*-*.json")))
            if not f.endswith("scorecard.json")]

def _measures(rows):
    m = {k: [0, 0] for k, _, _ in MEASURES}
    def add(k, ok, n=1): m[k][0] += ok; m[k][1] += n
    for r in rows:
        pts = [t for t in r["transcript"] if t["role"] == "patient" and not t.get("opening")]
        for t in pts:
            v = t.get("verdict")
            add("protocol", v == "correct")
            for k in ("inaccurate", "invented", "leaked", "withheld"): add(k, v == k)
        if r["suite"] == "student":
            add("student_pass", bool(r.get("pass")))
            continue
        for t in pts:
            if t.get("jargon"): continue
            e = {"reveal": "facts_given", "deny": "denials", "open": "open_no_leak"}.get(t.get("expect"))
            if e: add(e, t.get("verdict") == "correct")
        for x in r["credit"]: add("checklist", x["counted"])
        add("checklist_reach", len(r["covered"]), r["total"])
        for x in r["exams"]: add("exams", x["ok"])
        for x in r["correct_notes"]: add("correct_notes", x["pass"])
        for x in r["wrong_notes"]: add("wrong_notes", not x["pass"])
        for x in r["top_dx"]: add("dx_words", x["counted"])
        for x in r["tests"]: add("test_words", x["counted"])
    return m

def scorecard(rows):
    cases = {}
    for r in rows: cases.setdefault(r["case"], []).append(r)
    return {"patient_model": rows[0].get("patient_model") if rows else None,
            "overall": _measures(rows),
            "cases": {c: _measures(rs) for c, rs in sorted(cases.items())}}

def rate(p):
    return None if not p[1] else p[0] / p[1]

def cell(p):
    if not p[1]: return "n/a"
    v = 100 * p[0] / p[1]
    return (f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}") + f"% ({p[0]}/{p[1]})"

def gates():
    return json.load(open(os.path.join(HERE, "gates.json")))

def check(m):
    """The gates this set of measures fails, as (measure, rate, bar) tuples."""
    out = []
    for k, bar in gates()["gates"].items():
        r = rate(m[k])
        if r is None: continue
        higher = dict((a, c) for a, _, c in MEASURES)[k]
        if (higher and r < bar - 1e-9) or (not higher and r > bar + 1e-9): out.append((k, r, bar))
    return out

def gate_md(sc):
    names = {k: n for k, n, _ in MEASURES}
    G = gates()["gates"]
    L = ["## Gates", "", "The bar for approval. Set in `bench/gates.json`.", "",
         "| Measure | Bar | Overall | Result |", "|---|---|---|---|"]
    for k, bar in G.items():
        higher = dict((a, c) for a, _, c in MEASURES)[k]
        p = sc["overall"][k]; r = rate(p)
        ok = r is None or (r >= bar - 1e-9 if higher else r <= bar + 1e-9)
        L.append(f"| {names[k]} | {'at least' if higher else 'at most'} {round(bar * 100)}% | {cell(p)} | {'pass' if ok else 'FAIL'} |")
    L += ["", "| Case | Result |", "|---|---|"]
    for c, m in sc["cases"].items():
        bad = check(m)
        L.append(f"| {c} | " + ("approved" if not bad else "not approved: " +
                 ", ".join(f"{names[k]} {round(r * 100)}%" for k, r, _ in bad)) + " |")
    return "\n".join(L) + "\n"

def compare_md(a, b, la="before", lb="after"):
    names = {k: n for k, n, _ in MEASURES}
    higher = dict((k, h) for k, _, h in MEASURES)
    L = [f"| Measure | {la} | {lb} | Change |", "|---|---|---|---|"]
    for k, _, _ in MEASURES:
        pa, pb = a["overall"][k], b["overall"][k]
        ra, rb = rate(pa), rate(pb)
        ch = ""
        if ra is not None and rb is not None:
            d = round(100 * (rb - ra))
            ch = "same" if d == 0 else (("better" if (d > 0) == higher[k] else "worse") + f" {d:+d}")
        L.append(f"| {names[k]} | {cell(pa)} | {cell(pb)} | {ch} |")
    keys = ["protocol", "facts_given", "checklist", "exams", "correct_notes"]
    L += ["", "| Case | " + " | ".join(f"{names[k]}" for k in keys) + " |", "|---|" + "---|" * len(keys)]
    for c in sorted(set(a["cases"]) | set(b["cases"])):
        row = []
        for k in keys:
            pa = a["cases"].get(c, {}).get(k, [0, 0]); pb = b["cases"].get(c, {}).get(k, [0, 0])
            fa = "n/a" if not pa[1] else f"{round(100 * pa[0] / pa[1])}%"
            fb = "n/a" if not pb[1] else f"{round(100 * pb[0] / pb[1])}%"
            row.append(f"{fa} → {fb}")
        L.append(f"| {c} | " + " | ".join(row) + " |")
    return "\n".join(L) + "\n"

if __name__ == "__main__":
    if len(sys.argv) == 2:
        sc = scorecard(load_rows(sys.argv[1]))
        names = {k: n for k, n, _ in MEASURES}
        print("| Measure | Result |\n|---|---|")
        for k, _, _ in MEASURES: print(f"| {names[k]} | {cell(sc['overall'][k])} |")
        print("\n" + gate_md(sc))
    elif len(sys.argv) == 3:
        a, b = (scorecard(load_rows(d)) for d in sys.argv[1:])
        print(compare_md(a, b, os.path.basename(sys.argv[1].rstrip("/")), os.path.basename(sys.argv[2].rstrip("/"))))
        print(gate_md(b))
    else:
        print(__doc__)
