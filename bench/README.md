# Bench: a Claude doctor against the real patient

`bench.py` plays one consultation per case with no knowledge of the answers, then has a second
model judge every patient line against the case file. It exists to answer two questions after
any change to a case file or to `systemPrompt()` in `index.html`:

1. Can a competent doctor pass this case in one attempt, with these questions and these answer words?
2. Did the patient say anything inaccurate, invented, leaked, canned, or out of character?

## What it uses

- The **real prompt**. `case.js` runs the parser and prompt builder from `index.html` itself.
- The **real patient**. The same Ollama call, model, and options as the page.
- The **real marking**. Question credit and pass rules are ports of the page's own word matching.
- A **Claude doctor** through `claude -p`, which sees only the door card: name, age, setting,
  complaint, vital signs, task, and the list of examinable parts. Never the story or the answers.
- A **Claude judge** that sees everything and labels each patient turn:
  accurate, inaccurate, invented, leaked, canned_misfire, off_persona.

## Run it

```
python3 bench/bench.py                         # every case, once
python3 bench/bench.py --cases graham --runs 3
python3 bench/bench.py --doctor haiku --judge sonnet --no-judge
```

Needs Ollama running with the patient model, `node`, and a logged-in `claude` CLI.
Cases run one after another. The turn cap is the case's consultation minutes.

Results land in `bench/results/<timestamp>/`: one JSON per encounter with the full transcript
and the judge's notes, plus `summary.md`. Each result records a hash of the system prompt, so
two runs can be compared across prompt versions. The folder is not committed.

Cost is about 1 cent per doctor turn with Sonnet, so a full run of eight cases is roughly
one to two dollars and ten to fifteen minutes. One run at temperature 0.6 is a sample.
Use `--runs` for a measurement.

## Reading the result

A fail is a finding about the case file as much as about the doctor. If a good doctor fails,
either the patient held back a fact a direct question should have released, or the pass words
in `[ANSWER]` are too narrow, or the doctor never asked. The transcript shows which.

## The probe battery

`probe.py` is the free, local loop. It runs prompt rule variants against the real patient over
a long conversation of tagged clinical questions and scores the replies with word rules.
`V0` is always the live prompt in `index.html`. The other variants replace the jargon,
open-question and unknown-fact rules; they were written against the 1 September prompt.

```
python3 bench/probe.py --variants V0 --runs 2          # check the live prompt
python3 bench/probe.py --runs 3                         # all variants, about 40 minutes
```

Probes live in `bench/probes/`: regression probes by hand, clinical questions written by
Claude, and doctor lines harvested from earlier bench runs. The scorer cannot see invented
detail reliably. Use the Claude judge in `bench.py` for that.
