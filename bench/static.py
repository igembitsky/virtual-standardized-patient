#!/usr/bin/env python3
"""The fast check. Runs the standard examiner scripts through the page's own rules only:
checklist credit, jargon catch, examination matcher and note marking. No patient model, no
Claude, a few seconds. Use it after any change to a case file's word lists or answer key, or to
the matching code in app/index.html. The full check is eval.py.

  python3 bench/static.py                 every case
  python3 bench/static.py graham travis   some cases
  python3 bench/static.py --scripts DIR   other scripts, for example unseen ones from --write-fresh DIR
  python3 bench/static.py --write-fresh DIR   have the examiner write new scripts into DIR first
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval import HERE, ROOT, CASES, load_case, page_check

SCRIPTS = os.path.join(HERE, "scripts")

def check(cid):
    path = os.path.join(CASES, cid + ".txt")
    c = load_case(path)
    plan = json.load(open(os.path.join(SCRIPTS, cid + ".json")))
    probes = plan["probes"]
    ans = c["answer"]
    notes = ([("correct", n) for n in plan["correct_notes"]] + [("wrong", n) for n in plan["wrong_notes"]] +
             [("dx", {"dx": [v], "tx": []}) for v in plan["top_dx_variants"]] +
             [("key dx", {"dx": [ans.get("top", "")], "tx": []})] +
             [("key test", {"dx": [], "tx": [t]}) for t in ans.get("tests", [])])
    r = page_check(path, {"ask": [p["question"] for p in probes],
                          "examine": [e["phrasing"] for e in plan["exams"]],
                          "notes": [n for _, n in notes]})
    bad, n = [], {"checklist": [0, 0], "exams": [0, 0], "notes": [0, 0]}
    for p, x in zip(probes, r["ask"]):
        if not p["credits"]: continue
        ok = p["credits"] in x["credits"]; n["checklist"][0] += ok; n["checklist"][1] += 1
        if not ok: bad.append(f"checklist  {p['credits']!r} not counted: {p['question']}" +
                              (f"  [jargon: {x['jargon']}]" if x["jargon"] else ""))
    reached = {l for x in r["ask"] for l in x["credits"]}
    for q in c["questions"]:
        if q["label"] not in reached: bad.append(f"checklist  never reached: {q['label']}")
    for e, x in zip(plan["exams"], r["examine"]):
        want = (c["examine"].get(e["key"].lower()) or "").strip()
        ok = x["finding"].strip() == want if want else x["name"] is not None
        n["exams"][0] += ok; n["exams"][1] += 1
        if not ok: bad.append(f"exam       {e['phrasing']!r} for {e['key']} gave: {x['finding'][:60]}")
    for (kind, note), x in zip(notes, r["notes"]):
        if kind == "correct": ok = x["pass"]
        elif kind == "wrong": ok = not x["pass"]
        elif kind in ("dx", "key dx"): ok = x["dxHit"]
        else: ok = x["txHit"]
        if kind != "key test": n["notes"][0] += ok; n["notes"][1] += 1
        if not ok: bad.append(f"marking    {kind} {'passes' if kind == 'wrong' else 'not counted'}: dx {note['dx']} tests {note['tx']}")
    return c["name"], n, bad

def write_fresh(d):
    from concurrent.futures import ThreadPoolExecutor
    from eval import claude, PLAN_SYS, PLAN_SCHEMA
    os.makedirs(d, exist_ok=True)
    def one(f):
        c = load_case(os.path.join(CASES, f))
        labels = [q["label"] for q in c["questions"]]
        plan = claude("opus", PLAN_SYS, "CASE FILE\n" + c["raw"] +
                      "\n\nCHECKLIST LABELS, use exactly one of these or \"\" in credits:\n" +
                      "\n".join("- " + l for l in labels), PLAN_SCHEMA)
        json.dump({"case": c["id"], **plan}, open(os.path.join(d, c["id"] + ".json"), "w"), indent=1)
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(one, sorted(f for f in os.listdir(CASES) if f.endswith(".txt"))))

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--write-fresh"]:
        write_fresh(args[1]); args = ["--scripts", args[1]] + args[2:]
    if args[:1] == ["--scripts"]:
        SCRIPTS = os.path.abspath(args[1]); args = args[2:]
    ids = args or sorted(f[:-5] for f in os.listdir(SCRIPTS) if f.endswith(".json"))
    tot = {"checklist": [0, 0], "exams": [0, 0], "notes": [0, 0]}
    for cid in ids:
        name, n, bad = check(cid)
        for k in tot: tot[k][0] += n[k][0]; tot[k][1] += n[k][1]
        print(f"{name}: checklist {n['checklist'][0]}/{n['checklist'][1]}, exams {n['exams'][0]}/{n['exams'][1]}, "
              f"notes {n['notes'][0]}/{n['notes'][1]}")
        for b in bad: print("   " + b)
    print(f"\nALL: checklist {tot['checklist'][0]}/{tot['checklist'][1]}, exams {tot['exams'][0]}/{tot['exams'][1]}, "
          f"notes {tot['notes'][0]}/{tot['notes'][1]}. A key test that is not counted is fine if the case "
          "means only some tests to count.")
