import os
import json
import time
import sys
import random
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import base64
import requests
import schedule
import pyautogui
import numpy as np
from PIL import Image, ImageEnhance
import easyocr
import pygetwindow as gw
import win32gui
import win32con
import win32api
import win32process
from datetime import datetime, timedelta

# --- Configuration & Setup ---
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

CONFIG = load_config()


# --- Logging Helper ---
def log(message, type="INFO"):
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "ACTION": "🚀", "DEBUG": "🔍", "OCR": "👁️"}
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {icons.get(type, '🔹')} {message}")

# --- Initialize OCR Engine ---
log("Initializing EasyOCR Reader (English)...", "OCR")
READER = easyocr.Reader(['en'], gpu=False) # Keep gpu=False for compatibility

# --- WPPConnect Client ---
class WPPConnectClient:
    def __init__(self, base_url, session, secret_key):
        self.base_url = base_url.rstrip('/')
        self.session = session
        self.secret_key = secret_key
        self.token = None
        self.headers = {"Content-Type": "application/json"}

    def _generate_token(self):
        log(f"Generating access token for session: {self.session}...", "DEBUG")
        url = f"{self.base_url}/api/{self.session}/{self.secret_key}/generate-token"
        try:
            response = requests.post(url, timeout=20)
            if response.status_code in [200, 201]:
                self.token = response.json().get('token')
                self.headers["Authorization"] = f"Bearer {self.token}"
                log("Token generated successfully.", "SUCCESS")
                return True
            log(f"Failed to generate token: {response.text}", "ERROR")
        except Exception as e:
            log(f"Token generation error: {e}", "ERROR")
        return False

    def send_image(self, phone_number, file_path, caption=""):
        if not self.token:
            if not self._generate_token():
                return False

        is_group = "@g.us" in phone_number
        chat_id = phone_number if is_group else f"{phone_number.replace('+', '')}"
        
        try:
            with open(file_path, "rb") as img:
                b64 = base64.b64encode(img.read()).decode('utf-8')
                base64_data = f"data:image/png;base64,{b64}"
        except Exception as e:
            log(f"Image encoding error: {e}", "ERROR")
            return False

        url = f"{self.base_url}/api/{self.session}/send-image"
        payload = {
            "phone": chat_id,
            "base64": base64_data,
            "caption": caption,
            "isGroup": is_group
        }
        
        log(f"Sending image to {phone_number}...", "ACTION")
        try:
            res = requests.post(url, headers=self.headers, json=payload, timeout=45)
            if res.status_code == 401: # Token might be expired
                if self._generate_token():
                    res = requests.post(url, headers=self.headers, json=payload, timeout=45)
            
            if res.status_code in [200, 201]:
                log("Message sent successfully!", "SUCCESS")
                return True
            log(f"Send failed: {res.status_code} - {res.text}", "ERROR")
        except Exception as e:
            log(f"WPPConnect exception: {e}", "ERROR")
        return False

# --- Global Session State ---
SESSION_HWND = None

# --- Automation Functions ---
def activate_window(title_substring, keep_on_top=False):
    global SESSION_HWND
    if not title_substring: return True
    try:
        # Find all matching windows
        all_windows = gw.getWindowsWithTitle(title_substring)
        if not all_windows:
            log(f"Window '{title_substring}' not found.", "ERROR")
            SESSION_HWND = None
            return False
        
        # Filter for valid UI windows
        valid_candidates = []
        for w in all_windows:
            h = w._hWnd
            title = win32gui.GetWindowText(h).strip()
            if win32gui.IsWindow(h) and win32gui.IsWindowVisible(h) and title:
                valid_candidates.append((h, title))
        
        if not valid_candidates:
            log(f"No visible UI window matching '{title_substring}' found.", "ERROR")
            SESSION_HWND = None
            return False
            
        hwnd = None
        selected_title = None

        # --- UNIFIED SELECTION LOGIC ---
        
        # 1. Try to reuse SESSION_HWND if it's still valid
        if SESSION_HWND:
            matches = [v for v in valid_candidates if v[0] == SESSION_HWND]
            if matches:
                hwnd, selected_title = matches[0]
                log(f"Reusing session window: '{selected_title}'", "DEBUG")
        
        # 2. If no session hwnd or it was lost, handle selection
        if not hwnd:
            if len(valid_candidates) > 1:
                log(f"Found {len(valid_candidates)} matching windows. Please select one:", "ACTION")
                
                # Use GUI dialog for selection (works with pythonw.exe)
                import tkinter as tk
                from tkinter import ttk
                
                selected_idx = [None]  # Use list to allow modification in nested function
                
                def on_select():
                    selection = listbox.curselection()
                    if selection:
                        selected_idx[0] = selection[0]
                        root.destroy()
                
                def on_double_click(event):
                    on_select()
                
                # Create selection dialog
                root = tk.Tk()
                root.title("Select window to capture")
                root.geometry("600x300")
                root.resizable(False, False)
                
                # Center window on screen
                root.update_idletasks()
                x = (root.winfo_screenwidth() // 2) - (600 // 2)
                y = (root.winfo_screenheight() // 2) - (300 // 2)
                root.geometry(f"+{x}+{y}")
                
                # Make window always on top
                root.attributes('-topmost', True)
                
                # Label
                label = tk.Label(root, text=f"Found {len(valid_candidates)} windows. Please select one:", 
                                font=("Segoe UI", 10))
                label.pack(pady=10)
                
                # Listbox with scrollbar
                frame = tk.Frame(root)
                frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
                
                scrollbar = tk.Scrollbar(frame)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=("Consolas", 9))
                listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.config(command=listbox.yview)
                
                # Add items
                for i, (h, t) in enumerate(valid_candidates):
                    listbox.insert(tk.END, f"[{i+1}] {t} (HWND: {h})")
                
                # Select first item by default
                listbox.selection_set(0)
                listbox.bind('<Double-Button-1>', on_double_click)
                
                # Button
                btn = tk.Button(root, text="Select", command=on_select, font=("Segoe UI", 10), 
                               bg="#25D366", fg="white", padx=20, pady=5)
                btn.pack(pady=10)
                
                root.mainloop()
                
                if selected_idx[0] is not None:
                    hwnd, selected_title = valid_candidates[selected_idx[0]]
                else:
                    # User closed window without selecting, use first one
                    hwnd, selected_title = valid_candidates[0]
                    log("No selection made, using first window.", "WARNING")
            else:
                hwnd, selected_title = valid_candidates[0]
            
            # Save to session for subsequent calls
            SESSION_HWND = hwnd
            log(f"Window locked for this session: '{selected_title}'", "SUCCESS")

        log(f"Focusing window: '{selected_title}' (HWND: {hwnd})", "ACTION")
        
        # --- ULTIMATE ACTIVATION SEQUENCE ---
        
        # 1. Disable foreground lock
        try:
            win32api.SystemParametersInfo(win32con.SPI_SETFOREGROUNDLOCKTIMEOUT, 0, 
                                          win32con.SPIF_SENDWININICHANGE | win32con.SPIF_UPDATEINIFILE)
        except: pass

        # 2. Force Show/Restore even if not perceived as iconic
        # Some apps (like Photos) can be in a "pseudo-minimized" or background state
        log("Triggering aggressive show/restore...", "DEBUG")
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SendMessage(hwnd, win32con.WM_SYSCOMMAND, win32con.SC_RESTORE, 0)
        
        # 3. Maximize
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
        time.sleep(0.5)
        
        # 4. Force Foreground
        def force_foreground(h):
            try:
                # Try standard
                win32gui.SetForegroundWindow(h)
                win32gui.BringWindowToTop(h)
                return True
            except:
                # Try thread attachment
                try:
                    fore_thread = win32gui.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
                    target_thread = win32gui.GetWindowThreadProcessId(h)[0]
                    if fore_thread != target_thread:
                        win32process.AttachThreadInput(fore_thread, target_thread, True)
                        win32gui.SetForegroundWindow(h)
                        win32process.AttachThreadInput(fore_thread, target_thread, False)
                        return True
                except: pass
                return False

        if not force_foreground(hwnd):
            pyautogui.press('alt') # Bypasses some restrictions
            try: win32gui.SetForegroundWindow(hwnd)
            except: pass
        
        if keep_on_top:
            # HWND_TOPMOST = -1, HWND_NOTOPMOST = -2
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            log("Window set to Always on Top.", "DEBUG")
            
        time.sleep(1.5)
        return True
    except Exception as e:
        log(f"Activation error: {e}", "ERROR")
        return False

def reset_window_topmost(title_substring):
    if not title_substring: return
    try:
        windows = gw.getWindowsWithTitle(title_substring)
        if windows:
            hwnd = windows[0]._hWnd
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            log("Window topmost status reset.", "DEBUG")
    except Exception as e:
        log(f"Reset topmost error: {e}", "DEBUG")

def perform_ocr(screenshot, timestamp_str):
    """
    EasyOCR Implementation with conditional allowlist:
    - Title region: Alphanumeric (to capture "Overall Index")
    - Other regions: Numeric only (0-9 and .)
    """
    results = {}
    log("Starting EasyOCR Analysis...", "OCR")
    
    for region in CONFIG['regions']:
        name, x, y, w, h = region['name'], region['x'], region['y'], region['width'], region['height']
        is_title = "title" in name.lower()
        
        # 1. Take initial crop
        roi_pil = screenshot.crop((x, y, x + w, y + h))
        
        # 2. Convert to Grayscale & 3x Upscale
        gray_pil = roi_pil.convert('L')
        final_pil = gray_pil.resize((w * 3, h * 3), Image.Resampling.LANCZOS)
        
        # 3. Contrast Enhancement
        enhancer = ImageEnhance.Contrast(final_pil)
        final_pil = enhancer.enhance(2.5)
        
        # 4. Save debug
        debug_name = f"debug_{name.replace(' ', '_')}_{timestamp_str}.png"
        debug_path = os.path.join(SCREENSHOT_DIR, debug_name)
        final_pil.save(debug_path)
        
        # 5. Convert to format EasyOCR expects
        img_np = np.array(final_pil)
        
        # 6. EasyOCR Recognition with dynamic allowlist
        if is_title:
            # For Title, we allow letters to capture "Overall Index"
            ocr_results = READER.readtext(img_np, detail=0)
            text = " ".join(ocr_results).strip()
        else:
            # For data, we restrict to numbers and dots
            ocr_results = READER.readtext(img_np, detail=0, allowlist='0123456789.')
            text = "".join(ocr_results).strip()
            text = text.replace(' ', '').replace(',', '.')
             
        log(f"OCR Result [{name}]: {text}", "OCR")
        results[name] = text
    
    return results

def cleanup_old_screenshots():
    days = CONFIG.get('max_retention_days', 3)
    cutoff = datetime.now() - timedelta(days=days)
    log(f"Cleaning images older than {days} days...", "DEBUG")
    count = 0
    for f in os.listdir(SCREENSHOT_DIR):
        file_path = os.path.join(SCREENSHOT_DIR, f)
        if os.path.getmtime(file_path) < cutoff.timestamp():
            os.remove(file_path)
            count += 1
    if count > 0: log(f"Deleted {count} old screenshots.", "SUCCESS")

def job(is_test=False):
    global CONFIG, SESSION_HWND
    log("="*40, "INFO")
    log("Starting scheduled job...", "ACTION")
    
    try:
        CONFIG = load_config()
        cleanup_old_screenshots()
        
        window_title = CONFIG.get('window_title')
        if activate_window(window_title, keep_on_top=True):
            time.sleep(CONFIG.get('capture_delay_seconds', 1))
            screenshot = pyautogui.screenshot()
            
            # Immediately reset topmost to avoid annoying the user
            reset_window_topmost(window_title)
            
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            main_ss_path = os.path.join(SCREENSHOT_DIR, f"full_{ts}.png")
            screenshot.save(main_ss_path)
            
            ocr_res = perform_ocr(screenshot, ts)
            
            # --- Validation Logic ---
            title_text = ocr_res.get("Title", "").lower()
            dc = ocr_res.get("DC", "").strip()
            aws = ocr_res.get("AWS", "").strip()
            tap = ocr_res.get("TAP", "").strip()

            # 1. Validate Title
            if "overall index" not in title_text:
                log(f"Stop sending: 'Overall Index' not found in Title (found '{title_text}').", "ERROR")
                log("Screenshot is incorrect. Clearing saved window to reselect on next attempt.", "WARNING")
                SESSION_HWND = None
                return False

            # 2. Validate Data Values (DC, AWS, TAP)
            if not dc or not aws or not tap:
                log(f"Stop sending: Missing or unrecognized data (DC='{dc}', AWS='{aws}', TAP='{tap}').", "ERROR")
                log("One or more values could not be identified. Clearing saved window to reselect on next attempt.", "WARNING")
                SESSION_HWND = None
                return False

            log("'Overall Index' and data values confirmed. Proceeding to send report...", "SUCCESS")

            # Format custom message
            caption = (
                f"BC BLĐ: Hiện tại {dc} TB đang hoạt động, "
                f"tốc độ gió {aws} m/s, "
                f"công suất phát {tap} MW"
            )
            
            # Always send the report, even in test mode
            client = WPPConnectClient(CONFIG['wpp_base_url'], CONFIG['wpp_session'], CONFIG['wpp_secret_key'])
            if client.send_image(CONFIG['phone_number'], main_ss_path, caption):
                if is_test:
                    log(f"Test result sent via WhatsApp:\n{caption}", "DEBUG")
                log("Job finished successfully.", "SUCCESS")
                return True
            else:
                log("WhatsApp report delivery failed.", "ERROR")
                return False
        else:
            log(f"Window activation failed. Skipping this capture attempt.", "ERROR")
            return False

            
    except Exception as e:
        log(f"Job failed: {e}", "ERROR")
        return False
    
    return False

# --- Main Logic ---
if __name__ == "__main__":
    if "--test" in sys.argv:
        log("Running in TEST mode with auto-retry...", "ACTION")
        while True:
            success = job(is_test=True)
            if success:
                break
            log("Test run failed. Retrying in 10 seconds...", "WARNING")
            time.sleep(10)
    else:
        log("Bot started. Interactive setup...", "SUCCESS")
        
        # 1. Immediate setup: Ask user to select window
        window_title = CONFIG.get('window_title')
        activate_window(window_title)
        
        def pick_next_run(hour_offset=0, force_random=True):
            """Picks a random minute between 0-10 for the target hour."""
            target_time = datetime.now() + timedelta(hours=hour_offset)
            random_minute = random.randint(0, 10)
            return target_time.replace(minute=random_minute, second=0, microsecond=0)
        
        # 2. Determine first run (Random minute 0-10)
        now = datetime.now()
        if now.minute < 10:
            # Pick a minute between now+1 and 10
            start_min = now.minute + 1
            random_minute = random.randint(start_min, 10)
            next_run = now.replace(minute=random_minute, second=0, microsecond=0)
        else:
            # Too late for this hour, pick next hour (0-10)
            next_run = pick_next_run(1)

        log(f"First run scheduled at: {next_run.strftime('%H:%M:%S')}", "INFO")

        while True:
            now = datetime.now()
            if now >= next_run:
                success = job()
                
                if success:
                    # Successful run, schedule for next hour
                    next_run = pick_next_run(1)
                    log(f"Success! Next scheduled run at: {next_run.strftime('%H:%M:%S')}", "SUCCESS")
                else:
                    # Failed (Window missing or OCR error), retry in 5 minutes
                    next_run = now + timedelta(minutes=5)
                    log(f"Job failed (Window missing or OCR error). Retrying in 5 minutes at: {next_run.strftime('%H:%M:%S')}", "WARNING")
            
            # Sleep 30 seconds between checks
            time.sleep(30)
