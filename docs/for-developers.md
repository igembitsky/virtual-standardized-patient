[← Back to the README](../README.md)

# For developers

## The files


| File or folder | What it is |
|---|---|
| `Start on Mac.app` | Mac launcher. A small app whose one file, `Contents/MacOS/start`, is a shell script that runs `app/server.pl` |
| `Start on Windows.bat` | Windows launcher. Runs `app/server.ps1` with no window |
| `Start on Linux.desktop` | Linux launcher. Runs `app/server.py` |
| `app/index.html` | The whole program: page, styles, and script |
| `app/cases/` | Eight case files |
| `app/server.pl`, `app/server.ps1`, `app/server.py` | The same small web server three times, in the language each system already has: Perl on a Mac, PowerShell on Windows, Python on Linux |
| `CHANGELOG.md` | The versions, and what changed in each |
| `VERSION` | The latest version number. The page reads it from GitHub to offer an update |
| `docs/` | The install pages, and `VERIFICATION.md`, what was measured and how |
| `bench/` | Plays a Claude doctor against the patient and judges every line |

`.gitattributes` leaves `docs/`, `bench/`, `.github/` and `VERSION` out of GitHub's
**Download ZIP**, so participants get only what they need to run it.

What each server does:

- Serves the `app` folder on `127.0.0.1:8756`, to this computer only. `GET /cases/` returns
  a JSON list of the case files, so a new case appears on reload.
- Opens Ollama if it is installed and not running, then opens the browser.
- `GET /alive?tab=<id>` every 15 seconds from each open tab, and `POST /bye?tab=<id>` when a
  tab closes. The server stops 10 seconds after the last tab closes, 4 minutes after it last
  heard from a tab, or 2 minutes after starting if no tab ever opened. `POST /quit` stops it
  at once. On the way out it unloads the patient model from Ollama with `keep_alive: 0`.
- `GET /update` answers `can`. `POST /update` downloads the ZIP, checks it holds
  `app/index.html` and `app/cases/`, and copies it over the folder.
- `VSP_ZIP` overrides where the update comes from, for testing. `VSP_OPEN` (Mac) overrides
  the command that opens the browser.

To release a new version: change `version:` near the top of the script in `app/index.html`,
the number in `VERSION`, and `CFBundleShortVersionString` in `Start on Mac.app/Contents/Info.plist`,
and add an entry to `CHANGELOG.md`.

- The page talks to Ollama at `127.0.0.1:11434` through `/api/tags`, `/api/chat`, and, on
  the first run, `/api/pull`.
- To test a change to a case or to `systemPrompt()`, run `python3 bench/bench.py`. See
  [`bench/README.md`](../bench/README.md). It needs a logged-in `claude` command and costs about
  a dollar a run.

## Make it your own


Everything is in one text file, `app/index.html`. You can change any of it.

**A larger model.** Larger models keep hidden facts better and speak more naturally. Any model
in the [Ollama library](https://ollama.com/library) will work. As of September 2026, these are
worth trying:

| Memory | Models to try | Command |
|---|---|---|
| 8 GB | `qwen3:4b-instruct` | already set |
| 16 GB or more | `qwen3:8b`, `gemma3:12b` | `ollama pull qwen3:8b` |
| 32 GB or more | `qwen3:14b`, `qwen3:30b-a3b`, `gemma3:27b` | `ollama pull qwen3:14b` |

Only `qwen3:4b-instruct` has been tested with this program. The Qwen 3 models are listed first
because they are from the same family, so the patient rules are most likely to carry over.
`llama3.1:8b` was tested and did worse: it added stage directions and invented findings.

To compare open-weight models by size and score:

- [Artificial Analysis](https://artificialanalysis.ai/models/open-source), filter by open
  weights and by size.
- [Hugging Face](https://huggingface.co/models?pipeline_tag=text-generation&sort=trending),
  the largest catalogue of open-weight models.
- [LMArena](https://lmarena.ai/leaderboard), rankings from blind human votes.

Run the pull command in a terminal. Then open `app/index.html` in a text editor, find the line
`model: "qwen3:4b-instruct"` near the top of the script, and put the new name there.

**A hosted model.** The program uses Ollama's standard interface, so it can talk to any server
that uses it. Ollama offers cloud models with a free account: run `ollama signin`, pull a cloud
model, and set `model:` to its name. Or set `ollama:` in the same block to another server.
With a hosted model, your questions leave your computer.

**The prompt.** The patient's rules are in one function, `systemPrompt()` in `app/index.html`. It
sets how the patient talks, what it holds back, and how it answers an open question. In
testing, every problem with the patient was fixed in the prompt or the case file, not by
changing the model.

**Your own patients.** Press **Write your own patient** inside the program. It gives you
instructions to paste into any AI assistant with your source case. The assistant writes the
case file. Put the file in the `app/cases` folder and reload the page. The format is documented in
`app/cases/graham.txt`. Cases in other languages work.

**Other tools.** The same three parts, a text file for the content, a prompt for the model, and
program code for everything that must be correct, can make:

- A tutor that asks the learner questions instead of answering them.
- An examiner that marks a written note against a checklist.
- A flashcard maker that turns a lecture handout into a revision deck.
- A translation of the cases into the language your students speak.

[← Back to the README](../README.md)
