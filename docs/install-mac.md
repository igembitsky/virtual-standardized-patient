[← Back to the README](../README.md)

# Install on a Mac

Time: about 15 minutes. Most of it is a 2.5 GB download.

## 1. Install Ollama

Ollama is the free program that runs the AI model on your computer.

1. Go to [ollama.com/download](https://ollama.com/download).
2. Press **Download for macOS**.
3. Open the downloaded file and follow the steps on screen. If Ollama asks to move to your
   Applications folder, allow it.
4. Open Ollama once. A llama icon appears in the menu bar at the top of the screen.
5. Leave it running.

## 2. Download the simulator

1. Go to [github.com/igembitsky/virtual-standardized-patient](https://github.com/igembitsky/virtual-standardized-patient).
2. Press the green **Code** button.
3. Press **Download ZIP**.
4. Open your **Downloads** folder and double-click the ZIP file. A folder named
   `virtual-standardized-patient-main` appears.
5. Drag that folder to your **Desktop**.

## 3. Start the simulator

1. Open the folder on your Desktop.
2. Double-click `start-mac.command`.
3. The first time, macOS may block the file. See [If macOS blocks the file](#if-macos-blocks-the-file).
4. A Terminal window opens. Leave it open.
5. macOS may ask if Terminal can access files in your Desktop folder. Press **Allow**.
   See [If Terminal asks for folder access](#if-terminal-asks-for-folder-access).
6. The first time, the window downloads the patient model. It shows the percentage. Wait for
   **Download complete**.
7. Your browser opens the simulator at `http://127.0.0.1:8756/`.

### If macOS blocks the file

macOS checks every file downloaded from the internet. This happens once.

**macOS 15 or newer**

1. The message says Apple could not verify the file. Press **Done**.
2. Open **System Settings**.
3. Press **Privacy & Security**.
4. Scroll down to the **Security** section. Press **Open Anyway**.
5. Press **Open**.

**macOS 14 or older**

1. Right-click `start-mac.command`. On a trackpad, click with two fingers.
2. Choose **Open**.
3. Press **Open** again.

### If Terminal asks for folder access

The simulator files are in a folder on your Desktop. Terminal needs permission to read them.
macOS asks once.

![Terminal would like to access files in your Desktop folder](screenshots/terminal-folder-access.png)

1. Press **Allow**.

If you pressed **Don't Allow** by mistake:

1. Open **System Settings**.
2. Press **Privacy & Security**.
3. Press **Files and Folders**.
4. Under **Terminal**, turn on **Desktop Folder**.
5. Double-click `start-mac.command` again.

## 4. Check it works

1. The dot at the top left of the page is green. The line beside it reads
   `ready · qwen3:4b-instruct · nothing leaves this computer`.
2. Press **Choose a patient**. Eight patients are listed.
3. Turn off Wi-Fi. Choose a patient and ask a question. The patient answers.

## Every time after this

1. Open the folder. Double-click `start-mac.command`.
2. To stop, close the Terminal window.

To add a shortcut: right-click `start-mac.command`, choose **Make Alias**, and drag the alias
to the Desktop.

## If something goes wrong

| What you see | What to do |
|---|---|
| "Apple could not verify" or "unidentified developer" | See [If macOS blocks the file](#if-macos-blocks-the-file) |
| "Terminal would like to access files in your Desktop folder" | Press **Allow**. See [If Terminal asks for folder access](#if-terminal-asks-for-folder-access) |
| "You do not have appropriate access privileges" | Open Terminal. Type `chmod +x ` with a space after it. Drag `start-mac.command` into the window. Press Enter. Double-click the file again |
| "Ollama is not installed" in the window | Do step 1 again. Open Ollama once. Double-click the launcher again |
| The download stopped before 100% | Close the window. Double-click the launcher again. It continues from where it stopped |
| The download does not start | Open Terminal and type `ollama pull qwen3:4b-instruct`. Press Enter. Wait for `success` |
| The browser does not open | Open your browser and go to `http://127.0.0.1:8756/` |

Other problems are listed on [If something goes wrong](troubleshooting.md).

[← Back to the README](../README.md)
