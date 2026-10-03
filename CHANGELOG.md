# Versions

The version you have is shown at the bottom of the simulator's page.

## Not released yet

- A phone edition, for testing: the same program, with the model running in the phone's
  browser. Open https://igembitsky.github.io/virtual-standardized-patient/phone/ on the phone.
  It is not part of the download for laptops. See
  [For developers](docs/for-developers.md#the-phone-edition-test-version).

## 1.3.1, 28 September 2026

Two small safety fixes from a second independent audit.

- The log file is opened once and never through a link, so a prepared link cannot make the
  simulator write to, or show, another file.
- The Linux server answers "not found" directly for a file outside its folder.
- Only your own user account can read the log file.

## 1.3, 28 September 2026

Safer, after an independent security audit.

- **No more Update button.** The simulator never downloads or installs program files by
  itself. When a new version exists, the top of the page shows a link to it on GitHub, and you
  download it yourself. See **New versions** in the install guide.
- **Other web sites cannot use it.** It answers only its own page, and refuses requests from
  other sites, including requests the browser marks as coming from another site.
- **Safer on a Mac.** The error message cannot be tricked by a folder name, and the download
  mark is removed only from Start on Mac itself.
- **Safer history.** Saved encounters are checked before they are shown.
- **Fairer marking.** A negated answer, such as "not cholangitis", no longer passes.
- **More private reports.** Error reports leave out your user name and list only the patient
  models.
- It unloads only a patient model that it loaded itself, not one another program was using.

## 1.2, 27 September 2026

Easier to start and to stop, lighter on your computer, and easy to report a problem.

- **No terminal window.** Double-click **Start on Mac**, **Start on Windows**, or
  **Start on Linux**. The simulator opens in your browser, and nothing else stays open.
- **It stops by itself.** Close the browser tab and the simulator stops within about
  10 seconds. There is also a **Quit** button at the top of the page.
- **It gives the memory back.** When it stops, it tells Ollama to unload the patient model,
  which frees several gigabytes of memory at once instead of 20 minutes later. While it is
  open, an idle model is unloaded after 10 minutes instead of 20.
- **First-run setup happens in the page.** If Ollama is not running, the page says what to
  do. If the patient model is missing, the page downloads it and shows the progress.
- **Report a problem.** If the simulator cannot start, or something goes wrong in the page,
  it offers an error report to send by email or on GitHub. **Report a problem** is also at
  the bottom of the page.
- **A tidier folder.** The download holds only the three Start files, this list, the README,
  the licence, and an `app` folder with everything else.
- **A more accurate patient.** When a question asks about many things at once, the patient no
  longer answers "no" to all of them and skips facts from its own story. To "anything else?",
  it now says one new thing, not a list, and it keeps its hidden facts: in the test, 97 open
  questions in 100 gave nothing away, up from about 85. It contradicts its case in about 4
  replies in 100.
- **Fairer marking.** A good question in normal words now gets credit much more often: 99% of
  the test questions, up from 67%. More examination names work, such as "PR exam" and
  "auscultation". A test written as "chest X-ray" now counts. A patient can use a medical word
  that their own doctor told them.
- **Cases checked against their originals.** A new check compares each case with the MedEdPORTAL
  case it came from. Three cases had moved away from their originals and were revised:
  - **Terri Travis** no longer has an invented ulcer history (daily ibuprofen, months of
    indigestion, black stools). She takes Motrin now and then for headaches, as in the original.
  - **Marsha Morris** now has her two or three earlier, milder attacks, and her real job.
  - **Jerry Graham** no longer has yellow eyes, which the original does not give. He mentions his
    dark urine himself, as in the original. Only cholangitis passes as the most likely diagnosis.
  - In all three, examinations the original does not describe now show "nothing abnormal".
  Unclear lines in Bellevue, Davis, Lewis, Samuels and Springfield were also rewritten.
- **A public benchmark.** [The benchmark page](https://igembitsky.github.io/virtual-standardized-patient/benchmark.html)
  shows how well each model plays a patient, and the bar a model must meet to be approved.
- **Changed on 27 September: on a Mac, put the folder in Applications.** macOS protects the
  Desktop, Documents and Downloads folders, and asked strange questions such as "sh would like
  to access files in your Desktop folder". The simulator no longer asks for any permission.
  From Applications, the only question is the one-time **Open Anyway**. If the folder is still
  on the Desktop, it shows where to move it.
- **The log is now `log.txt` in the simulator folder**, beside the Start files, on every system,
  so it is easy to find and send.
- Copies from before 1.2 cannot update themselves to 1.2, because the folder changed. Download
  the new ZIP once, and replace the old folder. Your saved encounters are kept by the browser.

## 1.1, 5 September 2026

- **Update from inside the page.** When a new version exists, the top of the page shows an
  **Update** button.
- The patient keeps to plain words and does not use medical terms a patient would not know.

## 1.0, 1 September 2026

The first release, for the 5th Annual Global Health Conference.

- Eight patients adapted from peer reviewed MedEdPORTAL OSCE cases.
- Interview, examine, write a note against the clock, and see the result against the case
  authors' answer key.
- Runs on your own computer with Ollama and the `qwen3:4b-instruct` model.
