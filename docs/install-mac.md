[← Back to the README](../README.md)

# Install on a Mac

Time: about 15 minutes. Most of it is a 2.5 GB download.

## 1. Install Ollama

Ollama is the free program that runs the AI model on your computer.

1. Go to [ollama.com/download](https://ollama.com/download).
2. Press **Download for macOS**.
3. Open the downloaded file and follow the steps on screen.
4. Open Ollama once. A llama icon appears in the menu bar at the top of the screen.

## 2. Download the simulator

1. Go to [github.com/igembitsky/virtual-standardized-patient](https://github.com/igembitsky/virtual-standardized-patient).
2. Press the green **Code** button.
3. Press **Download ZIP**.
4. Open your **Downloads** folder and double-click the ZIP file.
5. Drag the new folder to your **Desktop**.

## 3. Start the simulator

1. Open the folder on your Desktop.
2. Double-click **Start on Mac**.
   The first time, macOS says it could not verify the app. Follow [If macOS blocks the app](#if-macos-blocks-the-app).
3. If macOS asks to let Start on Mac access files in your Desktop folder, press **Allow**.
4. Your browser opens the simulator. No other window opens.
5. The first time, the page downloads the patient model and shows the progress. Keep the
   page open until it says **ready**.

## 4. Check it works

1. The dot at the top left of the page is green.
2. Press **Choose a patient**. Eight patients are listed.
3. Choose a patient and ask a question. The patient answers.

You can now turn off Wi-Fi and use the simulator offline.

## Every time after this

1. Open the folder. Double-click **Start on Mac**.
2. To stop, close the browser tab, or press **Quit** at the top of the page. The simulator
   stops within a few seconds and gives the memory back.

## Updates

When a new version exists, the top of the page shows **New version** and an **Update** button.
Press **Update**. The page reloads by itself after about 10 seconds. Your notes and your
history stay. The version you have is at the bottom of the page.

---

## Troubleshooting

You only need this part if a step above did not work.

### If macOS blocks the app

The message says Apple could not verify the app. This happens once.

**macOS 15 or newer**

1. Press **Done**.
2. Open **System Settings**.
3. Press **Privacy & Security**.
4. Scroll down to the **Security** section. Press **Open Anyway**.
5. Press **Open**.

**macOS 14 or older**

1. Right-click **Start on Mac**. On a trackpad, click with two fingers.
2. Choose **Open**.
3. Press **Open** again.

### If you pressed Don't Allow by mistake

1. Open **System Settings**.
2. Press **Privacy & Security**.
3. Press **Files and Folders**.
4. Under **Start on Mac**, turn on **Desktop Folder**.
5. Double-click **Start on Mac** again.

### If nothing happens

1. Wait 20 seconds. The first start after a download can be slow.
2. Open your browser and go to `http://127.0.0.1:8756/`.
3. If that does not load, open **Terminal**, type `perl ` with a space after it, drag the
   file `server.pl` from the `app` folder into the window, and press Enter. The window shows
   what went wrong. Please [open an issue](https://github.com/igembitsky/virtual-standardized-patient/issues)
   and paste it.

### If the download stops

The page tries again by itself and carries on from where it stopped. If it still does not
start, open Terminal and type `ollama pull qwen3:4b-instruct`. Press Enter. Wait for `success`.

### Add a shortcut

Drag **Start on Mac** to the Dock. Or right-click it, choose **Make Alias**, and drag the
alias to the Desktop.

Other problems are listed on [If something goes wrong](troubleshooting.md).

[← Back to the README](../README.md)
