import pygame
import sys
import json
import os
import webbrowser
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
import serial
import threading
import time
import pyautogui

# --- Globals ---
CONFIG = {}
ARDUINO_PORT = "COM4"
BAUDRATE = 9600
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
FONT, SMALL_FONT, TITLE_FONT, SCREEN = None, None, None, None
FLASH_ANIMATIONS = {}
SERIAL_THREAD, SERIAL_THREAD_RUNNING = None, True
LAST_ACTION_TIME = {}
ACTION_COOLDOWN = 0.5

# --- UI Colors ---
COLOR_BACKGROUND = (30, 30, 30)
COLOR_BUTTON = (45, 45, 45)
COLOR_BUTTON_FLASH = (80, 80, 80)
COLOR_TEXT = (220, 220, 220)
COLOR_ACCENT = (0, 122, 204)
COLOR_EDIT_BUTTON = (60, 60, 60)

def init_pygame():
    """Initializes Pygame, fonts, and the main display window."""
    global FONT, SMALL_FONT, TITLE_FONT, SCREEN
    pygame.init()
    try:
        FONT = pygame.font.SysFont("Segoe UI", 20)
        SMALL_FONT = pygame.font.SysFont("Segoe UI", 14)
        TITLE_FONT = pygame.font.SysFont("Segoe UI Semibold", 22)
    except:
        FONT = pygame.font.SysFont(None, 24)
        SMALL_FONT = pygame.font.SysFont(None, 18)
        TITLE_FONT = pygame.font.SysFont(None, 26)
    SCREEN = pygame.display.set_mode((460, 510))
    pygame.display.set_caption("ConsoleDeck v7 (Delays)")

def load_config():
    """Loads or creates the configuration file."""
    global CONFIG, ARDUINO_PORT
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            CONFIG = json.load(f)
    else:
        CONFIG = {"arduino_port": "COM4"}
    
    for i in range(1, 10):
        for action_type in ["PRESS", "HOLD"]:
            key = f"BUTTON_{i}_{action_type}"
            if key not in CONFIG:
                CONFIG[key] = {"type": "none", "value": ""}
    
    ARDUINO_PORT = CONFIG.get("arduino_port", "COM4")
    print(f"[DEBUG] Config loaded. Port set to {ARDUINO_PORT}", flush=True)

def save_config():
    """Saves the current configuration."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(CONFIG, f, indent=4)
    print("[DEBUG] Config saved.", flush=True)

def execute_action(action):
    """Executes a single action or a sequence of actions (macro)."""
    action_type = action.get("type", "none")
    value = action.get("value", "")

    if action_type == "macro":
        print(f"Action: Executing macro with {len(value)} steps...", flush=True)
        for step in value:
            execute_action(step)
            # Add a small default delay between all steps for reliability
            time.sleep(0.05)
        return

    # --- New Delay Action Logic ---
    if action_type == "delay":
        try:
            # Convert milliseconds to seconds
            delay_seconds = int(value) / 1000.0
            print(f"Action: Delaying for {delay_seconds} seconds...", flush=True)
            time.sleep(delay_seconds)
        except (ValueError, TypeError):
            print(f"Error: Invalid delay value '{value}'. Must be a number.", flush=True)
        return

    if action_type == "link":
        try:
            webbrowser.open(value)
            print(f"Action: Opening link: {value}", flush=True)
        except Exception as e:
            print(f"Error opening link '{value}': {e}", flush=True)
    elif action_type == "exe":
        try:
            subprocess.Popen(value)
            print(f"Action: Running executable: {value}", flush=True)
        except Exception as e:
            print(f"Error running executable '{value}': {e}", flush=True)
    elif action_type == "keystroke":
        try:
            keys = [k.strip() for k in value.lower().split('+')]
            print(f"Action: Pressing hotkey: {keys}", flush=True)
            pyautogui.hotkey(*keys)
        except Exception as e:
            print(f"Error pressing hotkey '{value}': {e}", flush=True)
    elif action_type == "typetext":
        try:
            print(f"Action: Typing text: {value}", flush=True)
            pyautogui.write(value, interval=0.01)
        except Exception as e:
            print(f"Error typing text: {e}", flush=True)

def configure_button(button_number):
    """Opens a Tkinter window to configure button actions."""
    global CONFIG

    def create_action_frame(parent, title, action_key):
        frame = ttk.LabelFrame(parent, text=title, padding=(10, 5))
        frame.pack(fill="x", expand=True, padx=10, pady=5)
        action_config = CONFIG.get(action_key, {"type": "none", "value": ""})
        
        choice_var = tk.StringVar(value=action_config["type"])
        value_var = tk.StringVar(value=action_config.get("value", ""))
        
        ctrl_var, alt_var, shift_var = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        main_key_var = tk.StringVar()
        macro_text_widget = None

        def update_widgets(*args):
            nonlocal macro_text_widget
            for widget in frame.winfo_children():
                if not isinstance(widget, (ttk.Combobox, tk.Label, ttk.Button)):
                    widget.destroy()
            
            action_type = choice_var.get()

            if action_type in ["link", "typetext", "delay"]:
                entry = ttk.Entry(frame, width=40, textvariable=value_var)
                entry.pack(pady=5)
            elif action_type == "keystroke":
                keystroke_frame = ttk.Frame(frame)
                keystroke_frame.pack(pady=5)
                ttk.Checkbutton(keystroke_frame, text="Ctrl", variable=ctrl_var).pack(side="left")
                ttk.Checkbutton(keystroke_frame, text="Alt", variable=alt_var).pack(side="left")
                ttk.Checkbutton(keystroke_frame, text="Shift", variable=shift_var).pack(side="left")
                ttk.Label(keystroke_frame, text="  Key:").pack(side="left")
                key_entry = ttk.Entry(keystroke_frame, width=10, textvariable=main_key_var)
                key_entry.pack(side="left", padx=5)
                
                hotkey_str = value_var.get() if isinstance(value_var.get(), str) else ""
                saved_hotkey = hotkey_str.lower().split('+')
                modifiers = [m for m in saved_hotkey if m in ["ctrl", "alt", "shift"]]
                main_key = [k for k in saved_hotkey if k not in modifiers]
                
                ctrl_var.set("ctrl" in modifiers)
                alt_var.set("alt" in modifiers)
                shift_var.set("shift" in modifiers)
                main_key_var.set(main_key[0] if main_key else "")
            
            elif action_type == "macro":
                macro_text_widget = tk.Text(frame, height=8, width=50, relief=tk.SOLID, borderwidth=1)
                macro_text_widget.pack(pady=(5, 0))
                
                def copy_example():
                    example_text = (
                        "# One action per line. Format is type:value\n"
                        "keystroke:alt+tab\n"
                        "delay:500\n"
                        "keystroke:ctrl+a\n"
                        "delay:100\n"
                        "keystroke:ctrl+c\n"
                        "typetext:Text was copied."
                    )
                    macro_text_widget.delete("1.0", tk.END)
                    macro_text_widget.insert("1.0", example_text)

                example_button = ttk.Button(frame, text="Copy Example to Editor", command=copy_example)
                example_button.pack(pady=(5, 5))

                if isinstance(action_config['value'], list) and action_config['value']:
                    macro_string = "\n".join([f"{step['type']}:{step['value']}" for step in action_config['value']])
                    macro_text_widget.insert("1.0", macro_string)

        tk.Label(frame, text="Action Type:").pack(side="left", padx=5)
        dropdown = ttk.Combobox(frame, textvariable=choice_var, values=["none", "link", "exe", "keystroke", "typetext", "macro"], state="readonly")
        dropdown.pack(side="left", padx=5)
        dropdown.bind("<<ComboboxSelected>>", update_widgets)
        
        update_widgets()
        
        def get_value():
            action_type = choice_var.get()
            if action_type == "keystroke":
                parts = []
                if ctrl_var.get(): parts.append("ctrl")
                if alt_var.get(): parts.append("alt")
                if shift_var.get(): parts.append("shift")
                if main_key_var.get(): parts.append(main_key_var.get().strip().lower())
                return "+".join(parts)
            
            elif action_type == "macro" and macro_text_widget:
                macro_list = []
                text_content = macro_text_widget.get("1.0", tk.END).strip()
                for line in text_content.splitlines():
                    if line.strip() and not line.strip().startswith("#"):
                        if ":" in line:
                            step_type, step_value = line.split(":", 1)
                            macro_list.append({"type": step_type.strip(), "value": step_value.strip()})
                return macro_list
            else:
                return value_var.get()

        return choice_var, get_value

    root = tk.Tk()
    root.title(f"Configure Button {button_number}")
    root.attributes('-topmost', True)

    press_choice, get_press_value = create_action_frame(root, "Press Action (Quick Tap)", f"BUTTON_{button_number}_PRESS")
    hold_choice, get_hold_value = create_action_frame(root, "Hold Action (Long Press)", f"BUTTON_{button_number}_HOLD")
    
    def on_save():
        CONFIG[f"BUTTON_{button_number}_PRESS"] = {"type": press_choice.get(), "value": get_press_value()}
        CONFIG[f"BUTTON_{button_number}_HOLD"] = {"type": hold_choice.get(), "value": get_hold_value()}
        save_config()
        root.destroy()

    btn_save = ttk.Button(root, text="Save and Close", command=on_save)
    btn_save.pack(pady=20)
    root.mainloop()

def get_button_text(action):
    action_type = action.get("type", "none")
    value = action.get("value", "")
    if action_type == "macro":
        step_count = len(value) if isinstance(value, list) else 0
        return f"Macro: {step_count} steps"
    elif action_type == "exe":
        value = os.path.basename(value) if value else "N/A"
    if isinstance(value, str) and len(value) > 15:
        value = value[:12] + "..."
    return f"{action_type}: {value}"

def draw_ui():
    SCREEN.fill(COLOR_BACKGROUND)
    for i in range(9):
        x, y, btn_num = 20 + (i % 3) * 140, 20 + (i // 3) * 160, i + 1
        color = COLOR_BUTTON_FLASH if btn_num in FLASH_ANIMATIONS and pygame.time.get_ticks() < FLASH_ANIMATIONS[btn_num] else COLOR_BUTTON
        pygame.draw.rect(SCREEN, color, (x, y, 110, 110), border_radius=10)
        num_text = TITLE_FONT.render(str(btn_num), True, COLOR_TEXT)
        SCREEN.blit(num_text, (x + 10, y + 5))
        p_text = get_button_text(CONFIG.get(f"BUTTON_{btn_num}_PRESS", {}))
        p_surf = SMALL_FONT.render(f"Press: {p_text}", True, COLOR_TEXT)
        SCREEN.blit(p_surf, (x + 10, y + 45))
        h_text = get_button_text(CONFIG.get(f"BUTTON_{btn_num}_HOLD", {}))
        h_surf = SMALL_FONT.render(f"Hold: {h_text}", True, COLOR_TEXT)
        SCREEN.blit(h_surf, (x + 10, y + 75))
        edit_rect = pygame.Rect(x, y + 115, 110, 25)
        pygame.draw.rect(SCREEN, COLOR_EDIT_BUTTON, edit_rect, border_radius=5)
        edit_surf = SMALL_FONT.render("Edit", True, COLOR_TEXT)
        SCREEN.blit(edit_surf, (edit_rect.centerx - edit_surf.get_width() // 2, edit_rect.centery - edit_surf.get_height() // 2))
    port_surf = SMALL_FONT.render(f"Port: {ARDUINO_PORT}", True, COLOR_ACCENT)
    SCREEN.blit(port_surf, (10, SCREEN.get_height() - 20))
    pygame.display.flip()

def find_click_target(mx, my):
    for i in range(9):
        x, y = 20 + (i % 3) * 140, 20 + (i // 3) * 160
        if x <= mx <= x + 110 and y + 115 <= my <= y + 140:
            return "edit", i + 1
    if 10 <= mx <= 150 and SCREEN.get_height() - 25 <= my <= SCREEN.get_height() - 5:
        return "port", None
    return None, None

def listen_to_serial():
    global SERIAL_THREAD_RUNNING, CONFIG, LAST_ACTION_TIME
    while SERIAL_THREAD_RUNNING:
        try:
            with serial.Serial(ARDUINO_PORT, BAUDRATE, timeout=1) as ser:
                ser.flushInput()
                print(f"Successfully connected to {ARDUINO_PORT}", flush=True)
                while SERIAL_THREAD_RUNNING:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            print(f"Received: \"{line}\"", flush=True)
                            current_time = time.time()
                            button_id = line.split('_')[1]
                            if (current_time - LAST_ACTION_TIME.get(button_id, 0)) > ACTION_COOLDOWN:
                                LAST_ACTION_TIME[button_id] = current_time
                                FLASH_ANIMATIONS[int(button_id)] = pygame.time.get_ticks() + 200
                                if line in CONFIG:
                                    execute_action(CONFIG[line])
                    except (serial.SerialException, IndexError):
                        break
        except serial.SerialException:
            if SERIAL_THREAD_RUNNING:
                time.sleep(5)

def restart_serial_thread():
    global SERIAL_THREAD, SERIAL_THREAD_RUNNING, ARDUINO_PORT
    if SERIAL_THREAD and SERIAL_THREAD.is_alive():
        print("Stopping existing serial thread...", flush=True)
        SERIAL_THREAD_RUNNING = False
        SERIAL_THREAD.join(timeout=2)
    ARDUINO_PORT = CONFIG.get("arduino_port", "COM4")
    print(f"Starting new serial thread for port {ARDUINO_PORT}...", flush=True)
    SERIAL_THREAD_RUNNING = True
    SERIAL_THREAD = threading.Thread(target=listen_to_serial, daemon=True)
    SERIAL_THREAD.start()

def main():
    global CONFIG
    load_config()
    init_pygame()
    restart_serial_thread()
    running = True
    while running:
        draw_ui()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                target, value = find_click_target(*event.pos)
                if target == "edit":
                    configure_button(value)
                elif target == "port":
                    root = tk.Tk()
                    root.withdraw()
                    root.attributes('-topmost', True)
                    new_port = simpledialog.askstring("COM Port", "Enter new COM Port:", initialvalue=ARDUINO_PORT)
                    if new_port:
                        print(f"User changed port to {new_port}", flush=True)
                        CONFIG["arduino_port"] = new_port.upper()
                        save_config()
                        restart_serial_thread()
                    root.destroy()
    print("Shutting down...", flush=True)
    SERIAL_THREAD_RUNNING = False
    if SERIAL_THREAD:
        SERIAL_THREAD.join(timeout=2)
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
