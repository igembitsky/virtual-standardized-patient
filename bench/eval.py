#!/usr/bin/env python3
"""The evaluation harness. Two suites against the real patient, the real prompt and the
page's own counting and marking (through bench/page.js):

  student   A Claude medical student who sees only the door card and basic instructions.
            It interviews, examines and writes a note, as a novice at a first OSCE would.
            A Claude judge then checks every patient reply against the case file.
            Shows what a learner meets. A fail here is about the student, not the patient.

  examiner  A Claude examiner who knows the whole case writes a test script: every checklist
            item and every "only if asked" fact asked in fresh, varied words, questions about
            things not in the case, open questions, varied examination names, and varied notes.
            The patient answers the script. A Claude judge checks each reply against what it
            should have said. The page's own code checks that every question, examination and
            note is counted as it should be.

  python3 bench/eval.py                                   both suites, every case, once
  python3 bench/eval.py --suite examiner --cases samuels
  python3 bench/eval.py --patient-model qwen3.5:4b        the same test for another model

Needs Ollama with the patient model, node, and a logged-in claude CLI (it uses your
subscription). Results go to bench/results/eval-<timestamp>/, with report.md on top.
Standard library only.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HTML = os.path.join(ROOT, "index.html")
OLLAMA = "http://127.0.0.1:11434"
CLAUDE_MIN = ["--no-session-persistence", "--output-format", "json",
              "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
              "--disable-slash-commands", "--setting-sources", ""]
SESSION_MAX = 18   # examiner questions per conversation, near what a real 15 minute encounter holds

# ============================================================ prompts

STUDENT_SYS = """You are a medical student at a standardized patient exam. You get the door card
and these instructions only: talk to the patient, take a history, examine the patient if you
want to, then write three diagnoses, most likely first, and three tests. You want to pass.
Talk the way a student talks to a patient.
Each turn reply with JSON only, one of:
{"action":"ask","question":"one question, as you would say it to the patient"}
{"action":"examine","part":"the body part or examination you want"}
{"action":"finish","diagnoses":["most likely","second","third"],"tests":["test","test","test"]}
One question per turn. The turn count is your clock."""

STUDENT_SCHEMA = {"type": "object", "properties": {
    "action": {"type": "string", "enum": ["ask", "examine", "finish"]},
    "question": {"type": "string"}, "part": {"type": "string"},
    "diagnoses": {"type": "array", "items": {"type": "string"}},
    "tests": {"type": "array", "items": {"type": "string"}}},
    "required": ["action"]}

PLAN_SYS = """You are an expert OSCE examiner. You get a case file for a simulated patient that a
small local language model plays. Write a test script that checks the patient and the marking.
Ask everything in fresh words, the way different clinicians would. Never copy a line from the
case file. Use plain English a patient understands, no medical terms, except where a probe
says otherwise.

probes: the questions, in the order of a natural interview.
- For every [QUESTIONS] checklist item, at least one question that a clinician would naturally
  ask for it. Set "credits" to that item's label, exactly. Phrase it naturally. Do not add or
  avoid the listed words on purpose; the test is whether natural phrasing is counted.
- For every "(only if asked)" line, one direct question about that exact thing. Close lines on
  the same topic may share one question. expect "reveal". "target" is the line, word for word.
- For the most important ordinary [STORY] lines, 4 to 6 direct questions. expect "reveal".
- 3 or 4 questions about plausible things that are nowhere in the case. expect "deny".
  target "NOT IN CASE".
- 2 open questions such as "anything else going on?". expect "open". target "OPEN".
- A question may credit a checklist item and reveal a fact at the same time.
exams: for every key in [EXAMINE], one to three words a student would type into the
Examine search box, different from the key: a synonym, a body part, or an instrument (for
example "otoscope" or "eardrum" for ears).
correct_notes: 3 notes an expert who got it right would write. Vary how the most likely
diagnosis is written: abbreviation, synonym, American or British spelling, more or less detail.
Tests from the answer key, in varied words.
wrong_notes: 2 notes from a student who missed it: the most common wrong answer and its tests.
They must not name the correct diagnosis or any accepted diagnosis.
top_dx_variants: 5 more ways a clinician could write the most likely diagnosis.
test_variants: for every test in the answer key, 1 or 2 varied phrasings, with "key" set to
the answer key test.
Reply with JSON only."""

NOTE_SCHEMA = {"type": "object", "properties": {
    "dx": {"type": "array", "items": {"type": "string"}},
    "tx": {"type": "array", "items": {"type": "string"}}}, "required": ["dx", "tx"]}

PLAN_SCHEMA = {"type": "object", "properties": {
    "probes": {"type": "array", "items": {"type": "object", "properties": {
        "question": {"type": "string"}, "target": {"type": "string"},
        "expect": {"type": "string", "enum": ["reveal", "deny", "open"]},
        "credits": {"type": "string"}}, "required": ["question", "target", "expect", "credits"]}},
    "exams": {"type": "array", "items": {"type": "object", "properties": {
        "key": {"type": "string"}, "phrasing": {"type": "string"}}, "required": ["key", "phrasing"]}},
    "correct_notes": {"type": "array", "items": NOTE_SCHEMA},
    "wrong_notes": {"type": "array", "items": NOTE_SCHEMA},
    "top_dx_variants": {"type": "array", "items": {"type": "string"}},
    "test_variants": {"type": "array", "items": {"type": "object", "properties": {
        "key": {"type": "string"}, "phrasing": {"type": "string"}}, "required": ["key", "phrasing"]}}},
    "required": ["probes", "exams", "correct_notes", "wrong_notes", "top_dx_variants", "test_variants"]}

VERDICTS = ["correct", "withheld", "inaccurate", "invented", "leaked", "canned_misfire", "off_persona"]
JUDGE_SYS = """You audit a simulated patient that a small local language model plays in a teaching
clinic. The protocol: the patient says a fact from the case file only when the doctor asks about
that thing, says "(only if asked)" facts only to a direct question about that exact thing, says no
to anything that is not in the case, stays in character, and speaks briefly in plain words.
You get the case file, the system prompt the patient ran under, and the transcript.
Judge EVERY patient turn with one verdict:
- correct: follows the protocol. Gives what was asked, or a harmless paraphrase. A plain no
  to something not in the case. "Go ahead, doctor" to a request to touch or examine.
- withheld: the doctor asked about something that IS in the case file, and the patient did
  not give it, or said no or "I don't know"
- inaccurate: contradicts the case file
- invented: adds a fact that is not in the case file and cannot be inferred from it
  (a plain no to a question about something absent is correct, not invented)
- leaked: gives an "(only if asked)" fact that the doctor did not ask about
- canned_misfire: the "I don't know that word" or "not following you" line when the doctor's
  words were plain and clear
- off_persona: bullet points, breaks role, mentions being a model, or runs far too long
When a turn shows what the examiner expected, judge against it, but the case file wins.
Be strict on facts, lenient on words. Reply with JSON only."""

JUDGE_SCHEMA = {"type": "object", "properties": {
    "turns": {"type": "array", "items": {"type": "object", "properties": {
        "turn": {"type": "integer"},
        "verdict": {"type": "string", "enum": VERDICTS},
        "note": {"type": "string"}}, "required": ["turn", "verdict", "note"]}},
    "overall": {"type": "string"}}, "required": ["turns", "overall"]}

# ============================================================ the three outside parts

def load_case(path):
    out = subprocess.run(["node", os.path.join(HERE, "page.js"), HTML, path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)

def page_check(path, req):
    out = subprocess.run(["node", os.path.join(HERE, "page.js"), HTML, path, "--check"],
                         input=json.dumps(req), capture_output=True, text=True, check=True).stdout
    return json.loads(out)

def patient_say(model, messages):
    # The same request the page sends, except streaming.
    body = json.dumps({"model": model, "messages": messages, "stream": False, "think": False, "keep_alive": "20m",
                       "options": {"temperature": 0.6, "num_ctx": 8192, "num_predict": 300}}).encode()
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r: d = json.load(r)
    txt = re.sub(r"<think>[\s\S]*?</think>", "", d["message"]["content"]).strip()
    return txt, round(time.time() - t0, 1)

def claude(model, system, prompt, schema, timeout=600):
    cmd = ["claude", "-p", "--model", model, *CLAUDE_MIN, "--json-schema", json.dumps(schema),
           "--system-prompt", system, "--tools", ""]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    try: d = json.loads(p.stdout)
    except Exception: raise RuntimeError("claude did not return JSON: " + (p.stdout or p.stderr)[:300])
    if d.get("is_error"): raise RuntimeError("claude error: " + str(d.get("result"))[:300])
    out = d.get("structured_output")
    if out is None:
        try: out = json.loads(d.get("result") or "")
        except Exception: raise RuntimeError("no structured output: " + str(d.get("result"))[:300])
    return out

def opening_msgs(c):
    return [{"role": "system", "content": c["system"]},
            {"role": "user", "content": "Good day. I am the doctor. Why are you here today?"},
            {"role": "assistant", "content": c["opening"]}]

def jargon_line(word):
    return f'I don\'t know that word, doctor. What does "{word}" mean?'

# ============================================================ judge

def judge(c, turns, model):
    """turns: dicts with role doctor/patient/examination; a patient turn may carry 'expect'."""
    lines, k = [], 0
    for t in turns:
        if t["role"] == "patient":
            k += 1
            extra = ""
            if t.get("jargon"): extra = "  [the page itself said this, because of a medical word]"
            elif t.get("expect"):
                extra = f"  [examiner expected: {t['expect']}; target: {t['target']}]"
            lines.append(f"Patient turn {k}: {t['text']}{extra}")
        elif t["role"] == "doctor": lines.append(f"Doctor: {t['text']}")
        elif t["role"] == "session": lines.append("--- a new encounter starts; the patient opens with the opening line ---")
        else: lines.append(f"Examination (from the file, not the model): {t['text']}")
    prompt = ("CASE FILE\n" + c["raw"] + "\n\nSYSTEM PROMPT THE PATIENT RAN UNDER\n" + c["system"] +
              "\n\nTRANSCRIPT\n" + "\n".join(lines) + f"\n\nThere are {k} patient turns. Judge each one.")
    pts = [t for t in turns if t["role"] == "patient"]
    for attempt in range(2):   # a judge that skips turns gets one more try
        out = claude(model, JUDGE_SYS, prompt, JUDGE_SCHEMA)
        got = {t["turn"]: t for t in out.get("turns", [])}
        if all(i in got for i in range(1, k + 1)): break
    for i, t in enumerate(pts, 1):
        v = got.get(i)
        if t.get("jargon") and v is None: v = {"verdict": "correct", "note": "page jargon line"}
        t["verdict"] = (v or {}).get("verdict", "unjudged"); t["note"] = (v or {}).get("note", "")
    counts = {}
    for t in pts: counts[t["verdict"]] = counts.get(t["verdict"], 0) + 1
    return counts, out.get("overall", "")

# ============================================================ suite 1: the student

def door_card(c, cap):
    vit = "; ".join(f"{v['label']} {v['value']}" for v in c["vitals"]) or "not taken"
    return (f"DOOR CARD\nPatient: {c['name']}, age {c['age']}, {c['occupation']}.\nSetting: {c['setting']}.\n"
            f"Complaint: {c['complaint']}.\nVital signs: {vit}.\nTask: {c['task']}\nYou have {cap} turns.")

def fmt(turns):
    who = {"doctor": "You", "patient": "Patient", "examination": "Examination"}
    return "\n".join(f"{who[t['role']]}: {t['text']}" for t in turns) or "(nothing yet)"

def run_student(c, path, a):
    cap = int(c.get("consultMins") or 15)
    card = door_card(c, cap)
    msgs = opening_msgs(c)
    turns = [{"role": "doctor", "text": "Good day. I am the doctor. Why are you here today?"},
             {"role": "patient", "text": c["opening"], "opening": True}]
    asked, dx, tx, error = [], [], [], None
    t0 = time.time()
    for n in range(1, cap + 2):
        last = n >= cap
        prompt = (card + "\n\nTRANSCRIPT SO FAR\n" + fmt(turns) + f"\n\nTurn {min(n, cap)} of {cap}. " +
                  ("This is your last turn. action must be finish." if last else "Reply with JSON."))
        try: act = claude(a.student, STUDENT_SYS, prompt, STUDENT_SCHEMA, timeout=300)
        except Exception as e: error = str(e); break
        kind = act.get("action")
        if kind == "ask" and act.get("question"):
            q = act["question"].strip()
            chk = page_check(path, {"ask": [q]})["ask"][0]
            turns.append({"role": "doctor", "text": q})
            asked.append(q)
            if chk["jargon"]:
                line = jargon_line(chk["jargon"])
                msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": line}]
                turns.append({"role": "patient", "text": line, "jargon": True}); continue
            msgs.append({"role": "user", "content": q})
            try: reply, sec = patient_say(a.patient_model, msgs)
            except Exception as e: error = "patient: " + str(e); break
            msgs.append({"role": "assistant", "content": reply})
            turns.append({"role": "patient", "text": reply, "sec": sec})
        elif kind == "examine":
            part = act.get("part", "")
            ex = page_check(path, {"examine": [part]})["examine"][0]
            turns.append({"role": "doctor", "text": "examine " + part})
            turns.append({"role": "examination", "text": (ex["name"] + ": " if ex["name"] else "") + ex["finding"]})
        elif kind == "finish" or last:
            dx = [s.strip() for s in (act.get("diagnoses") or []) if s and s.strip()][:3]
            tx = [s.strip() for s in (act.get("tests") or []) if s and s.strip()][:3]
            break
    chk = page_check(path, {"ask": asked, "notes": [{"dx": dx, "tx": tx}]})
    # the page counts a question only once the patient answered; jargon questions get no credit
    covered = sorted({l for r in chk["ask"] for l in r["credits"]})
    note = chk["notes"][0]
    judged = [t for t in turns if not t.get("opening")]
    counts, overall = judge(c, judged, a.judge) if judged else ({}, "")
    return {"suite": "student", "case": c["id"], "name": c["name"],
            "turns_used": sum(1 for t in turns if t["role"] == "doctor") - 1, "turn_cap": cap,
            "covered": covered, "total": len(c["questions"]),
            "missed": [q["label"] for q in c["questions"] if q["label"] not in covered],
            "dx": dx, "tests": tx, **note, "verdicts": counts, "overall": overall,
            "transcript": turns, "error": error, "seconds": round(time.time() - t0)}

# ============================================================ suite 2: the examiner

def run_examiner(c, path, a):
    t0 = time.time()
    labels = [q["label"] for q in c["questions"]]
    plan = claude(a.planner, PLAN_SYS, "CASE FILE\n" + c["raw"] +
                  "\n\nCHECKLIST LABELS, use exactly one of these or \"\" in credits:\n" +
                  "\n".join("- " + l for l in labels), PLAN_SCHEMA)
    probes = plan["probes"]
    chk = page_check(path, {
        "ask": [p["question"] for p in probes],
        "examine": [e["phrasing"] for e in plan["exams"]],
        "notes": [n for n in plan["correct_notes"]] + [n for n in plan["wrong_notes"]] +
                 [{"dx": [v], "tx": []} for v in plan["top_dx_variants"]] +
                 [{"dx": [], "tx": [v["phrasing"]]} for v in plan["test_variants"]]})

    # the interview, in sessions the length of a real encounter
    turns, error = [], None
    for s in range(0, len(probes), SESSION_MAX):
        msgs = opening_msgs(c)
        turns.append({"role": "session"})
        for i in range(s, min(s + SESSION_MAX, len(probes))):
            p, r = probes[i], chk["ask"][i]
            turns.append({"role": "doctor", "text": p["question"]})
            base = {"role": "patient", "probe": i, "expect": p["expect"], "target": p["target"]}
            if r["jargon"]:
                line = jargon_line(r["jargon"])
                msgs += [{"role": "user", "content": p["question"]}, {"role": "assistant", "content": line}]
                turns.append({**base, "text": line, "jargon": r["jargon"]}); continue
            msgs.append({"role": "user", "content": p["question"]})
            try: reply, sec = patient_say(a.patient_model, msgs)
            except Exception as e: error = "patient: " + str(e); break
            msgs.append({"role": "assistant", "content": reply})
            turns.append({**base, "text": reply, "sec": sec})
            print(f"   {p['expect'][:3]} Q: {p['question']}\n       A: {reply}", flush=True)
        if error: break
    counts, overall = judge(c, turns, a.judge)

    # counting by the page's own code
    credit_rows = []
    for p, r in zip(probes, chk["ask"]):
        if p["credits"]:
            credit_rows.append({"question": p["question"], "label": p["credits"],
                                "counted": p["credits"] in r["credits"], "jargon": r["jargon"]})
    covered = sorted({l for r in chk["ask"] for l in r["credits"]})
    exam_rows = []
    for e, r in zip(plan["exams"], chk["examine"]):
        want = (c["examine"].get(e["key"].lower()) or "").strip()
        exam_rows.append({"key": e["key"], "phrasing": e["phrasing"], "got": r["finding"],
                          "ok": bool(want) and r["finding"].strip() == want})
    notes = chk["notes"]; k = 0
    def take(n):
        nonlocal k
        out = notes[k:k + n]; k += n; return out
    correct = [{"note": n, **m} for n, m in zip(plan["correct_notes"], take(len(plan["correct_notes"])))]
    wrong = [{"note": n, **m} for n, m in zip(plan["wrong_notes"], take(len(plan["wrong_notes"])))]
    topdx = [{"phrasing": v, "counted": m["dxHit"]} for v, m in zip(plan["top_dx_variants"], take(len(plan["top_dx_variants"])))]
    tests = [{"key": v["key"], "phrasing": v["phrasing"], "counted": m["txHit"]}
             for v, m in zip(plan["test_variants"], take(len(plan["test_variants"])))]
    return {"suite": "examiner", "case": c["id"], "name": c["name"], "plan": plan,
            "verdicts": counts, "overall": overall, "transcript": turns,
            "credit": credit_rows, "covered": covered, "total": len(labels),
            "missed": [l for l in labels if l not in covered],
            "exams": exam_rows, "correct_notes": correct, "wrong_notes": wrong,
            "top_dx": topdx, "tests": tests, "error": error, "seconds": round(time.time() - t0)}

# ============================================================ report

def pct(n, d): return f"{n}/{d}" + (f" ({round(100 * n / d)}%)" if d else "")

def bad_turns(r):
    return [t for t in r["transcript"] if t["role"] == "patient" and t.get("verdict") not in (None, "correct")]

def report(rows, a, stamp):
    S = [r for r in rows if r["suite"] == "student"]
    E = [r for r in rows if r["suite"] == "examiner"]
    L = [f"# Evaluation {stamp}", "",
         f"Patient model `{a.patient_model}`. Student `{a.student}`, examiner `{a.planner}`, judge `{a.judge}`. "
         "Temperature 0.6. One run per case is a sample, not a measurement.", ""]
    allp = [t for r in rows for t in r["transcript"] if t["role"] == "patient" and not t.get("opening")]
    ok = sum(1 for t in allp if t.get("verdict") == "correct")
    L += ["## Headline", "", "| Measure | Result |", "|---|---|",
          f"| Patient replies that follow the protocol, both suites | {pct(ok, len(allp))} |"]
    if E:
        rev = [t for r in E for t in r["transcript"] if t.get("expect") == "reveal" and not t.get("jargon")]
        den = [t for r in E for t in r["transcript"] if t.get("expect") == "deny"]
        opn = [t for r in E for t in r["transcript"] if t.get("expect") == "open"]
        cr = [x for r in E for x in r["credit"]]
        ex = [x for r in E for x in r["exams"]]
        cn = [x for r in E for x in r["correct_notes"]]; wn = [x for r in E for x in r["wrong_notes"]]
        td = [x for r in E for x in r["top_dx"]]
        L += [f"| Asked facts given (examiner) | {pct(sum(t.get('verdict') == 'correct' for t in rev), len(rev))} |",
              f"| Absent things denied cleanly | {pct(sum(t.get('verdict') == 'correct' for t in den), len(den))} |",
              f"| Open questions answered without a leak | {pct(sum(t.get('verdict') == 'correct' for t in opn), len(opn))} |",
              f"| Checklist questions counted, varied words | {pct(sum(x['counted'] for x in cr), len(cr))} |",
              f"| Examinations found, varied words | {pct(sum(x['ok'] for x in ex), len(ex))} |",
              f"| Correct notes that pass | {pct(sum(x['pass'] for x in cn), len(cn))} |",
              f"| Wrong notes that fail | {pct(sum(not x['pass'] for x in wn), len(wn))} |",
              f"| Most likely diagnosis, varied words, counted | {pct(sum(x['counted'] for x in td), len(td))} |"]
    if S:
        L += [f"| Student passes (about the student, not the patient) | {pct(sum(r['pass'] for r in S), len(S))} |"]
    L += [""]

    if S:
        L += ["## Suite 1: the student", "",
              "| Patient | Turns | Checklist | Pass | " + " | ".join(VERDICTS) + " |",
              "|---|---|---|---|" + "---|" * len(VERDICTS)]
        for r in S:
            v = r["verdicts"]
            L.append(f"| {r['name']} | {r['turns_used']}/{r['turn_cap']} | {len(r['covered'])} of {r['total']} | "
                     f"{'PASS' if r['pass'] else 'fail'} ({'y' if r['dxHit'] else 'n'}/{'y' if r['txHit'] else 'n'}) | " +
                     " | ".join(str(v.get(x, 0)) for x in VERDICTS) + " |" + (f" ERROR {r['error'][:80]}" if r["error"] else ""))
        L += [""]
        for r in S:
            L += [f"**{r['name']}.** Diagnoses: {'; '.join(r['dx']) or '(none)'}. Tests: {'; '.join(r['tests']) or '(none)'}. "
                  f"Not asked: {', '.join(r['missed']) or 'nothing'}.", ""]
    if E:
        L += ["## Suite 2: the examiner", "",
              "| Patient | Facts given | Denials | Open | Checklist counted | Exams | Correct pass | Wrong fail | Dx variants | " +
              " | ".join(VERDICTS) + " |", "|---|---|---|---|---|---|---|---|---|" + "---|" * len(VERDICTS)]
        for r in E:
            T = r["transcript"]; v = r["verdicts"]
            f = lambda e: pct(sum(t.get("verdict") == "correct" for t in T if t.get("expect") == e and not t.get("jargon")),
                              sum(1 for t in T if t.get("expect") == e and not t.get("jargon")))
            L.append(f"| {r['name']} | {f('reveal')} | {f('deny')} | {f('open')} | "
                     f"{sum(x['counted'] for x in r['credit'])}/{len(r['credit'])} | {sum(x['ok'] for x in r['exams'])}/{len(r['exams'])} | "
                     f"{sum(x['pass'] for x in r['correct_notes'])}/{len(r['correct_notes'])} | "
                     f"{sum(not x['pass'] for x in r['wrong_notes'])}/{len(r['wrong_notes'])} | "
                     f"{sum(x['counted'] for x in r['top_dx'])}/{len(r['top_dx'])} | " +
                     " | ".join(str(v.get(x, 0)) for x in VERDICTS) + " |" + (f" ERROR {r['error'][:80]}" if r["error"] else ""))
        L += [""]

    L += ["## Findings", "", "Every patient reply that did not follow the protocol, and everything the page did not count.", ""]
    for r in rows:
        items = []
        for t in bad_turns(r):
            q = ""
            i = r["transcript"].index(t)
            if i and r["transcript"][i - 1]["role"] == "doctor": q = r["transcript"][i - 1]["text"]
            items.append(f"- **{t['verdict']}**. Q: \"{q}\" A: \"{t['text']}\" {t.get('note', '')}")
        if r["suite"] == "examiner":
            for x in r["credit"]:
                if not x["counted"]:
                    items.append(f"- **not counted**: \"{x['question']}\" should count for *{x['label']}*" +
                                 (f" (jargon catch fired on \"{x['jargon']}\")" if x["jargon"] else ""))
            for l in r["missed"]:
                items.append(f"- **checklist item never counted** in the whole script: *{l}*")
            for x in r["exams"]:
                if not x["ok"]: items.append(f"- **examination missed**: \"examine {x['phrasing']}\" (for {x['key']}) gave \"{x['got']}\"")
            for x in r["correct_notes"]:
                if not x["pass"]: items.append(f"- **correct note failed**: dx {x['note']['dx']}, tests {x['note']['tx']}")
            for x in r["wrong_notes"]:
                if x["pass"]: items.append(f"- **wrong note passed**: dx {x['note']['dx']}, tests {x['note']['tx']}")
            for x in r["top_dx"]:
                if not x["counted"]: items.append(f"- **diagnosis wording not counted**: \"{x['phrasing']}\"")
            for x in r["tests"]:
                if not x["counted"]: items.append(f"- test wording not counted (fine if another test counts): \"{x['phrasing']}\" for {x['key']}")
        if r.get("error"): items.append(f"- **error**: {r['error']}")
        if items:
            L += [f"### {r['name']}, {r['suite']}", ""] + items + [""]
    return "\n".join(L) + "\n"

# ============================================================ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="all", choices=["all", "student", "examiner"])
    ap.add_argument("--cases", default="", help="comma separated case ids, default all")
    ap.add_argument("--patient-model", default="qwen3:4b-instruct")
    ap.add_argument("--student", default="sonnet")
    ap.add_argument("--planner", default="opus")
    ap.add_argument("--judge", default="opus")
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    a = ap.parse_args()
    files = sorted(f for f in os.listdir(os.path.join(ROOT, "cases")) if f.endswith(".txt"))
    want = [s.strip() for s in a.cases.split(",") if s.strip()]
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    outdir = os.path.join(a.out, "eval-" + stamp); os.makedirs(outdir, exist_ok=True)
    suites = ["student", "examiner"] if a.suite == "all" else [a.suite]
    rows = []
    for f in files:
        path = os.path.join(ROOT, "cases", f)
        c = load_case(path)
        if want and c["id"] not in want: continue
        for s in suites:
            print(f"== {c['name']}, {s}", flush=True)
            try:
                r = (run_student if s == "student" else run_examiner)(c, path, a)
            except Exception as e:
                print("   FAILED:", e, flush=True); continue
            r["prompt_sha"] = hashlib.sha256(c["system"].encode()).hexdigest()[:12]
            r["patient_model"] = a.patient_model
            rows.append(r)
            print(f"   verdicts {r['verdicts']}, {r['seconds']}s", flush=True)
            json.dump(r, open(os.path.join(outdir, f"{c['id']}-{s}.json"), "w"), indent=1, ensure_ascii=False)
            open(os.path.join(outdir, "report.md"), "w").write(report(rows, a, stamp))
    print(f"\nDONE {len(rows)} runs. Report: {os.path.join(outdir, 'report.md')}")

if __name__ == "__main__":
    main()
