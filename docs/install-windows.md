[← Back to the README](../README.md)

# Install on Windows

Time: about 20 minutes. Most of it is two downloads, 1.5 GB and 2.5 GB. Windows 10 or 11.

> [!NOTE]
> The Windows launcher has not yet been run on Windows. It uses only what Windows ships.
> If it works, or does not, please [open an issue](https://github.com/igembitsky/virtual-standardized-patient/issues) and say so.

## 1. Install Ollama

Ollama is the free program that runs the AI model on your computer.

1. Go to [ollama.com/download](https://ollama.com/download).
2. Press **Download for Windows**.
3. Open the downloaded file. Follow the steps on screen.
4. Open Ollama once. A llama icon appears near the clock, at the bottom right of the screen.
5. Leave it running.

## 2. Download the simulator

1. Go to [github.com/igembitsky/virtual-standardized-patient](https://github.com/igembitsky/virtual-standardized-patient).
2. Press the green **Code** button.
3. Press **Download ZIP**.
4. Open your **Downloads** folder. Right-click the ZIP file and choose **Extract All**. Press
   **Extract**. A folder named `virtual-standardized-patient-main` appears.
5. Drag that folder to your **Desktop**.

## 3. Start the simulator

1. Open the folder on your Desktop.
2. Double-click `start-windows.bat`.
3. The first time, Windows may show a warning. See [If Windows shows a warning](#if-windows-shows-a-warning).
4. A black window opens. Leave it open.
5. The first time, the window downloads the patient model. It shows the percentage. Wait for
   **Download complete**.
6. Your browser opens the simulator at `http://127.0.0.1:8756/`.

### If Windows shows a warning

Windows checks every file downloaded from the internet. This happens once.

- If the box says **Windows protected your PC**: press **More info**. Press **Run anyway**.
- If the box says **Open File - Security Warning**: press **Run**.

## 4. Check it works

1. The dot at the top left of the page is green. The line beside it reads
   `ready · qwen3:4b-instruct · nothing leaves this computer`.
2. Press **Choose a patient**. Eight patients are listed.
3. Turn off Wi-Fi. Choose a patient and ask a question. The patient answers.

## Every time after this

1. Open the folder. Double-click `start-windows.bat`.
2. To stop, close the black window.

To add a shortcut: right-click `start-windows.bat`, choose **Show more options**, then
**Send to**, then **Desktop (create shortcut)**.

## If something goes wrong

| What you see | What to do |
|---|---|
| A blue **Windows protected your PC** box | Press **More info**. Press **Run anyway** |
| The black window closes at once | Right-click `start-windows.bat` and choose **Edit**. Nothing to change. Close it. Double-click the file again. If it still closes, open an issue |
| "Ollama is not installed" in the window | Do step 1 again. Open Ollama once. Double-click the launcher again |
| The download stopped before 100% | Close the window. Double-click the launcher again. It continues from where it stopped |
| The download does not start | Press the Start button, type `PowerShell`, and open it. Type `ollama pull qwen3:4b-instruct`. Press Enter. Wait for `success` |
| The browser does not open | Open your browser and go to `http://127.0.0.1:8756/` |

Other problems are listed on [If something goes wrong](troubleshooting.md).

[← Back to the README](../README.md)
