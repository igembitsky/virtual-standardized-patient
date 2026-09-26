# The evaluation harness

Run it after any change to a case file, to `systemPrompt()` in `index.html`, or to the model.

```
python3 bench/eval.py                                  # both suites, every case, about an hour
python3 bench/eval.py --cases samuels                  # one case
python3 bench/eval.py --suite examiner                 # one suite
python3 bench/eval.py --patient-model qwen3.5:4b       # the same test for another model
```

Needs Ollama running with the patient model, `node`, and a logged-in `claude` command. The
`claude` command uses your Claude subscription. Cases run one after another.

Results land in `bench/results/eval-<timestamp>/`: `report.md` on top, and one JSON per case
and suite with the full transcript, the examiner's script, and the judge's notes. Each result
records a hash of the system prompt, so runs can be compared across prompt versions. The
results folder is not committed.

## What is real and what is Claude

- The **patient** is real: the prompt from `index.html`, the same Ollama request as the page.
- The **counting and marking** are real: `page.js` runs the page's own jargon catch, checklist
  credit, examination matcher and note marking from `index.html`. Nothing is a copy.
- The **student**, the **examiner** and the **judge** are Claude, through `claude -p`.

## Suite 1: the student

A novice. It sees only the door card and one line of instructions: talk to the patient, take a
history, examine if you want, write three diagnoses and three tests. It plays the whole
encounter against the case's clock.

This suite shows what a learner meets. A fail here is a finding about the student, not about
the patient. The patient is judged on every reply all the same.

## Suite 2: the examiner

An expert who knows the whole case writes a fresh test script for every run, so the wording
changes each time:

- every checklist item, asked in natural words, to check the page counts it
- every "only if asked" fact, asked directly, to check the patient gives it
- the main story facts, asked directly
- things that are not in the case, to check the patient says a plain no
- open questions, to check the patient leaks nothing
- the examinations, in the short words a student types
- three correct notes and two wrong notes in varied words, to check the marking
- five more ways to write the diagnosis, and varied names for each test

The script is asked in encounters of up to 18 questions, the size of a real consultation.

## The judge

Claude reads the case file, the prompt and the transcript, and gives every patient reply one
verdict:

| Verdict | Meaning |
|---|---|
| correct | follows the protocol |
| withheld | asked about a fact in the case and did not give it |
| inaccurate | contradicts the case file |
| invented | adds a fact that is not in the case |
| leaked | gives an "only if asked" fact nobody asked for |
| canned_misfire | the "I don't know that word" line on plain words |
| off_persona | breaks role, lists, or runs far too long |

## Reading the report

The headline table gives one number per question: does the patient follow its protocol, does it
give what is asked, does it deny what is absent, and does the page count what it should. The
findings list every reply and every count that went wrong, with the words that caused it.

One run at temperature 0.6 is a sample. Compare two runs before you call a change better.

## The probe battery

`probe.py` is an older, cheaper loop. It runs prompt rule variants against the real patient over
a long conversation of tagged clinical questions and scores the replies with word rules, with no
Claude at all. `V0` is always the live prompt.

```
python3 bench/probe.py --variants V0 --runs 2
```

Probes live in `bench/probes/`.
