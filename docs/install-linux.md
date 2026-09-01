[← Back to the README](../README.md)

# Install on Linux

Time: about 15 minutes. Most of it is a 2.5 GB download. Python 3 must be installed. Nearly
every Linux has it.

> [!NOTE]
> The Linux launcher has not yet been run on Linux. If it works, or does not, please
> [open an issue](https://github.com/igembitsky/virtual-standardized-patient/issues) and say so.

## 1. Install Ollama

Ollama is the free program that runs the AI model on your computer.

1. Open a terminal.
2. Type this line and press Enter:

   ```
   curl -fsSL https://ollama.com/install.sh | sh
   ```

3. Enter your password if it asks.
4. Ollama now runs in the background, and starts with your computer.

## 2. Download the simulator

1. Go to [github.com/igembitsky/virtual-standardized-patient](https://github.com/igembitsky/virtual-standardized-patient).
2. Press the green **Code** button.
3. Press **Download ZIP**.
4. Open your **Downloads** folder. Right-click the ZIP file and choose **Extract Here**. A
   folder named `virtual-standardized-patient-main` appears.
5. Move that folder to your **Desktop**.

## 3. Start the simulator

Choose one of the three ways.

**GNOME: Ubuntu, Fedora, Debian**

1. Open the folder. Right-click `start-linux.desktop` and choose **Allow Launching**.
2. Double-click `start-linux.desktop`.

**KDE: Kubuntu, KDE neon**

1. Open the folder. Double-click `start-linux.sh`.
2. Choose **Execute**.

**Any Linux, from a terminal**

```
cd ~/Desktop/virtual-standardized-patient-main
./start-linux.sh
```

Then:

1. A terminal window opens. Leave it open.
2. The first time, the window downloads the patient model. It shows the percentage. Wait for
   **Download complete**.
3. Your browser opens the simulator at `http://127.0.0.1:8756/`.

## 4. Check it works

1. The dot at the top left of the page is green. The line beside it reads
   `ready · qwen3:4b-instruct · nothing leaves this computer`.
2. Press **Choose a patient**. Eight patients are listed.
3. Turn off Wi-Fi. Choose a patient and ask a question. The patient answers.

## Every time after this

1. Start it the same way as in step 3.
2. To stop, close the terminal window, or press Control-C in it.

## If something goes wrong

| What you see | What to do |
|---|---|
| Double-click opens the file in a text editor | Use `start-linux.desktop` with **Allow Launching**, or start it from a terminal |
| Nothing happens on double-click | Open a terminal and run the two lines in step 3 |
| "python3 was not found" | Install Python 3 from your package manager. On Ubuntu: `sudo apt install python3` |
| "Ollama is not installed" in the window | Do step 1 again |
| The download stopped before 100% | Close the window. Start it again. It continues from where it stopped |
| The download does not start | In a terminal, run `ollama pull qwen3:4b-instruct`. Wait for `success` |
| The browser does not open | Open your browser and go to `http://127.0.0.1:8756/` |

Other problems are listed in the README under [If something goes wrong](../README.md#if-something-goes-wrong).

[← Back to the README](../README.md)
