# Mac Development Setup Guide — Quad Fighter

This guide walks you through setting up everything you need to run and develop **Quad Fighter** on a Mac, from scratch.

---

## Table of Contents

1. [Install Visual Studio Code](#1-install-visual-studio-code)
2. [Install Python](#2-install-python)
3. [Clone the Repository in VS Code](#3-clone-the-repository-in-vs-code)
4. [Install Dependencies](#4-install-dependencies)
5. [Run the Game](#5-run-the-game)

---

## 1. Install Visual Studio Code

Visual Studio Code (VS Code) is a free code editor that works great for Python development.

### Steps

1. Open your browser and go to **[https://code.visualstudio.com](https://code.visualstudio.com)**

2. Click the **Download Mac Universal** button (the site detects macOS automatically).

   ![VS Code download page showing the Download Mac Universal button](docs/screenshots/setup/01-vscode-download.png)

3. Once the `.zip` file downloads, open it — it will extract the **Visual Studio Code** application.

4. Drag **Visual Studio Code.app** into your **Applications** folder.

   ![Drag VS Code into the Applications folder](docs/screenshots/setup/02-vscode-drag-to-applications.png)

5. Open **Launchpad** (or open Finder → Applications) and double-click **Visual Studio Code** to launch it.

   > **First-launch security prompt:** If macOS says the app "cannot be opened because it is from an unidentified developer", go to  
   > **System Settings → Privacy & Security → Open Anyway**.

6. VS Code will open to its Welcome tab.

   ![VS Code Welcome screen on first launch](docs/screenshots/setup/03-vscode-welcome.png)

### Install the Python Extension

1. Click the **Extensions** icon in the left sidebar (looks like four squares).

   ![Extensions icon in VS Code sidebar](docs/screenshots/setup/04-vscode-extensions.png)

2. Search for **Python** and install the extension published by **Microsoft**.

   ![Python extension in the VS Code marketplace](docs/screenshots/setup/05-vscode-python-extension.png)

3. Click **Install**. Once done, the button changes to a gear icon.

---

## 2. Install Python

Quad Fighter requires **Python 3.10 or later**.

### Check if Python is already installed

1. Open **Terminal** (search for it in Spotlight with `⌘ + Space`).
2. Run:

   ```bash
   python3 --version
   ```

   If you see `Python 3.10.x` or higher, you can skip to [Step 3](#3-clone-the-repository-in-vs-code).

   ![Terminal showing python3 --version output](docs/screenshots/setup/06-terminal-python-version.png)

### Download and install Python

1. Go to **[https://www.python.org/downloads/macos/](https://www.python.org/downloads/macos/)**

2. Click the latest **Python 3.x.x** release link, then download the **macOS 64-bit universal2 installer** `.pkg` file.

   ![Python downloads page showing the macOS installer](docs/screenshots/setup/07-python-download.png)

3. Open the downloaded `.pkg` file and follow the installer steps (Continue → Agree → Install).

   ![Python installer wizard on macOS](docs/screenshots/setup/08-python-installer.png)

4. Once installation is complete, verify it worked:

   ```bash
   python3 --version
   ```

   You should see the version you just installed.

   ![Terminal confirming the new Python version](docs/screenshots/setup/09-python-verify.png)

---

## 3. Clone the Repository in VS Code

You will download (clone) the Quad Fighter source code directly inside VS Code.

### Steps

1. Open **VS Code**.

2. Press `⌘ + Shift + P` to open the **Command Palette**.

3. Type **Git: Clone** and press **Enter**.

   ![Command Palette with "Git: Clone" typed](docs/screenshots/setup/10-vscode-git-clone.png)

4. Paste the repository URL:

   ```
   https://github.com/julesdg6/quad-fighter.git
   ```

   Press **Enter**.

   ![Entering the repository URL in the Git Clone prompt](docs/screenshots/setup/11-vscode-clone-url.png)

5. Choose a folder on your Mac where you want to save the project (for example, your **Documents** folder) and click **Select as Repository Destination**.

   ![Folder picker for where to clone the repository](docs/screenshots/setup/12-vscode-clone-destination.png)

6. VS Code will clone the repository. When it's done, click **Open** in the notification that appears.

   ![VS Code notification asking to open the cloned repository](docs/screenshots/setup/13-vscode-open-cloned.png)

7. You should now see the **quad-fighter** project files in the Explorer panel on the left.

   ![VS Code Explorer showing the quad-fighter files](docs/screenshots/setup/14-vscode-explorer.png)

---

## 4. Install Dependencies

Quad Fighter needs two Python packages:

| Package | Purpose |
|---------|---------|
| `pygame-ce` | Game window, rendering, input |
| `numpy` | Procedural audio generation |

### Open the VS Code Terminal

1. In VS Code, go to **Terminal → New Terminal** (or press `` Ctrl + ` ``).

   A terminal pane will open at the bottom of the window, already pointing at the project folder.

   ![VS Code terminal pane open at the project root](docs/screenshots/setup/15-vscode-terminal.png)

### (Recommended) Create a virtual environment

Using a virtual environment keeps these packages isolated from your system Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your terminal prompt will change to show `(.venv)` at the start, confirming it is active.

![Terminal showing the (.venv) prefix after activation](docs/screenshots/setup/16-venv-activate.png)

### Install the packages

```bash
pip install -r requirements.txt
```

pip will download and install `pygame-ce` and `numpy`. You'll see a progress bar for each package.

![pip installing packages from requirements.txt](docs/screenshots/setup/17-pip-install.png)

When it finishes you'll see `Successfully installed ...` at the bottom.

---

## 5. Run the Game

1. Make sure your virtual environment is still active (you'll see `(.venv)` in the terminal prompt). If you opened a new terminal window, re-activate it:

   ```bash
   source .venv/bin/activate
   ```

2. Run the game:

   ```bash
   python3 main.py
   ```

   ![Running python3 main.py in the VS Code terminal](docs/screenshots/setup/18-run-game.png)

3. The Quad Fighter window will open and show the main menu.

   ![Quad Fighter main menu on first launch](docs/screenshots/setup/19-game-running.png)

### Controls

| Key | Action |
|-----|--------|
| ← → Arrow keys | Move left / right |
| ↑ ↓ Arrow keys | Move forward / back (lane depth) |
| Space | Jump |
| Z | Punch / light attack |
| X | Kick / heavy attack |
| C (hold) | Crouch |
| G | Grab |

---

## Troubleshooting

### `python3: command not found`
Python is not installed or not on your PATH.  
Re-run the [Python installer](#download-and-install-python) and restart your terminal.

### `No module named pygame`
The virtual environment is not active, or you installed packages outside it.  
Run `source .venv/bin/activate` and then `pip install -r requirements.txt` again.

### Game window does not open / crashes immediately
macOS may block pygame from accessing the display the first time.  
Try running from the built-in VS Code terminal rather than an external one, or grant Terminal/VS Code **Screen Recording** permission in **System Settings → Privacy & Security**.

### Permission denied on `run.command`
If you prefer to launch the game by double-clicking `run.command` in Finder, make it executable first:

```bash
chmod +x run.command
```

Then double-click it in Finder to launch.

---

> **Note on screenshots:** The screenshots referenced above (`docs/screenshots/setup/`) are placeholder paths. Add real screen captures at those paths to make this guide fully visual.
