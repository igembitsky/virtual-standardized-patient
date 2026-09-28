#!/usr/bin/env python3
"""Publishes evaluation results to docs/benchmark.html, the public benchmark page.

  python3 bench/publish.py add RUN+RUN [--unseen RUN]   keep these runs as the result for their model
  python3 bench/publish.py build                        write docs/benchmark.html from the kept results

RUN is a folder in bench/results/. Join two or more with + to pool them. --unseen names a run made
with `eval.py --fresh`: new examiner questions that no fix was tuned on. One kept result per model,
in bench/published/<model>.json. It holds the scorecard, not the transcripts.

The approval decision is made here, with the rules in gates.json, and written into the page.
The page only shows it. Standard library only.
"""
import glob, json, os, platform, re, subprocess, sys, urllib.request
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PUB = os.path.join(HERE, "published")
DOC = os.path.join(ROOT, "docs", "benchmark.html")
OLLAMA = "http://127.0.0.1:11434"

def machine():
    try:
        chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip())
        return f"{chip}, {round(mem / 2**30)} GB, macOS {platform.mac_ver()[0]}"
    except Exception:
        return platform.platform()

def model_size(model):
    out = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.split() and line.split()[0] in (model, model + ":latest"):
            m = re.search(r"(\d+(\.\d+)?\s*[GM]B)", line)
            return m.group(1) if m else ""
    return ""

def model_ram(model):
    """Memory the model takes with the program's settings (8,192 word pieces of context)."""
    try:
        body = json.dumps({"model": model, "prompt": "Hello", "stream": False, "keep_alive": "1m",
                           "options": {"num_ctx": 8192, "num_predict": 1}}).encode()
        urllib.request.urlopen(urllib.request.Request(OLLAMA + "/api/generate", data=body), timeout=300).read()
        for m in json.load(urllib.request.urlopen(OLLAMA + "/api/ps", timeout=10)).get("models", []):
            if m["name"] in (model, model + ":latest"):
                return f"{m['size'] / 1e9:.1f} GB"
    except Exception:
        pass
    return ""

def decide(sc, runs, unseen_sc):
    """Approval of a model, by the rules in gates.json. Returns (approved, reasons)."""
    g = score.gates(); reasons = []
    labels = {k: n for k, n, _ in score.MEASURES}
    for k, r, bar in score.check(sc["overall"]):
        reasons.append(f"{labels[k]}: {r * 100:.1f}%, bar {bar * 100:.0f}%")
    if runs < g["rules"]["model_min_runs"]:
        reasons.append(f"Only {runs} test run. It needs {g['rules']['model_min_runs']}.")
    if unseen_sc is None:
        reasons.append("No check with new questions yet.")
    else:
        for k, r, bar in score.check(unseen_sc["overall"]):
            if k in g["patient_gates"]:
                reasons.append(f"New questions: {labels[k]} {r * 100:.1f}%, bar {bar * 100:.0f}%")
    return not reasons, reasons

def add(d, unseen=None):
    rows = score.load_rows(d)
    sc = score.scorecard(rows)
    model = sc["patient_model"]
    secs = sorted(t["sec"] for r in rows for t in r["transcript"] if t.get("role") == "patient" and "sec" in t)
    unseen_sc = score.scorecard(score.load_rows(unseen)) if unseen else None
    if unseen_sc and unseen_sc["patient_model"] != model:
        sys.exit(f"--unseen is a run of {unseen_sc['patient_model']}, not {model}")
    runs = len(d.split("+"))
    ok, reasons = decide(sc, runs, unseen_sc)
    rec = {"model": model, "size": model_size(model), "ram": model_ram(model),
           "reply": f"{secs[len(secs) // 2]} s" if secs else "",
           "date": date.today().isoformat(), "machine": machine(),
           "run": "+".join(os.path.basename(x.rstrip("/")) for x in d.split("+")), "runs": runs,
           "unseen_run": os.path.basename(unseen.rstrip("/")) if unseen else None,
           "prompt_sha": rows[0].get("prompt_sha"), "names": {r["case"]: r["name"] for r in rows},
           "approved": ok, "reasons": reasons,
           "scorecard": sc, "unseen": unseen_sc}
    os.makedirs(PUB, exist_ok=True)
    path = os.path.join(PUB, re.sub(r"[^a-z0-9.-]+", "_", model.lower()) + ".json")
    json.dump(rec, open(path, "w"), indent=1)
    print("kept", path, "approved" if ok else "not approved: " + "; ".join(reasons))

def build():
    recs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(PUB, "*.json")))]
    recs.sort(key=lambda r: -score.rate(r["scorecard"]["overall"]["protocol"]))
    g = score.gates()
    data = {"gates": g["gates"], "why": g["why"], "rules": g["rules"],
            "patient_gates": g["patient_gates"], "program_gates": g["program_gates"],
            "lower": ["inaccurate", "invented", "leaked", "withheld"],
            "models": [{k: r.get(k) for k in ("model", "size", "ram", "reply", "date", "machine", "runs",
                                              "prompt_sha", "names", "approved", "reasons")} |
                       {"overall": r["scorecard"]["overall"], "cases": r["scorecard"]["cases"],
                        "unseen": r["unseen"]["overall"] if r.get("unseen") else None}
                       for r in recs]}
    t = open(os.path.join(HERE, "benchmark_template.html")).read()
    open(DOC, "w").write(t.replace("__DATA__", json.dumps(data).replace("<", "\\u003c")))
    print("wrote", DOC)

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["add"] and len(a) in (2, 4):
        add(a[1], a[3] if len(a) == 4 and a[2] == "--unseen" else None)
    elif a[:1] == ["build"]:
        build()
    else:
        print(__doc__)
