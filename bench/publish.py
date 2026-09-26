#!/usr/bin/env python3
"""Publishes evaluation results to docs/benchmark.md, the public benchmark page.

  python3 bench/publish.py add bench/results/eval-<stamp>    keep this run as the result for its model
  python3 bench/publish.py build                             write docs/benchmark.md from the kept runs

One kept run per model, in bench/published/<model>.json. A kept run holds the scorecard, not the
transcripts. Standard library only.
"""
import json, os, platform, re, subprocess, sys
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PUB = os.path.join(HERE, "published")
DOC = os.path.join(ROOT, "docs", "benchmark.md")

MODEL_MEASURES = ["protocol", "facts_given", "denials", "open_no_leak", "inaccurate", "invented", "leaked", "withheld"]
PAGE_MEASURES = ["checklist", "exams", "correct_notes", "wrong_notes", "dx_words"]
SHORT = {"protocol": "Follows the rules", "facts_given": "Gives asked facts", "denials": "Says no to absent things",
         "open_no_leak": "No leak on open questions", "inaccurate": "Contradicts the case", "invented": "Adds facts",
         "leaked": "Leaks hidden facts", "withheld": "Holds back facts", "checklist": "Checklist counted",
         "exams": "Exams found", "correct_notes": "Correct notes pass", "wrong_notes": "Wrong notes fail",
         "dx_words": "Diagnosis wordings"}

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

def add(d):
    rows = score.load_rows(d)
    sc = score.scorecard(rows)
    secs = [t["sec"] for r in rows for t in r["transcript"] if t.get("role") == "patient" and "sec" in t]
    model = sc["patient_model"]
    rec = {"model": model, "size": model_size(model), "date": date.today().isoformat(),
           "run": os.path.basename(d.rstrip("/")), "prompt_sha": rows[0].get("prompt_sha"),
           "cases": sorted({r["case"] for r in rows}), "machine": machine(),
           "median_reply_seconds": sorted(secs)[len(secs) // 2] if secs else None,
           "scorecard": sc}
    os.makedirs(PUB, exist_ok=True)
    path = os.path.join(PUB, re.sub(r"[^a-z0-9.-]+", "_", model.lower()) + ".json")
    json.dump(rec, open(path, "w"), indent=1)
    print("kept", path)

def pc(p):
    return "n/a" if not p[1] else f"{round(100 * p[0] / p[1])}%"

def build():
    recs = [json.load(open(os.path.join(PUB, f))) for f in sorted(os.listdir(PUB)) if f.endswith(".json")]
    names = {k: n for k, n, _ in score.MEASURES}
    G = score.gates()["gates"]
    L = ["[← Back to the README](../README.md)", "",
         "# Benchmark", "",
         "How well each model plays a standardized patient in this program. The same automated test",
         "runs for every model. Use this page to choose a model for your computer.", "",
         "## Results by model", "",
         "Higher is better for the first four columns. Lower is better for the last four.",
         "Each column is explained under [What each measure means](#what-each-measure-means).", "",
         "| Model | Size | Reply time | " + " | ".join(SHORT[k] for k in MODEL_MEASURES) + " | Approved |",
         "|---|---|---|" + "---|" * len(MODEL_MEASURES) + "---|"]
    for r in sorted(recs, key=lambda r: -score.rate(r["scorecard"]["overall"]["protocol"])):
        o = r["scorecard"]["overall"]
        bad = [k for k, _, _ in score.check(o) if k in MODEL_MEASURES]
        L.append(f"| `{r['model']}` | {r['size']} | {r['median_reply_seconds']} s | " +
                 " | ".join(pc(o[k]) for k in MODEL_MEASURES) + f" | {'yes' if not bad else 'no'} |")
    if len(recs) >= 2:
        rs = sorted(recs, key=lambda r: -score.rate(r["scorecard"]["overall"]["protocol"]))
        L += ["", "```mermaid", "xychart-beta", '  title "Patient replies that follow the rules (%)"',
              "  x-axis [" + ", ".join(f'"{r["model"]}"' for r in rs) + "]", "  y-axis 0 --> 100",
              "  bar [" + ", ".join(str(round(100 * score.rate(r["scorecard"]["overall"]["protocol"]))) for r in rs) + "]", "```"]
    L += ["", "Reply time is the median time for one patient reply on the test computer. Each result is from",
          "one run of the test. The test computer, date and prompt version for each result are at the end of this page.", ""]

    L += ["## What each measure means", "",
          "| Column | Meaning | Bar for approval |", "|---|---|---|"]
    meaning = {
        "protocol": "All patient replies, in both tests, that follow the rules for a standardized patient.",
        "facts_given": "The examiner asks for a fact that is in the case. The patient gives it.",
        "denials": "The examiner asks about something that is not in the case. The patient says no and adds nothing.",
        "open_no_leak": "The examiner asks an open question, such as \"anything else?\". The patient gives no hidden fact.",
        "inaccurate": "The reply says something different from the case file.",
        "invented": "The reply adds a fact that is not in the case file.",
        "leaked": "The reply gives a hidden fact that nobody asked about.",
        "withheld": "The doctor asked for a fact in the case. The reply does not give it.",
        "checklist": "A question for a checklist item, in different words, gets credit.",
        "exams": "An examination, typed in different words, finds the correct result.",
        "correct_notes": "A correct note, in different words, passes.",
        "wrong_notes": "A note with a wrong diagnosis fails.",
        "dx_words": "The correct diagnosis, in different words, gets credit.",
    }
    for k in MODEL_MEASURES + PAGE_MEASURES:
        higher = dict((a, c) for a, _, c in score.MEASURES)[k]
        bar = (f"{round(G[k] * 100)}% or more" if higher else f"{round(G[k] * 100)}% or less") if k in G else "none"
        L.append(f"| {SHORT[k]} | {meaning[k]} | {bar} |")
    L += [""]

    if recs:
        ref = max(recs, key=lambda r: r["date"])
        L += ["## Results by case", "",
              "The program marks questions, examinations and notes with fixed word rules, not with the model.",
              "These results are the same for every model. They show how well each case file is written.", "",
              "| Case | " + " | ".join(SHORT[k] for k in PAGE_MEASURES) + f" | Follows the rules, `{ref['model']}` |",
              "|---|" + "---|" * (len(PAGE_MEASURES) + 1)]
        for c, m in ref["scorecard"]["cases"].items():
            L.append(f"| {c} | " + " | ".join(pc(m[k]) for k in PAGE_MEASURES) + f" | {pc(m['protocol'])} |")
        L += [""]

    L += ["## How the test works", "",
          "The test uses the real program. It sends the same prompt and the same settings to the patient",
          "model as the program does. It counts questions, examinations and notes with the program's own code.",
          "Three other roles are played by Claude, a large AI model from Anthropic:", "",
          "- **The student.** It gets only the information on the door of the room. It interviews the",
          "  patient, examines, and writes a note. This shows what a learner sees.",
          "- **The examiner.** It knows the whole case. It asks for every fact and every checklist item,",
          "  in words that are different from the case file. It also asks about things that are not in the",
          "  case, and asks open questions. It tries correct notes and wrong notes.",
          "- **The judge.** It reads the case file and every reply. It gives each reply one verdict:",
          "  correct, withheld, inaccurate, invented, leaked, wrong \"I don't know that word\" reply, or",
          "  out of character.", "",
          "The examiner's questions are the same for every model. They are in `bench/scripts/`.",
          "The code is in `bench/`. See [`bench/README.md`](../bench/README.md) to run the test yourself.", "",
          "## Limits of this test", "",
          "- One run is a sample. The patient model uses some randomness, so a second run gives",
          "  slightly different numbers. A difference of a few percent between two models can be chance.",
          "- The judge is an AI model. It can make mistakes. Every verdict and its reason are kept in",
          "  the results, so a person can check them.",
          "- The word rules count only the words in each case file. A good question in unusual words",
          "  can get no credit. A check with new, unseen wording finds this.",
          "- Reply time depends on the computer. A computer without a graphics chip is slower.",
          "- Eight cases is a small set. The cases are from MedEdPORTAL and are in English.", ""]

    L += ["## Test details", "", "| Model | Date | Test computer | Prompt version | Cases |", "|---|---|---|---|---|"]
    for r in recs:
        L.append(f"| `{r['model']}` | {r['date']} | {r['machine']} | `{r['prompt_sha']}` | {len(r['cases'])} |")
    L += ["", "[← Back to the README](../README.md)", ""]
    open(DOC, "w").write("\n".join(L))
    print("wrote", DOC)

if __name__ == "__main__":
    if sys.argv[1:2] == ["add"] and len(sys.argv) == 3: add(sys.argv[2])
    elif sys.argv[1:2] == ["build"]: build()
    else: print(__doc__)
