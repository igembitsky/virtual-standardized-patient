#!/usr/bin/env python3
"""Plays a Claude doctor against the real simulated patient, once per case, then has a
second Claude judge every patient line against the case file.

  python3 bench/bench.py                       all cases, one run each
  python3 bench/bench.py --cases graham,morris --runs 2
  python3 bench/bench.py --doctor haiku --judge sonnet

The doctor sees only what a learner sees: the door card. The judge sees everything.
Results go to bench/results/<timestamp>/ with a summary.md. Standard library only.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLLAMA = "http://127.0.0.1:11434"
CLAUDE_MIN = ["--no-session-persistence", "--output-format", "json",
              "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
              "--disable-slash-commands", "--setting-sources", ""]

DOCTOR_SYS = """You are a final-year medical student at an OSCE station with a simulated patient.
You know only the door card. Take a focused history, examine when it helps, then give three
differential diagnoses, most likely first, and three initial tests. One attempt, no retries.
Each turn reply with JSON only, one of:
{"action":"ask","question":"one question, as you would say it to the patient"}
{"action":"examine","part":"one of the allowed parts"}
{"action":"finish","diagnoses":["most likely","second","third"],"tests":["test","test","test"]}
Exactly one question per turn. A sentence that joins two topics with "and" or "or" is two
questions; split them. The turn count is your clock."""

DOCTOR_SCHEMA = {"type": "object", "properties": {
    "action": {"type": "string", "enum": ["ask", "examine", "finish"]},
    "question": {"type": "string"}, "part": {"type": "string"},
    "diagnoses": {"type": "array", "items": {"type": "string"}},
    "tests": {"type": "array", "items": {"type": "string"}}},
    "required": ["action"]}

JUDGE_SYS = """You are an OSCE examiner auditing a simulated patient played by a small local
language model. You get the case file the patient was built from, the exact system prompt it
ran under, and the transcript. Judge EVERY patient turn with one verdict:
- accurate: matches the case file, or a harmless paraphrase of it
- inaccurate: contradicts the case file
- invented: states a fact that is not in the case file and cannot be inferred from it
- leaked: gives a line marked "only if asked" without a direct question about that exact thing
- canned_misfire: uses the "I don't know that word" or "not following you" line when the
  doctor's sentence had no medical term and was clear
- off_persona: bullet points, breaks role, mentions being a model, or runs far past one or two
  sentences when the persona asks for short answers
"Go ahead, doctor" to a request to touch, press, feel or listen is accurate.
"No, doctor, that's all" to an open question is accurate. Be strict on facts, lenient on words.
Reply with JSON only."""

JUDGE_SCHEMA = {"type": "object", "properties": {
    "turns": {"type": "array", "items": {"type": "object", "properties": {
        "turn": {"type": "integer"},
        "verdict": {"type": "string", "enum": ["accurate", "inaccurate", "invented", "leaked", "canned_misfire", "off_persona"]},
        "note": {"type": "string"}}, "required": ["turn", "verdict", "note"]}},
    "overall": {"type": "string"}}, "required": ["turns", "overall"]}

# ---------- ports of the app's own deterministic logic ----------
def word_hit(hay, word):
    w = word.lower().strip()
    if not w: return False
    stem = w.endswith("*")
    core = re.escape(w[:-1] if stem else w)
    return re.search(r"(^|[^a-z0-9])" + core + ("" if stem else r"($|[^a-z0-9])"), hay, re.I) is not None

def mark_covered(text, questions, covered):
    t = " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", text.lower())) + " "
    for q in questions:
        if q["id"] in covered: continue
        if any(word_hit(t, w) for w in q["words"]): covered.add(q["id"])

def has_any(text, words):
    if not words: return False
    t = " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())) + " "
    return any(word_hit(t, w) for w in words)

def do_examine(what, examine):
    keys = list(examine.keys())
    q = re.sub(r"[^a-z ]", "", (what or "").lower()).strip()
    if not q: return None, "You can examine: " + ", ".join(keys) + "."
    hit = next((k for k in keys if k in q), None) or \
          next((k for k in keys if any(w in q for w in k.split(" "))), None)
    if hit: return hit, examine[hit]
    return None, "This case has no findings for that. Try: " + ", ".join(keys) + "."

# ---------- model calls ----------
def load_case(path):
    out = subprocess.run(["node", os.path.join(HERE, "case.js"), os.path.join(ROOT, "index.html"), path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)

def patient_say(model, messages):
    body = json.dumps({"model": model, "messages": messages, "stream": False, "keep_alive": "20m",
                       "options": {"temperature": 0.6, "num_ctx": 8192, "num_predict": 300}}).encode()
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r: d = json.load(r)
    return d["message"]["content"].strip(), round(time.time() - t0, 1)

def claude(model, system, prompt, schema):
    cmd = ["claude", "-p", "--model", model, *CLAUDE_MIN, "--json-schema", json.dumps(schema),
           "--system-prompt", system, "--tools", ""]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300)
    try: d = json.loads(p.stdout)
    except Exception: raise RuntimeError("claude did not return JSON: " + (p.stdout or p.stderr)[:300])
    if d.get("is_error"): raise RuntimeError("claude error: " + str(d.get("result"))[:300])
    out = d.get("structured_output")
    if out is None:
        try: out = json.loads(d.get("result") or "")
        except Exception: raise RuntimeError("no structured output: " + str(d.get("result"))[:300])
    return out, float(d.get("total_cost_usd") or 0)

# ---------- one encounter ----------
def door_card(c, cap):
    vit = "; ".join(f"{v['label']} {v['value']}" for v in c["vitals"]) or "not taken"
    return (f"DOOR CARD\nPatient: {c['name']}, age {c['age']}, {c['occupation']}.\nSetting: {c['setting']}.\n"
            f"Complaint: {c['complaint']}.\nVital signs: {vit}.\nTask: {c['task']}\n"
            f"You may examine: {', '.join(c['examine'].keys()) or 'nothing'}.\nYou have {cap} turns.")

def fmt_transcript(turns):
    lines = []
    for t in turns:
        who = {"doctor": "You", "patient": "Patient", "examination": "Examination"}[t["role"]]
        lines.append(f"{who}: {t['text']}")
    return "\n".join(lines) or "(nothing yet)"

def play(c, args, run_no):
    cap = int(c.get("consultMins") or 15)
    card = door_card(c, cap)
    msgs = [{"role": "system", "content": c["system"]},
            {"role": "user", "content": "Good day. I am the doctor. Why are you here today?"},
            {"role": "assistant", "content": c["opening"]}]
    turns, covered, cost, t0 = [], set(), 0.0, time.time()
    dx, tx, finished, error = [], [], False, None
    for n in range(1, cap + 2):
        last = n >= cap
        prompt = (card + "\n\nTRANSCRIPT SO FAR\n" + fmt_transcript(turns) +
                  f"\n\nTurn {min(n, cap)} of {cap}. " +
                  ("This is your last turn. action must be finish." if last else "Reply with JSON."))
        try:
            act, usd = claude(args.doctor, DOCTOR_SYS, prompt, DOCTOR_SCHEMA)
        except Exception as e:
            error = str(e); break
        cost += usd
        a = act.get("action")
        if a == "ask" and act.get("question") and not act["question"].lstrip().startswith("{"):
            q = act["question"].strip()
            turns.append({"role": "doctor", "text": q})
            mark_covered(q, c["questions"], covered)
            msgs.append({"role": "user", "content": q})
            try:
                reply, sec = patient_say(args.patient_model, msgs)
            except Exception as e:
                error = "patient: " + str(e); break
            msgs.append({"role": "assistant", "content": reply})
            turns.append({"role": "patient", "text": reply, "sec": sec})
        elif a == "examine":
            part = act.get("part", "")
            turns.append({"role": "doctor", "text": "examine " + part})
            hit, line = do_examine(part, c["examine"])
            turns.append({"role": "examination", "text": (hit + ": " if hit else "") + line})
        elif a == "finish" or last:
            dx = [s.strip() for s in (act.get("diagnoses") or []) if s and s.strip()][:3]
            tx = [s.strip() for s in (act.get("tests") or []) if s and s.strip()][:3]
            finished = True; break
        else:
            turns.append({"role": "doctor", "text": "(unusable reply: " + json.dumps(act)[:120] + ")"})
    dx_words = c["answer"].get("dxWords") or []; tx_words = c["answer"].get("txWords") or []
    dx_hit = has_any(" ".join(dx), dx_words); tx_hit = has_any(" ".join(tx), tx_words)
    return {
        "case": c["id"], "name": c["name"], "file": c["file"], "run": run_no,
        "patient_model": args.patient_model, "doctor_model": args.doctor,
        "prompt_sha": hashlib.sha256(c["system"].encode()).hexdigest()[:12],
        "turn_cap": cap, "doctor_turns": sum(1 for t in turns if t["role"] == "doctor"),
        "covered": len(covered), "total": len(c["questions"]),
        "covered_labels": [q["label"] for q in c["questions"] if q["id"] in covered],
        "missed_labels": [q["label"] for q in c["questions"] if q["id"] not in covered],
        "dx": dx, "tests": tx, "dxHit": dx_hit, "txHit": tx_hit, "pass": dx_hit and tx_hit,
        "expected": c["answer"].get("top"), "finished": finished, "error": error,
        "transcript": turns, "doctor_cost_usd": round(cost, 4), "seconds": round(time.time() - t0),
    }

def judge(c, enc, args):
    pt = [t for t in enc["transcript"] if t["role"] == "patient"]
    numbered, k = [], 0
    for t in enc["transcript"]:
        if t["role"] == "patient": k += 1; numbered.append(f"Patient turn {k}: {t['text']}")
        elif t["role"] == "doctor": numbered.append(f"Doctor: {t['text']}")
        else: numbered.append(f"Examination (from the file, not the model): {t['text']}")
    prompt = ("CASE FILE\n" + c["raw"] + "\n\nSYSTEM PROMPT THE PATIENT RAN UNDER\n" + c["system"] +
              "\n\nTRANSCRIPT\n" + "\n".join(numbered) + f"\n\nThere are {len(pt)} patient turns. Judge each one.")
    out, usd = claude(args.judge, JUDGE_SYS, prompt, JUDGE_SCHEMA)
    counts = {}
    for t in out.get("turns", []): counts[t["verdict"]] = counts.get(t["verdict"], 0) + 1
    return {"model": args.judge, "turns": out.get("turns", []), "counts": counts,
            "overall": out.get("overall", ""), "cost_usd": round(usd, 4)}

def summary_md(rows):
    H = ["patient", "run", "turns", "questions", "pass", "dx / tests hit", "accurate", "inaccurate", "invented", "leaked", "misfire", "off-persona", "cost $"]
    L = ["| " + " | ".join(H) + " |", "|" + "---|" * len(H)]
    for r in rows:
        j = r.get("judge", {}).get("counts", {})
        L.append("| " + " | ".join(str(x) for x in [
            r["name"], r["run"], f"{r['doctor_turns']}/{r['turn_cap']}", f"{r['covered']} of {r['total']}",
            "PASS" if r["pass"] else ("ERROR" if r["error"] else "fail"),
            f"{'y' if r['dxHit'] else 'n'} / {'y' if r['txHit'] else 'n'}",
            j.get("accurate", 0), j.get("inaccurate", 0), j.get("invented", 0), j.get("leaked", 0),
            j.get("canned_misfire", 0), j.get("off_persona", 0),
            f"{r['doctor_cost_usd'] + r.get('judge', {}).get('cost_usd', 0):.2f}"]) + " |")
    return "\n".join(L)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="", help="comma separated case ids, default all")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--doctor", default="sonnet")
    ap.add_argument("--judge", default="opus")
    ap.add_argument("--patient-model", default="qwen3:4b-instruct")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    args = ap.parse_args()
    files = sorted(f for f in os.listdir(os.path.join(ROOT, "cases")) if f.endswith(".txt"))
    want = [s.strip() for s in args.cases.split(",") if s.strip()]
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    outdir = os.path.join(args.out, stamp); os.makedirs(outdir, exist_ok=True)
    rows = []
    for f in files:
        c = load_case(os.path.join(ROOT, "cases", f))
        if want and c["id"] not in want: continue
        for run_no in range(1, args.runs + 1):
            print(f"== {c['name']} run {run_no}", flush=True)
            enc = play(c, args, run_no)
            for t in enc["transcript"]:
                print(f"   {t['role'][:3]}: {t['text']}", flush=True)
            print(f"   -> {enc['covered']} of {enc['total']} questions, dx={enc['dx']}, tests={enc['tests']}, "
                  f"{'PASS' if enc['pass'] else 'fail'}, {enc['seconds']}s, ${enc['doctor_cost_usd']}" +
                  (f", ERROR {enc['error']}" if enc["error"] else ""), flush=True)
            if not args.no_judge and enc["transcript"]:
                try:
                    enc["judge"] = judge(c, enc, args)
                    print(f"   judge: {enc['judge']['counts']} — {enc['judge']['overall'][:200]}", flush=True)
                except Exception as e:
                    enc["judge"] = {"error": str(e), "counts": {}}; print("   judge failed:", e, flush=True)
            rows.append(enc)
            json.dump(enc, open(os.path.join(outdir, f"{c['id']}-{run_no}.json"), "w"), indent=1, ensure_ascii=False)
            open(os.path.join(outdir, "summary.md"), "w").write(
                f"# Bench {stamp}\n\npatient model {args.patient_model}, doctor {args.doctor}, judge {args.judge}, "
                f"runs per case {args.runs}, temperature 0.6. One run is a sample, not a measurement.\n\n" + summary_md(rows) + "\n")
    total = sum(r["doctor_cost_usd"] + r.get("judge", {}).get("cost_usd", 0) for r in rows)
    print(f"\nDONE {len(rows)} encounters, total cost ${total:.2f}, results in {outdir}")

if __name__ == "__main__":
    main()
