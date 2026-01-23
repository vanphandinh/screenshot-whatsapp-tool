import os
import json
import time
import base64
import requests
import schedule
import pyautogui
import pygetwindow as gw
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import easyocr
from datetime import datetime, timedelta

# --- Configuration & Setup ---
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

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

# --- Automation Functions ---
def activate_window(title_substring):
    if not title_substring: return True
    try:
        windows = gw.getWindowsWithTitle(title_substring)
        if not windows:
            log(f"Window '{title_substring}' not found.", "ERROR")
            return False
        
        target = windows[0]
        log(f"Focusing window: '{target.title}'", "ACTION")
        if target.isMinimized: target.restore()
        try:
            target.show()
            target.activate()
        except:
            pyautogui.press('alt')
            target.activate()
        time.sleep(1.5)
        return True
    except Exception as e:
        log(f"Activation error: {e}", "ERROR")
        return False

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
    global CONFIG
    log("="*40, "INFO")
    log("Starting scheduled job...", "ACTION")
    
    try:
        CONFIG = load_config()
        cleanup_old_screenshots()
        
        if activate_window(CONFIG.get('window_title')):
            time.sleep(CONFIG.get('capture_delay_seconds', 1))
            screenshot = pyautogui.screenshot()
            
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            main_ss_path = os.path.join(SCREENSHOT_DIR, f"full_{ts}.png")
            screenshot.save(main_ss_path)
            
            ocr_res = perform_ocr(screenshot, ts)
            
            # --- Validation Logic ---
            title_text = ocr_res.get("Title", "").lower()
            if "overall index" not in title_text:
                log(f"Dừng gửi: Không tìm thấy 'Overall Index' trong Title (thấy '{title_text}').", "ERROR")
                log("Màn hình được chụp không đúng.", "ERROR")
                return

            log("Xác nhận 'Overall Index' thành công. Tiến hành gửi báo cáo...", "SUCCESS")

            # Format custom message
            dc = ocr_res.get("DC", "N/A")
            aws = ocr_res.get("AWS", "N/A")
            tap = ocr_res.get("TAP", "N/A")
            
            caption = (
                f"BC BLĐ: Hiện tại {dc} TB đang hoạt động, "
                f"tốc độ gió {aws} m/s, "
                f"công suất phát {tap} MW"
            )
            
            # Always send the report, even in test mode
            client = WPPConnectClient(CONFIG['wpp_base_url'], CONFIG['wpp_session'], CONFIG['wpp_secret_key'])
            client.send_image(CONFIG['phone_number'], main_ss_path, caption)
            
            if is_test:
                log(f"Test result sent via WhatsApp:\n{caption}", "DEBUG")
            
    except Exception as e:
        log(f"Job failed: {e}", "ERROR")
    log("Job finished.", "INFO")

# --- Main Logic ---
if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        job(is_test=True)
    else:
        log(f"Bot started. Scheduled at XX:05 every hour.", "SUCCESS")
        schedule.every().hour.at(":05").do(job)
        while True:
            schedule.run_pending()
            time.sleep(30)
