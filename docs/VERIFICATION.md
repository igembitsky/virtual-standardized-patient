# What was measured, and how

Everything below was run on an Apple M3 Pro, 18 GB, macOS, with Ollama 0.33.1 and
`qwen3:4b-instruct`. Nothing here is an estimate.

## The whole journey, in a real browser

Driven end to end with Playwright against the real model, not a mock.

| Step | Result |
|---|---|
| Connects and picks a model | `ready · qwen3:4b-instruct` |
| Three cases load from `cases/` | 3 cases ready |
| Case card shows 4 vital signs and the timing | 15 min consultation, 5 min note |
| Clock starts | 15:00 |
| Patient answers, opening line exact | "I have a terrible pain in my stomach that seems to be getting worse." |
| `examine abdomen` returns the case file finding | Murphy's sign positive, guarding in the right upper quadrant |
| `examine legs` gets the fixed line, not a hint | "Legs and feet: nothing abnormal." (changed 2026-09-01: Examine now offers one standard list for every case) |
| "Can I check your temperature?" reaches the patient | yes, not swallowed as an examination |
| Question counter | 3 of 9 |
| Notes carry to the note screen | yes |
| Note clock | 05:00 |
| Marking | PASS, correctly |
| Report downloads | `graham-2026-09-01-20-23.txt` |
| History saves, reopens, back button returns | yes |
| Console errors | none |

## The eight patients

All eight load, render a case card, and open with their scripted line word for word.
Each carries its own timings, vital signs and citation from its own publication.

| Patient | Complaint | Source | Consultation | Note | Questions |
|---|---|---|---|---|---|
| Jerry Graham, 55 | 1 day history of right upper quadrant pain | 8139 | 15 min | 5 min | 9 |
| Marsha Morris, 45 | 1 week history of lower abdominal pain | 8139 | 15 min | 5 min | 9 |
| Terri Travis, 60 | 6 hour history of severe upper abdominal pain | 8139 | 15 min | 5 min | 9 |
| Lou Lewis, 68 | 1 month history of trouble sleeping | 10867 | 12 min | 10 min | 6 |
| Lynette Springfield, 51 | 4 to 5 month history of hot flashes | 11146 | 15 min | 15 min | 14 |
| Robin Samuels, 30 | 3 day history of sinus and ear pressure with fever | 10837 | 15 min | 10 min | 7 |
| Joanne Davis, 37 | 6 month history of heavy vaginal bleeding | 11216 | 15 min | 10 min | 15 |
| June Bellevue, 28 | Pain with intercourse | 11001 | 15 min | 10 min | 33 |

Vital signs were checked against each source. The two telehealth cases correctly say
"not taken", because their authors say no vitals were obtained. Robin Samuels carries
five readings including oxygen saturation, which only parses because of the label fix above.

A full encounter was run on Lynette Springfield, a case with a different shape from the
abdominal pain ones: no vitals, a 15 minute note, and no physical examination.
She opened with her exact line, gave the menstrual history when asked directly,
`examine` correctly offered only "general", the counter reached 3 of 14, the note clock
started at 15:00, and the marking returned PASS against the authors' own answer,
"Menopause or perimenopause". No console errors.

## Persona behaviour, over repeated runs

| Case | Opening line exact | Hidden finding volunteered |
|---|---|---|
| Jerry Graham | 5 of 5 | 0 of 5 |
| Marsha Morris | 5 of 5 | 0 of 5, and 1 of 5 on a different probe set |
| Terri Travis | 5 of 5 | 0 of 5 |

Honest reading: the hidden finding leaks roughly once in ten open questions.
It is not zero. Adding a further instruction was tested and did not help, so it was not added.

## The conversion was checked, and it found real defects

Each converted case was read against its source by a second agent whose only brief was to find
invented clinical detail. Four of the five failed a strict check. Every finding below is fixed.

| Defect | Case | Fix |
|---|---|---|
| **She gave away the diagnosis.** Eight of thirteen scored history items were volunteered unasked, including "change of life" | Springfield | 15 lines moved behind a direct question. Retested: an open question now gets the story with no diagnosis in it |
| "No enlarged spleen", a diagnostically loaded negative the source never states | Samuels | Removed |
| Rash "on the arms" when the source's moulage is lower legs only | Samuels | Removed |
| "Rhonchi on both sides" when the source says only "lower fields" | Samuels | Removed |
| "No allergies to medicines", never stated | Davis | Removed |
| "Nothing since" after childhood chlamydia, an inference | Davis | Removed |
| Sibling given a sex the source does not give | Davis | Removed |
| Menstrual cycles "are regular", never stated | Bellevue | Removed |
| Pass words accepted "screening test" without naming the PHQ-9 | Lewis | Restricted to phq, patient health questionnaire, depression screen |
| "also accepted" promoted two differentials the source calls unlikely | Lewis | Replaced |
| Bare "thyroid" passed on the differential alone | Springfield | Removed |
| "how many" matched any question; "help\*" matched "helpful" | Springfield, Davis | Made specific |

**Attribution.** The checkers challenged the author list on four cases. Every citation was then
verified against Crossref, the authoritative record. The author lists were right, but the check
exposed an error of my own that had spread to nine files including a published page:
**the 2011 case is by Falcone J, not Falcone T.** John Falcone and Jennifer Ogilvie. Corrected
everywhere.

Trap sentences that must score nothing, across all eight cases: **3 hits out of 80**, and all
three are "tell me more about the pain" matching an open-invitation question, which is correct.

## Word matching

The marking and the question counter are word searches, so they were tested as such.

| Input | Word | Match |
|---|---|---|
| "do you feel sick beforehand" | `before` | no |
| "have you had this before" | `before` | yes |
| "is it worsening" | `worse` | no |
| "what makes it worse" | `worse` | yes |
| "megallbladder" | `gallbladder` | no |
| "gallbladder pain" | `gallbladder` | yes |
| "what aggravates it" | `aggravat*` | yes |
| "liver function tests" | `liver function` | yes |
| "kidney function" | `liver function` | no |

A word matches the whole word. A word ending in `*` matches any ending.

## Accessibility

Contrast ratios computed from the rendered page in both themes.

| | Light | Dark | Needs |
|---|---|---|---|
| Body text | 10.16 | 11.45 | 4.5 |
| Primary button | 6.50 | 8.14 | 4.5 |
| Small print | 5.09 | 6.53 | 4.5 |

- The browser's own font size setting changes the page in both themes.
- Past encounters open with the keyboard alone.
- The consultation is a live region, so replies are announced.
- One minute left is spoken, not only coloured amber.
- Abnormal vital signs carry the word "abnormal", not only amber text.

## The launcher

| Test | Result |
|---|---|
| Serves the page and the cases listing | 200 |
| Path traversal `/../../etc/passwd` | 404 |
| A sibling folder with a similar name | 404 |
| Three idle connections open, four requests | all 200, 0.07 s total |
| Leaked or zombie processes afterwards | none |

Before the fork was added, one idle connection stalled every other request.
A browser opens idle connections routinely, so this mattered.

## The adversarial review

Five independent reviewers read the code with different briefs: logic, navigation, copy,
robustness, accessibility. Every finding was then handed to a separate reviewer told to
refute it. 64 agents in total.

**59 findings raised. 52 refuted. 7 confirmed. All 7 are fixed and re-tested.**

| Confirmed finding | Fix | Proof |
|---|---|---|
| Question credit matched bare substrings, so "how many **wee**ks" ticked *colour of the urine* and "**Pleas**e" ticked *what makes it better or worse* | Whole word matching, with `*` for a deliberate stem | 0 false credits on the reviewer's 8 trap sentences; 27 of 27 real questions still score |
| A vital sign labelled `O2 sat` was dropped in silence, and a section header written `[Examine]` filed every finding into the patient's speech | Labels accept digits; headers are case insensitive | Both parse correctly |
| Opening `index.html` by double-clicking gave an empty library and a misleading error | A dedicated screen naming the launcher for each system | Shows "Start it with the launcher" |
| The clock counted ticks, so a sleeping laptop paused it | Measured against the wall clock, with the time given back after a gap | 15 simulated minutes of sleep cost 0 seconds |
| Any model was accepted, including an embedding model that cannot talk | Filtered by capability and by name | Verified in the code path |
| A malformed line in a case file vanished silently | Counted and shown on the case card in amber | 1 warning raised, the good line still parsed |

The 52 refuted findings were mostly matters of taste, or behaviour that was already correct,
or things fixed while the review was running.

## The patient rules, after a real encounter went wrong

On 1 September a real Graham encounter showed four failures: the duration came out as
"about three hours" (the story says about a day), the canned jargon line fired on a sentence
with no jargon, an open question got a five fact dump, and "does it hurt when I press?" got
"I don't know". The same nine doctor lines were then replayed against three models, with the
case file as it was and as revised, two runs each, one model loaded at a time.

| Model and file | Duration right | Jargon line misfired | Sentences to "other symptoms" | "Go ahead, doctor" to touch or press |
|---|---|---|---|---|
| qwen3 4B, old file | 0 of 2 | 2 of 2 | 7, 5 | 0 of 4 |
| qwen3 4B, revised draft file | 2 of 2 | 0 of 2 | 2, 2 | 4 of 4 |
| granite4.1 3B, old file | 0 of 2 | 0 of 2 | 6, 2 | 0 of 4, and it invented findings |
| llama3.1 8B, old file | 2 of 2 | 0 of 2 | 2, 2 | 0 of 4, invented findings, stage directions |
| llama3.1 8B, revised draft file | 2 of 2 | 0 of 2 | 1, 1 | 2 of 4 |

The draft file named fever and chills as the one thing to give to an open question. The rule
that shipped is generic, and under it the same probe gets four to six sentences. See below.

So the fixes went into the prompt, not the model. Four rules were added to `systemPrompt()`
for every patient, and the two-line jargon rule was removed from all eight case files:

1. The jargon line names examples of real medical terms and says everyday words never count.
2. A second line for confusion: "Sorry, doctor, I'm not following you", then answer.
3. To touch, press, feel or listen: "Go ahead, doctor." The page then shows `examine abdomen`.
4. To "anything else?": one more line from the story, or "No, doctor, that's all." Never a
   hidden line.

The Graham story now states the duration as a question and answer, and the pointing
direction is gone. Cost: the Graham prompt went from 806 to 962 tokens.

Re-measured with the live prompt builder, three runs:

| Probe | Result |
|---|---|
| "Any history of cholelithiasis or biliary colic?" | jargon line, 2 of 2 |
| "Anything else at all?" and "anything else you want to tell me?" | "No, doctor, that's all", 6 of 6 in 3 runs, no misfire |
| "What colour is your urine?" (hidden, direct) | tea coloured, 2 of 2 |
| Hidden facts on the 6 open questions above | 0 leaks |
| "Does it hurt when I press there?" in a real browser | "Go ahead, doctor." and the hint line, no console errors |

Two earlier wordings of the open-question rule were rejected on the same probes: one gave
away the hidden fear of an operation in 2 of 2 runs, and one fired the jargon line on
"anything else?" in 4 of 6. The rule that survived gives the patient a fixed line to fall
back on. The cost of that rule is a known one: "anything else?" now almost always gets
"No, doctor, that's all", so a learner has to ask specific questions.

Still weak: "Do you have any other symptoms?" and "Tell me more about the pain" get four to
seven sentences in most runs. Rule 1 asks for one or two. A 4B model reads a broad question
as permission to list.

## The first bench run

`bench/bench.py` plays a Claude doctor against the real patient, once per case, with no
knowledge of the answers, and has a second model judge every patient line against the case
file. Run on 1 September 2026: patient `qwen3:4b-instruct`, doctor Sonnet, judge Opus, one run
per case, about 12 minutes and 2 dollars.

| Result | Count |
|---|---|
| Cases passed | 6 of 8 |
| Patient turns judged | 75 |
| Accurate | 54 |
| Invented a fact | 10 |
| Fallback line on a plain question | 5 |
| Contradicted the file | 2 |
| Hidden line on a related question | 3, all Springfield |
| Out of persona | 1 |

The two fails. Samuels: the doctor never asked about childhood or earlier infections, the
hidden facts stayed hidden, and the immunodeficiency was missed. The case worked as designed.
Lewis: the diagnosis was right, and the doctor had already read the PHQ-9 score of 15 through
`examine depression screening`. The answer key wants that questionnaire named as a test, so a
doctor who already holds the result fails. That is a finding about the answer key.

The invented facts are mostly confident negatives about things the file does not cover:
"no nausea", "never had an ultrasound", "a normal mammogram last year". The fallback lines
added on 1 September fire on plain questions about one turn in fifteen, most often when the
doctor joins two topics in one question. One run at temperature 0.6 is a sample.

## Still not verified

1. **`start-windows.bat` and `serve.ps1` have never run on Windows.** They use only what
   Windows ships and need no administrator rights, but nobody has proved it. This includes the
   Ollama check and the model download added on 1 September.
2. **`start-linux.sh` and `start-linux.desktop` have never run on Linux.** The shell and
   Python parts of `start-linux.sh` were run on macOS and served the page correctly, but the
   desktop entry, `xdg-open`, and `ollama serve` paths are untested.
3. **Speed on a laptop without a graphics chip** has not been measured.

## The launcher, second pass (1 September 2026)

Each launcher now checks that Ollama is reachable, opens it if not, and downloads the patient
model through Ollama's `/api/pull` when none of the four accepted models is present. Then it
serves the folder and opens the browser. On macOS, with a stubbed `open`:

| Test | Result |
|---|---|
| Ollama up, model present: no download, page served, browser opened once | yes |
| `GET /` and `GET /cases/` | 200, eight files |
| Path traversal `/../../../etc/passwd` | 404 |
| Second copy started while the first runs | dies with "already running", browser opened to the running copy |
| `start-linux.sh` on macOS: same four checks | all pass, busy port reported and exits |
| Progress parser on synthetic `/api/pull` output | 0%, 50%, then "Download complete" |
| `POST /api/pull` for a model already present | `success` in under two seconds, nothing loaded |
| Shell, Perl, and Python parts parse | yes |

The Windows PowerShell part could not be parsed here: no PowerShell on this machine.
