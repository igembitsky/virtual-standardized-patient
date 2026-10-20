# Contributing

Thank you for helping. This project is a teaching tool for medical students and their teachers,
often in places with little internet. Every change must keep it simple to install, private,
and correct.

## Ways to help

| You want to | Do this |
|---|---|
| Report a problem with the install | [Open a setup problem](https://github.com/igembitsky/virtual-standardized-patient/issues/new?template=setup-problem.md) |
| Report a wrong answer from a patient | [Open a patient problem](https://github.com/igembitsky/virtual-standardized-patient/issues/new?template=patient-problem.md) |
| Suggest a case, a language, or a feature | [Open an idea](https://github.com/igembitsky/virtual-standardized-patient/issues/new?template=idea.md) |
| Report a security problem | Do not open an issue. See [SECURITY.md](../SECURITY.md) |
| Change the program or a case | Open a pull request, as below |

## Rules for every change

1. **One file is the program.** Everything the learner sees is in `app/index.html`. Do not add a
   build step, a framework, or a dependency.
2. **Nothing leaves the computer.** No new network request, no analytics, no account.
3. **The model only speaks as the patient.** Examination findings, counting, and marking come
   from the case file and the program, never from the model.
4. **Keep the credit.** Each case keeps its authors, its source, its license, and a note of what
   was changed. See [`app/cases/LICENSE.md`](../app/cases/LICENSE.md).
5. **Plain English.** Many learners read English as a second language. Use short sentences and
   common words.
6. **The hosted web version is built from `app/index.html`.** A change to that file also
   changes the web version, so keep it working in both.

## Add or change a case

1. Copy a case file in `app/cases/`. The format is documented in `app/cases/graham.txt`.
2. Use only openly licensed sources, for example peer-reviewed OSCE cases under CC BY.
3. Fill in the credit, and say what you changed from the source.
4. Reload the page. The new patient appears in the list.
5. Run the bench for that case: `python3 bench/eval.py --cases <id>`. See
   [`bench/README.md`](../bench/README.md).

## Test a change to the program

```bash
npm install --no-save --prefix tests playwright@1.56.1
npx --prefix tests playwright install chromium
node tests/e2e.mjs . python3 app/server.py
```

The test drives one launcher's server in a real browser against a stand-in for Ollama. The
first argument is the simulator folder, and the rest is the command that starts the server. GitHub runs them
on a Mac, Windows, and Linux machine for every pull request. A change to `systemPrompt()` or to
the model needs a bench run too.

## Pull requests

- Keep each pull request to one change.
- Say what problem it solves and how you tested it.
- Add a line to [CHANGELOG.md](../CHANGELOG.md) if a learner will notice the change.

By taking part, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
