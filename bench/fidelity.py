#!/usr/bin/env python3
"""The fidelity check. Compares a case file with the original MedEdPORTAL case it was adapted
from, so a change that improves the benchmark cannot quietly move the case away from what its
authors published. Claude reads both and lists every difference that matters.

  python3 bench/fidelity.py springfield                 one case
  python3 bench/fidelity.py                             every case
  python3 bench/fidelity.py springfield --against FILE  a draft case file instead of the live one

The original files are not in this repository. Point VSP_SOURCES at the folder that holds
mededportal_<id>/source-text/ (default: ../workshop/vsp/sources next to this repository).
Results go to bench/results/fidelity-<timestamp>/. Standard library only.
"""
import json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval import HERE, ROOT, CASES, claude

SOURCES = os.environ.get("VSP_SOURCES") or os.path.join(os.path.dirname(ROOT), "workshop", "vsp", "sources")

# Which original files each case comes from. The learner-facing files (door card, scoring) are
# included too, because the answer key and the task come from them.
MAP = {
    "graham":      ("mededportal_8139", ["Jennifer_Jerry_Graham_Cholangitis_OSCE_2010", "Jennifer_Jerry_Graham_Checklist_2010", "Instructor's_Guide"]),
    "morris":      ("mededportal_8139", ["Mark_Marsha_Morris_Diverticulitis_OSCE_2010", "Mark_Marsha_Morris_Checklist_2010", "Instructor's_Guide"]),
    "travis":      ("mededportal_8139", ["Tim_Terri_Travis_Perforated_Ulcer_OSCE_2010", "Tim_Terri_Travis_Checklist_2010", "Instructor's_Guide"]),
    "lewis":       ("mededportal_10867", None),
    "springfield": ("mededportal_11146", None),
    "samuels":     ("mededportal_10837", None),
    "davis":       ("mededportal_11216", None),
    "bellevue":    ("mededportal_11001", None),
}

SYS = """You check that a case file for a simulated patient stays faithful to the published
standardized patient case it was adapted from. A small language model plays the patient from
the case file. Lines marked "(only if asked)" are facts the patient gives only to a direct
question. Other [STORY] lines may be said when the doctor asks about that topic.

Adapting is allowed: rewording, plain words, splitting or merging lines, short answers,
instructions on how to speak, and marking which facts are held back. Judge the facts.

List every item in these groups. Quote the case file line and the original text for each.
- added: a fact in the case file that the original does not state and that cannot be read from it
- contradicts: a fact in the case file that goes against the original
- missing: a fact the original gives the patient that matters for the diagnosis, the checklist or
  the answer key, and that the case file leaves out
- held_back: a fact the case file marks "(only if asked)" although the original gives it freely,
  for example in the opening statement or the patient's own story
- answer_key: a difference between the case file's [ANSWER] or [QUESTIONS] and the original's
  answer, differential, tests or checklist
Give "none" groups as empty lists. Be strict on facts and lenient on words. Reply with JSON only."""

ITEM = {"type": "object", "properties": {"case_line": {"type": "string"}, "original": {"type": "string"},
        "note": {"type": "string"}}, "required": ["case_line", "original", "note"]}
SCHEMA = {"type": "object", "properties": {k: {"type": "array", "items": ITEM} for k in
          ["added", "contradicts", "missing", "held_back", "answer_key"]} |
          {"verdict": {"type": "string"}},
          "required": ["added", "contradicts", "missing", "held_back", "answer_key", "verdict"]}

def source_text(cid):
    d, names = MAP[cid]
    folder = os.path.join(SOURCES, d, "source-text")
    files = sorted(os.listdir(folder))
    if names: files = [f for f in files if f[:-4] in names]
    return "\n\n".join(f"=== {f}\n" + open(os.path.join(folder, f), errors="replace").read() for f in files)

def check(cid, path=None, model="opus"):
    case = open(path or os.path.join(CASES, cid + ".txt")).read()
    prompt = f"ORIGINAL PUBLISHED CASE\n{source_text(cid)}\n\nCASE FILE\n{case}"
    return claude(model, SYS, prompt, SCHEMA)

def show(cid, r):
    print(f"== {cid}: {r['verdict']}")
    for k in ["contradicts", "added", "missing", "held_back", "answer_key"]:
        for x in r[k]:
            print(f"   {k:11s} {x['case_line'][:90]!r}\n               original: {x['original'][:90]!r}\n               {x['note'][:160]}")

if __name__ == "__main__":
    args = sys.argv[1:]
    against = None
    if "--against" in args:
        i = args.index("--against"); against = args[i + 1]; args = args[:i] + args[i + 2:]
    ids = args or list(MAP)
    out = os.path.join(HERE, "results", "fidelity-" + datetime.now().strftime("%Y-%m-%d-%H%M"))
    os.makedirs(out, exist_ok=True)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4) as ex:
        res = dict(zip(ids, ex.map(lambda c: check(c, against), ids)))
    for cid, r in res.items():
        show(cid, r)
        json.dump(r, open(os.path.join(out, cid + ".json"), "w"), indent=1)
    print("\n" + " | ".join(f"{c}: {sum(len(r[k]) for k in ['contradicts', 'added', 'held_back'])} issues" for c, r in res.items()))
    print("results in", out)
