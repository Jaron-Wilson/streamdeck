import pygame
import sys
import json
import os
import webbrowser
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import serial
import threading
import time
import pyautogui

# --- New Imports for Profile Automation ---
try:
    import win32gui
    import win32process
    import psutil
    AUTOMATION_ENABLED = True
except ImportError:
    AUTOMATION_ENABLED = False
    print("Warning: 'pywin32' and 'psutil' libraries not found. Automatic profile switching is disabled.", flush=True)
    print("Install them with: pip install pywin32 psutil", flush=True)

# --- Globals ---
CONFIG = {}
ACTIVE_PROFILE_NAME = "Default"
ARDUINO_PORT = "COM4"
BAUDRATE = 9600
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
FONT, SMALL_FONT, TITLE_FONT, SCREEN = None, None, None, None
FLASH_ANIMATIONS = {}
SERIAL_THREAD, WATCHER_THREAD = None, None
RUN_THREADS = True
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
    SCREEN = pygame.display.set_mode((460, 560))
    pygame.display.set_caption("ConsoleDeck v9 (Final)")

def load_config():
    """Loads or creates the configuration file with the profile structure."""
    global CONFIG, ARDUINO_PORT, ACTIVE_PROFILE_NAME
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                CONFIG = json.load(f)
            except json.JSONDecodeError:
                print("Error: config.json is corrupted. Creating a new one.", flush=True)
                CONFIG = {} # Reset config
    else:
        CONFIG = {}

    # Ensure the base structure is valid
    if "settings" not in CONFIG or not isinstance(CONFIG["settings"], dict):
        CONFIG["settings"] = {"arduino_port": "COM4", "active_profile": "Default", "automation_enabled": True}
    if "profiles" not in CONFIG or not isinstance(CONFIG["profiles"], dict):
        CONFIG["profiles"] = {"Default": {}}
    if "automation" not in CONFIG or not isinstance(CONFIG["automation"], dict):
        CONFIG["automation"] = {}
    if not CONFIG["profiles"]:
        CONFIG["profiles"]["Default"] = {}
    
    CONFIG["settings"].setdefault("automation_enabled", True)
    
    # Ensure a valid active profile is set
    profile_keys = list(CONFIG["profiles"].keys())
    active_profile = CONFIG["settings"].get("active_profile", profile_keys[0])
    if active_profile not in profile_keys:
        active_profile = profile_keys[0]
    
    ACTIVE_PROFILE_NAME = active_profile
    CONFIG["settings"]["active_profile"] = active_profile
    
    # Ensure all button keys exist for all profiles to prevent crashes
    for profile_name in CONFIG["profiles"]:
        for i in range(1, 10):
            for action in ["PRESS", "HOLD"]:
                key = f"BUTTON_{i}_{action}"
                if key not in CONFIG["profiles"][profile_name]:
                    CONFIG["profiles"][profile_name][key] = {"type": "none", "value": ""}

    ARDUINO_PORT = CONFIG["settings"].get("arduino_port", "COM4")
    print(f"[DEBUG] Config loaded. Active profile: '{ACTIVE_PROFILE_NAME}', Port: {ARDUINO_PORT}", flush=True)

def save_config():
    """Saves the current configuration."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(CONFIG, f, indent=4)
    print("[DEBUG] Config saved.", flush=True)

def execute_action(action):
    """Executes a single action or a sequence of actions (macro)."""
    global ACTIVE_PROFILE_NAME
    action_type = action.get("type", "none")
    value = action.get("value", "")

    if action_type == "switch_profile":
        profile_names = list(CONFIG["profiles"].keys())
        if not profile_names: return
        try:
            current_index = profile_names.index(ACTIVE_PROFILE_NAME)
            next_index = (current_index + 1) % len(profile_names)
            ACTIVE_PROFILE_NAME = profile_names[next_index]
            CONFIG["settings"]["active_profile"] = ACTIVE_PROFILE_NAME
            save_config()
            print(f"Action: Switched to profile '{ACTIVE_PROFILE_NAME}'", flush=True)
        except (ValueError, IndexError):
            print("Error: Could not switch profile.", flush=True)
        return

    if action_type == "macro":
        print(f"Action: Executing macro with {len(value)} steps...", flush=True)
        for step in value:
            execute_action(step)
            time.sleep(0.05)
        return

    if action_type == "delay":
        try:
            delay_seconds = int(value) / 1000.0
            print(f"Action: Delaying for {delay_seconds} seconds...", flush=True)
            time.sleep(delay_seconds)
        except (ValueError, TypeError):
            print(f"Error: Invalid delay value '{value}'.", flush=True)
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

def manage_profiles():
    """Opens a Tkinter window to manage all profile settings."""
    global ACTIVE_PROFILE_NAME, CONFIG
    root = tk.Tk()
    root.title("Profile Manager")
    root.attributes('-topmost', True)
    automation_toggle_frame = ttk.LabelFrame(root, text="Global Settings", padding=10)
    automation_toggle_frame.pack(fill="x", padx=10, pady=5)
    automation_var = tk.BooleanVar(value=CONFIG["settings"].get("automation_enabled", True))
    def toggle_automation():
        CONFIG["settings"]["automation_enabled"] = automation_var.get()
        save_config()
        status = "enabled" if automation_var.get() else "disabled"
        print(f"Automatic profile switching {status}.", flush=True)
    ttk.Checkbutton(automation_toggle_frame, text="Enable Automatic Profile Switching", variable=automation_var, command=toggle_automation).pack()
    selection_frame = ttk.LabelFrame(root, text="Active Profile", padding=10)
    selection_frame.pack(fill="x", padx=10, pady=5)
    profile_var = tk.StringVar(value=ACTIVE_PROFILE_NAME)
    profile_dropdown = ttk.Combobox(selection_frame, textvariable=profile_var, values=list(CONFIG["profiles"].keys()), state="readonly")
    profile_dropdown.pack()
    def on_profile_select(*args):
        global ACTIVE_PROFILE_NAME
        selected = profile_var.get()
        if selected in CONFIG["profiles"]:
            ACTIVE_PROFILE_NAME = selected
            CONFIG["settings"]["active_profile"] = selected
            save_config()
            print(f"Manually switched to profile: {ACTIVE_PROFILE_NAME}", flush=True)
    profile_var.trace("w", on_profile_select)
    management_frame = ttk.LabelFrame(root, text="Manage Profiles", padding=10)
    management_frame.pack(fill="x", padx=10, pady=5)
    new_profile_var = tk.StringVar()
    ttk.Entry(management_frame, textvariable=new_profile_var, width=20).grid(row=0, column=0, padx=5)
    def create_profile():
        name = new_profile_var.get().strip()
        if name and name not in CONFIG["profiles"]:
            CONFIG["profiles"][name] = {}
            for i in range(1, 10):
                for action in ["PRESS", "HOLD"]: CONFIG["profiles"][name][f"BUTTON_{i}_{action}"] = {"type": "none", "value": ""}
            save_config()
            profile_dropdown['values'] = list(CONFIG["profiles"].keys()); new_profile_var.set("")
            print(f"Created profile: {name}", flush=True)
    ttk.Button(management_frame, text="Create", command=create_profile).grid(row=0, column=1)
    def rename_profile():
        new_name = new_profile_var.get().strip(); old_name = profile_var.get()
        if new_name and old_name and new_name not in CONFIG["profiles"]:
            CONFIG["profiles"][new_name] = CONFIG["profiles"].pop(old_name)
            if CONFIG["settings"]["active_profile"] == old_name: CONFIG["settings"]["active_profile"] = new_name
            for exe, prof in list(CONFIG["automation"].items()):
                if prof == old_name: CONFIG["automation"][exe] = new_name
            save_config(); profile_dropdown['values'] = list(CONFIG["profiles"].keys()); profile_var.set(new_name); new_profile_var.set("")
            print(f"Renamed '{old_name}' to '{new_name}'", flush=True)
    ttk.Button(management_frame, text="Rename Selected", command=rename_profile).grid(row=1, column=1)
    def delete_profile():
        name_to_delete = profile_var.get()
        if name_to_delete and len(CONFIG["profiles"]) > 1:
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the profile '{name_to_delete}'?"):
                del CONFIG["profiles"][name_to_delete]
                for exe, prof in list(CONFIG["automation"].items()):
                    if prof == name_to_delete: del CONFIG["automation"][exe]
                new_active = next(iter(CONFIG["profiles"])); CONFIG["settings"]["active_profile"] = new_active
                save_config(); profile_dropdown['values'] = list(CONFIG["profiles"].keys()); profile_var.set(new_active)
                print(f"Deleted profile: {name_to_delete}", flush=True)
    ttk.Button(management_frame, text="Delete Selected", command=delete_profile).grid(row=2, column=1)
    if AUTOMATION_ENABLED:
        automation_frame = ttk.LabelFrame(root, text="Automatic Profile Switching", padding=10)
        automation_frame.pack(fill="x", padx=10, pady=5); ttk.Label(automation_frame, text="Link .exe name to a profile:").pack()
        exe_var = tk.StringVar(); ttk.Label(automation_frame, text="Executable Name (e.g., chrome.exe):").pack(); ttk.Entry(automation_frame, textvariable=exe_var).pack()
        profile_for_exe_var = tk.StringVar(); ttk.Label(automation_frame, text="Profile to Switch To:").pack(); ttk.Combobox(automation_frame, textvariable=profile_for_exe_var, values=list(CONFIG["profiles"].keys()), state="readonly").pack()
        def add_mapping():
            exe_name = exe_var.get().strip().lower(); prof_name = profile_for_exe_var.get()
            if exe_name and prof_name: CONFIG["automation"][exe_name] = prof_name; save_config(); update_automation_list(); print(f"Added automation: '{exe_name}' -> '{prof_name}'", flush=True)
        ttk.Button(automation_frame, text="Add/Update Mapping", command=add_mapping).pack(pady=5)
        automation_list_var = tk.StringVar(value=[f"{k} -> {v}" for k, v in CONFIG["automation"].items()])
        listbox = tk.Listbox(automation_frame, listvariable=automation_list_var, height=4); listbox.pack()
        def update_automation_list():
             listbox.delete(0, tk.END); [listbox.insert(tk.END, f"{k} -> {v}") for k, v in CONFIG["automation"].items()]
        def delete_mapping():
            selected = listbox.get(tk.ACTIVE)
            if selected: exe_name = selected.split(" -> ")[0]; del CONFIG["automation"][exe_name]; save_config(); update_automation_list()
        ttk.Button(automation_frame, text="Delete Selected Mapping", command=delete_mapping).pack()
    root.mainloop()

def configure_button(button_number):
    """Opens a Tkinter window to configure button actions for the active profile."""
    global CONFIG, ACTIVE_PROFILE_NAME
    active_profile_data = CONFIG["profiles"][ACTIVE_PROFILE_NAME]
    
    root = tk.Tk()
    root.title(f"Configure Button {button_number} ({ACTIVE_PROFILE_NAME})")
    root.attributes('-topmost', True)
    
    def create_action_frame(parent, title, action_key):
        frame = ttk.LabelFrame(parent, text=title, padding=(10, 5))
        frame.pack(fill="x", expand=True, padx=10, pady=5)
        
        action_config = active_profile_data.get(action_key, {"type": "none", "value": ""})
        choice_var = tk.StringVar(value=action_config["type"])
        
        simple_value_var = tk.StringVar()
        ctrl_var, alt_var, shift_var = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        main_key_var = tk.StringVar()
        macro_text_widget = None

        def update_widgets(*args):
            nonlocal macro_text_widget
            for widget in frame.winfo_children():
                if not isinstance(widget, (ttk.Combobox, tk.Label)):
                    widget.destroy()
            
            action_type = choice_var.get()

            if action_type in ["link", "typetext", "delay", "exe"]:
                simple_value_var.set(action_config.get("value", ""))
                entry = ttk.Entry(frame, width=40, textvariable=simple_value_var)
                entry.pack(pady=5)
                if action_type == "exe":
                    def choose_file():
                        path = filedialog.askopenfilename(title="Select Executable", filetypes=[("Executables", "*.exe"), ("All files", "*.*")])
                        if path: simple_value_var.set(path)
                    ttk.Button(frame, text="Choose .exe File", command=choose_file).pack()
            
            elif action_type == "keystroke":
                keystroke_frame = ttk.Frame(frame); keystroke_frame.pack(pady=5)
                ttk.Checkbutton(keystroke_frame, text="Ctrl", variable=ctrl_var).pack(side="left")
                ttk.Checkbutton(keystroke_frame, text="Alt", variable=alt_var).pack(side="left")
                ttk.Checkbutton(keystroke_frame, text="Shift", variable=shift_var).pack(side="left")
                ttk.Label(keystroke_frame, text="  Key:").pack(side="left")
                ttk.Entry(keystroke_frame, width=10, textvariable=main_key_var).pack(side="left", padx=5)
                
                hotkey_str = action_config.get("value", "")
                saved_hotkey = hotkey_str.lower().split('+')
                modifiers = {m for m in saved_hotkey if m in ["ctrl", "alt", "shift"]}
                main_key = [k for k in saved_hotkey if k not in modifiers]
                ctrl_var.set("ctrl" in modifiers)
                alt_var.set("alt" in modifiers)
                shift_var.set("shift" in modifiers)
                main_key_var.set(main_key[0] if main_key else "")

            elif action_type == "macro":
                macro_text_widget = tk.Text(frame, height=8, width=50, relief=tk.SOLID, borderwidth=1)
                macro_text_widget.pack(pady=(5,0))
                def copy_example(): macro_text_widget.delete("1.0", tk.END); macro_text_widget.insert("1.0", "# One action per line. Format is type:value\nkeystroke:alt+tab\ndelay:500\nkeystroke:ctrl+a")
                ttk.Button(frame, text="Copy Example to Editor", command=copy_example).pack(pady=(5,5))
                
                value = action_config.get("value", [])
                if isinstance(value, list) and value:
                    macro_string = "\n".join([f"{step['type']}:{step['value']}" for step in value])
                    macro_text_widget.insert("1.0", macro_string)
            
            elif action_type == "switch_profile":
                ttk.Label(frame, text="This action cycles to the next profile.").pack(pady=5)
        
        tk.Label(frame, text="Action Type:").pack(side="left", padx=5)
        dropdown = ttk.Combobox(frame, textvariable=choice_var, values=["none", "link", "exe", "keystroke", "typetext", "macro", "switch_profile", "delay"], state="readonly")
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
                return "+".join(p for p in parts if p)
            
            elif action_type == "macro" and macro_text_widget:
                macro_list = []
                text_content = macro_text_widget.get("1.0", tk.END).strip()
                for line in text_content.splitlines():
                    if line.strip() and not line.strip().startswith("#") and ":" in line:
                        step_type, step_value = line.split(":", 1)
                        macro_list.append({"type": step_type.strip(), "value": step_value.strip()})
                return macro_list
            
            elif action_type == "switch_profile":
                return "next"

            else:
                return simple_value_var.get()

        return choice_var, get_value
    
    press_choice, get_press_value = create_action_frame(root, "Press Action", f"BUTTON_{button_number}_PRESS")
    hold_choice, get_hold_value = create_action_frame(root, "Hold Action", f"BUTTON_{button_number}_HOLD")
    
    def on_save():
        active_profile_data[f"BUTTON_{button_number}_PRESS"] = {"type": press_choice.get(), "value": get_press_value()}
        active_profile_data[f"BUTTON_{button_number}_HOLD"] = {"type": hold_choice.get(), "value": get_hold_value()}
        save_config()
        root.destroy()

    ttk.Button(root, text="Save and Close", command=on_save).pack(pady=20)
    root.mainloop()

def get_button_text(action):
    action_type = action.get("type", "none"); value = action.get("value", "")
    if action_type == "macro": return f"Macro: {len(value) if isinstance(value, list) else 0} steps"
    elif action_type == "exe": value = os.path.basename(value) if value else "N/A"
    elif action_type == "switch_profile": return "Switch Profile"
    if isinstance(value, str) and len(value) > 15: value = value[:12] + "..."
    return f"{action_type}: {value}"

def draw_ui():
    global ACTIVE_PROFILE_NAME, ARDUINO_PORT
    SCREEN.fill(COLOR_BACKGROUND)
    profile_text = TITLE_FONT.render(f"Profile: {ACTIVE_PROFILE_NAME}", True, COLOR_TEXT)
    SCREEN.blit(profile_text, (SCREEN.get_width() // 2 - profile_text.get_width() // 2, 5))
    manage_text = SMALL_FONT.render("(Manage Profiles)", True, COLOR_ACCENT)
    SCREEN.blit(manage_text, (SCREEN.get_width() // 2 - manage_text.get_width() // 2, 35))
    active_profile_data = CONFIG["profiles"].get(ACTIVE_PROFILE_NAME, {})
    for i in range(9):
        x, y, btn_num = 20 + (i % 3) * 140, 20 + (i // 3) * 160 + 60, i + 1
        color = COLOR_BUTTON_FLASH if btn_num in FLASH_ANIMATIONS and pygame.time.get_ticks() < FLASH_ANIMATIONS[btn_num] else COLOR_BUTTON
        pygame.draw.rect(SCREEN, color, (x, y, 110, 110), border_radius=10)
        num_text = TITLE_FONT.render(str(btn_num), True, COLOR_TEXT)
        SCREEN.blit(num_text, (x + 10, y + 5))
        p_text = get_button_text(active_profile_data.get(f"BUTTON_{btn_num}_PRESS", {}))
        p_surf = SMALL_FONT.render(f"Press: {p_text}", True, COLOR_TEXT)
        SCREEN.blit(p_surf, (x + 10, y + 45))
        h_text = get_button_text(active_profile_data.get(f"BUTTON_{btn_num}_HOLD", {}))
        h_surf = SMALL_FONT.render(f"Hold: {h_text}", True, COLOR_TEXT)
        SCREEN.blit(h_surf, (x + 10, y + 75))
        edit_rect = pygame.Rect(x, y + 115, 110, 25)
        pygame.draw.rect(SCREEN, COLOR_EDIT_BUTTON, edit_rect, border_radius=5)
        edit_surf = SMALL_FONT.render("Edit", True, COLOR_TEXT)
        SCREEN.blit(edit_surf, (edit_rect.centerx - edit_surf.get_width() // 2, edit_rect.centery - edit_surf.get_height() // 2))
    port_text_surf = SMALL_FONT.render(f"Port: {ARDUINO_PORT}", True, COLOR_ACCENT)
    SCREEN.blit(port_text_surf, (10, SCREEN.get_height() - 20))
    pygame.display.flip()

def find_click_target(mx, my):
    if SCREEN.get_width() // 2 - 70 < mx < SCREEN.get_width() // 2 + 70 and 30 < my < 55: return "profiles", None
    for i in range(9):
        x, y = 20 + (i % 3) * 140, 20 + (i // 3) * 160 + 60
        if x <= mx <= x + 110 and y + 115 <= my <= y + 140: return "edit", i + 1
    if 10 <= mx <= 150 and SCREEN.get_height() - 25 <= my <= SCREEN.get_height() - 5: return "port", None
    return None, None

def listen_to_serial():
    global RUN_THREADS, CONFIG, LAST_ACTION_TIME
    while RUN_THREADS:
        try:
            with serial.Serial(ARDUINO_PORT, BAUDRATE, timeout=1) as ser:
                ser.flushInput(); print(f"Successfully connected to {ARDUINO_PORT}", flush=True)
                while RUN_THREADS:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            print(f"Received: \"{line}\"", flush=True); current_time = time.time(); button_id = line.split('_')[1]
                            if (current_time - LAST_ACTION_TIME.get(button_id, 0)) > ACTION_COOLDOWN:
                                LAST_ACTION_TIME[button_id] = current_time; FLASH_ANIMATIONS[int(button_id)] = pygame.time.get_ticks() + 200
                                action = CONFIG["profiles"][ACTIVE_PROFILE_NAME].get(line)
                                if action: execute_action(action)
                    except (serial.SerialException, IndexError): break
        except serial.SerialException:
            if RUN_THREADS: time.sleep(5)

def profile_watcher():
    global ACTIVE_PROFILE_NAME, RUN_THREADS
    if not AUTOMATION_ENABLED: return
    last_exe = None
    while RUN_THREADS:
        if not CONFIG["settings"].get("automation_enabled", True):
            time.sleep(2); continue
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid); current_exe = process.name().lower()
                if current_exe != last_exe:
                    print(f"Active window changed to: {current_exe}", flush=True); last_exe = current_exe
                    target_profile = CONFIG["automation"].get(current_exe)
                    if target_profile and target_profile != ACTIVE_PROFILE_NAME and target_profile in CONFIG["profiles"]:
                        print(f"Automation: Switching to profile '{target_profile}'", flush=True); ACTIVE_PROFILE_NAME = target_profile
                        CONFIG["settings"]["active_profile"] = target_profile
        except (psutil.NoSuchProcess, psutil.AccessDenied, win32process.error, win32gui.error):
            last_exe = None
        time.sleep(2)

def restart_threads():
    global SERIAL_THREAD, WATCHER_THREAD, RUN_THREADS, ARDUINO_PORT
    if (SERIAL_THREAD and SERIAL_THREAD.is_alive()) or (WATCHER_THREAD and WATCHER_THREAD.is_alive()):
        RUN_THREADS = False; 
        if SERIAL_THREAD: SERIAL_THREAD.join(timeout=2)
        if WATCHER_THREAD: WATCHER_THREAD.join(timeout=2)
    ARDUINO_PORT = CONFIG["settings"].get("arduino_port", "COM4")
    print(f"Starting threads for port {ARDUINO_PORT}...", flush=True)
    RUN_THREADS = True
    SERIAL_THREAD = threading.Thread(target=listen_to_serial, daemon=True); SERIAL_THREAD.start()
    WATCHER_THREAD = threading.Thread(target=profile_watcher, daemon=True); WATCHER_THREAD.start()

def main():
    global CONFIG
    load_config(); init_pygame(); restart_threads()
    running = True
    while running:
        draw_ui()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                target, value = find_click_target(*event.pos)
                if target == "edit": configure_button(value)
                elif target == "profiles": manage_profiles()
                elif target == "port":
                    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
                    new_port = simpledialog.askstring("COM Port", "Enter new COM Port:", initialvalue=ARDUINO_PORT)
                    if new_port: CONFIG["settings"]["arduino_port"] = new_port.upper(); save_config(); restart_threads()
                    root.destroy()
    global RUN_THREADS
    RUN_THREADS = False; 
    if SERIAL_THREAD: SERIAL_THREAD.join(timeout=2)
    if WATCHER_THREAD: WATCHER_THREAD.join(timeout=2)
    pygame.quit(); sys.exit()

if __name__ == "__main__":
    main()
