[← Back to the README](../README.md)

# For developers

## The files


| File or folder | What it is |
|---|---|
| `index.html` | The whole program: page, styles, and script |
| `cases/` | Eight case files |
| `start-mac.command` | Mac launcher. Checks Ollama, pulls the model, serves the folder with Perl |
| `start-windows.bat`, `serve.ps1` | Windows launcher and its PowerShell server |
| `start-linux.sh`, `start-linux.desktop` | Linux launcher, with Python, and its desktop entry |
| `docs/install-*.md` | The three install pages |
| `docs/VERIFICATION.md` | What was measured, and how |
| `bench/` | Plays a Claude doctor against the patient and judges every line |

- The launcher serves the folder on `127.0.0.1:8756`. `GET /cases/` returns a JSON list of
  the case files, so a new case appears on reload.
- The page talks to Ollama at `127.0.0.1:11434` through `/api/tags` and `/api/chat`.
- To test a change to a case, to `systemPrompt()`, or to the model, run `python3 bench/eval.py`.
  See [`bench/README.md`](../bench/README.md). It needs a logged-in `claude` command, which
  uses your Claude subscription.

## Make it your own


Everything is in one text file, `index.html`. You can change any of it.

**A larger model.** Larger models keep hidden facts better and speak more naturally. Any model
in the [Ollama library](https://ollama.com/library) will work. As of September 2026, these are
worth trying:

| Memory | Models to try | Command |
|---|---|---|
| 8 GB | `qwen3:4b-instruct` | already set |
| 8 GB | `qwen3.5:4b`, `granite4.2:3b` | `ollama pull qwen3.5:4b` |
| 16 GB or more | `gemma4:e4b-it-qat`, `granite4.2:8b`, `qwen3.5:9b` | `ollama pull gemma4:e4b-it-qat` |

Only `qwen3:4b-instruct` has been tested with this program. `llama3.1:8b` was tested and did
worse: it added stage directions and invented findings. Test a new model with
`python3 bench/eval.py --patient-model <name>` before you use it with learners.

Some models, such as Qwen 3.5 and Granite 4.2, can "think" before they answer. The program
turns this off in every request, so the patient answers at once.

To find new open-weight models and compare them:

- [Ollama, newest first](https://ollama.com/search?o=newest), what you can download, with sizes.
- [Artificial Analysis IFBench](https://artificialanalysis.ai/evaluations/ifbench), how well
  models follow instructions.
- [EQ-Bench](https://eqbench.com/), the nearest public test of role-play and character.
- [Arena](https://arena.ai/leaderboard/text?license=open-source), rankings from blind human votes.

No public leaderboard tests a simulated patient. The bench in this repository does.

Run the pull command in a terminal. Then open `index.html` in a text editor, find the line
`model: "qwen3:4b-instruct"` near the top of the script, and put the new name there. The
program uses that model if it is installed. If it is not, the program uses the first installed
model from `fallbackModels` on the next line.

**A hosted model.** The program uses Ollama's standard interface, so it can talk to any server
that uses it. Ollama offers cloud models with a free account: run `ollama signin`, pull a cloud
model, and set `model:` to its name. Or set `ollama:` in the same block to another server.
With a hosted model, your questions leave your computer.

**The prompt.** The patient's rules are in one function, `systemPrompt()` in `index.html`. It
sets how the patient talks, what it holds back, and how it answers an open question. In
testing, every problem with the patient was fixed in the prompt or the case file, not by
changing the model.

**Your own patients.** Press **Write your own patient** inside the program. It gives you
instructions to paste into any AI assistant with your source case. The assistant writes the
case file. Put the file in the `cases` folder and reload the page. The format is documented in
`cases/graham.txt`. Cases in other languages work.

**Other tools.** The same three parts, a text file for the content, a prompt for the model, and
program code for everything that must be correct, can make:

- A tutor that asks the learner questions instead of answering them.
- An examiner that marks a written note against a checklist.
- A flashcard maker that turns a lecture handout into a revision deck.
- A translation of the cases into the language your students speak.

[← Back to the README](../README.md)
