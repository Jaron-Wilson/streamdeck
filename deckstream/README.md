# ConsoleDeck v11

Welcome to ConsoleDeck! This project turns a custom-built, 9-button keypad powered by an ESP32 into a powerful, fully customizable macro pad for Windows. It features a user-friendly interface for configuring buttons, support for complex macros, and automatic profile switching based on the application you're currently using.

## Features

* **Customizable Buttons:** Assign actions to both a quick "press" and a long "hold" for all 9 buttons.
* **Profile System:** Create, rename, and delete profiles to organize your macros for different tasks (e.g., "Work," "Gaming," "Video Editing").
* **Automatic Profile Switching:** Link profiles to specific applications (`.exe`), and the deck will switch automatically when you focus that application.
* **Rich Action Types:** Go beyond simple hotkeys with a variety of built-in actions.
* **Powerful Macro Editor:** Chain multiple actions together, including keystrokes, text typing, and delays, to automate complex workflows.
* **User-Friendly GUI:** A Pygame-based interface allows for easy configuration and management of all features.

---

## Setup

To get started, you'll need to set up both the Python application on your computer and the firmware on your ESP32.

### 1. Python Environment (Your PC)

The application is run from a Python script on your computer. First, you need to install the required libraries.

**Installation:**
Open a command prompt (CMD) or terminal and run the following command to install all necessary libraries in one line:

```bash
pip install pygame pyserial pyautogui pywin32 psutil
```

* `pygame`: For drawing the graphical user interface.
* `pyserial`: For communicating with the ESP32 over the USB port.
* `pyautogui`: For simulating keystrokes and typing text.
* `pywin32` & `psutil`: For detecting the active window for automatic profile switching.

### 2. Arduino Firmware (Your ESP32)

The provided `.ino` script is the firmware for your ESP32.

1.  **Open the `.ino` script** in the Arduino IDE.
2.  **Install the ESP32 Board Manager:** If you haven't already, go to `File > Preferences` and add the following URL to the "Additional Boards Manager URLs" field:
    `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
    Then, go to `Tools > Board > Boards Manager...`, search for "esp32", and install the package by Espressif Systems.
3.  **Select Your Board:** Go to `Tools > Board` and select a generic board like "ESP32 Dev Module".
4.  **Select the Port:** Go to `Tools > Port` and select the COM port that your ESP32 is connected to.
5.  **Upload the Code:** Click the "Upload" button to flash the firmware to your device.

---

## Running the Application

1.  Plug your ESP32 device into your computer's USB port.
2.  Navigate to the project folder in your command prompt or terminal.
3.  Run the Python script:
    ```bash
    python streamdeck.py
    ```
    (Or whatever you have named your main Python file).

The ConsoleDeck UI should appear, and it will attempt to connect to your device on the configured COM port.

---

## Action Types Explained

When you click "Edit" on a button, you can assign an action. Here’s what each type does:

| Action Type      | Description                                                                                             | Example Value                                                                               |
| ---------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `none`           | **Does Nothing.** The default for unassigned buttons.                                                     | (No value needed)                                                                           |
| `link`           | Opens the specified URL in your default web browser.                                                      | `https://www.google.com`                                                                    |
| `exe`            | Runs an executable file, just like double-clicking it.                                                    | `C:\Windows\System32\calc.exe`                                                              |
| `open_with`      | Opens a specific file or project folder with a specific application. Use `|` to separate the two paths. | `C:\path\to\idea64.exe|C:\Users\YourUser\IdeaProjects\MyProject`                             |
| `keystroke`      | Simulates a keyboard hotkey. For modifiers, use `ctrl`, `alt`, `shift`, and `win`.                        | `ctrl+shift+esc`                                                                            |
| `typetext`       | Types out a string of text character by character.                                                        | `This is an automated message!`                                                             |
| `delay`          | **For macros only.** Pauses the macro for a specified number of milliseconds.                             | `500` (pauses for half a second)                                                            |
| `switch_profile` | Switches to the next available profile in your list.                                                      | (No value needed)                                                                           |
| `macro`          | Executes a list of other actions in sequence, one per line, using the `type:value` format.                | See the detailed macro example below.                                                       |

### Macro Example

To create a macro that copies selected text, switches to another window, and pastes it, you would enter the following into the multi-line macro editor:

```
# This macro copies text and pastes it in another window
keystroke:ctrl+c
delay:100
keystroke:alt+tab
delay:500
typetext:Pasting from my ConsoleDeck:
keystroke:ctrl+v
