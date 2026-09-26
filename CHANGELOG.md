# Versions

The version you have is shown at the bottom of the simulator's page.

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
