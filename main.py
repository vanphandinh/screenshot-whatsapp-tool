import json
import os
import time
import base64
import requests
import pyautogui
import pytesseract
import pygetwindow as gw
from PIL import Image
import schedule
from datetime import datetime
import sys

# --- CONFIGURATION ---
def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = load_config()
SCREENSHOT_DIR = "screenshots"

# Ensure screenshot directory exists
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

# Setup Tesseract
TESS_PATH = os.path.normpath(CONFIG['tesseract_path'])
pytesseract.tesseract_cmd = TESS_PATH
TESS_DIR = os.path.dirname(TESS_PATH)
if os.path.exists(TESS_DIR):
    os.environ['PATH'] += os.pathsep + TESS_DIR


def log(msg, level="INFO"):
    """Professional logging with emojis and timestamps."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji = "ℹ️"
    if level == "SUCCESS": emoji = "✅"
    elif level == "ERROR": emoji = "❌"
    elif level == "DEBUG": emoji = "🛠️"
    elif level == "ACTION": emoji = "🚀"
    elif level == "OCR": emoji = "🔍"
    
    print(f"[{timestamp}] {emoji} {msg}")

class WPPConnectClient:
    """Handles communication with self-hosted WPPConnect-Server."""
    def __init__(self, base_url, session, secret_key=""):
        self.base_url = base_url.rstrip('/')
        self.session = session
        self.secret_key = secret_key
        self.token = None
        self.headers = {
            "Content-Type": "application/json"
        }

    def _generate_token(self):
        """Generates an access token using the secret key."""
        if not self.secret_key:
            return False
            
        url = f"{self.base_url}/api/{self.session}/{self.secret_key}/generate-token"
        log(f"Generating token for session '{self.session}'...", "DEBUG")
        try:
            response = requests.post(url, timeout=15)
            if response.status_code in [200, 201]:
                data = response.json()
                self.token = data.get('token')
                if self.token:
                    self.headers["Authorization"] = f"Bearer {self.token}"
                    return True
            log(f"Token generation failed: {response.status_code}", "ERROR")
        except Exception as e:
            log(f"Token exception: {e}", "ERROR")
        return False

    def send_image_file(self, phone_number, file_path, caption):
        """Sends an image file via WPPConnect API by converting to Base64."""
        if not self.token:
            if not self._generate_token():
                log("Cannot proceed without a valid token.", "ERROR")
                return False

        chat_id = f"{phone_number.replace('+', '')}"
        
        try:
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                base64_data = f"data:image/png;base64,{base64_image}"
        except Exception as e:
            log(f"Error encoding image: {e}", "ERROR")
            return False

        url = f"{self.base_url}/api/{self.session}/send-image"
        
        payload = {
            "phone": chat_id,
            "base64": base64_data,
            "caption": caption
        }
        
        log(f"Sending image to {phone_number}...", "ACTION")
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=45)
            
            if response.status_code == 401:
                log("Token expired. Refreshing...", "DEBUG")
                if self._generate_token():
                    response = requests.post(url, headers=self.headers, json=payload, timeout=45)

            if response.status_code in [200, 201]:
                log("Message sent successfully!", "SUCCESS")
                return True
            else:
                log(f"Send failed: {response.status_code} - {response.text}", "ERROR")
        except Exception as e:
            log(f"WPPConnect exception: {e}", "ERROR")
        return False


def activate_window(title_substring):
    """Finds and activates a window with a much more robust sequence."""
    try:
        if not title_substring:
            return True
            
        windows = gw.getWindowsWithTitle(title_substring)
        if not windows:
            log(f"Window '{title_substring}' not found.", "ERROR")
            return False
        
        target = windows[0]
        log(f"Focusing window: '{target.title}'", "ACTION")
        
        if target.isMinimized:
            target.restore()
        
        try:
            target.show()
            target.activate()
        except Exception:
            pyautogui.press('alt') 
            target.activate()
            
        time.sleep(1.5) 
        return True
    except Exception as e:
        log(f"Activation error: {e}", "ERROR")
        return False


def capture_screen():
    """Captures the full screen after activating the target window."""
    target_title = CONFIG.get('window_title', '')
    if target_title:
        if not activate_window(target_title):
            log("Capturing current screen (window focus failed).", "DEBUG")
    
    filename = f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    
    delay = CONFIG.get('capture_delay_seconds', 1)
    if delay > 0:
        time.sleep(delay)
    
    screenshot = pyautogui.screenshot()
    screenshot.save(filepath)
    log(f"Screenshot saved: {filepath}", "SUCCESS")
    return screenshot, filepath


def perform_ocr(screenshot, timestamp_str):
    """Extracts text from defined regions with 3x upscale and underline removal."""
    results = []
    log("Starting OCR processing...", "OCR")
    
    for region in CONFIG['regions']:
        x, y, w, h = region['x'], region['y'], region['width'], region['height']
        roi = screenshot.crop((x, y, x + w, y + h))
        
        if h > 5:
            roi = roi.crop((0, 0, w, h - 3)) 
            new_h = h - 3
        else:
            new_h = h

        processed = roi.resize((w * 3, new_h * 3), Image.Resampling.LANCZOS)
        
        debug_name = f"debug_{region['name'].replace(' ', '_')}_{timestamp_str}.png"
        debug_path = os.path.join(SCREENSHOT_DIR, debug_name)
        processed.save(debug_path)
        
        custom_config = '--oem 3 --psm 7'
        text = pytesseract.image_to_string(processed, lang='eng+vie', config=custom_config).strip()
        text = text.replace(' ', '')
             
        log(f"OCR Result [{region['name']}]: {text}", "OCR")
        results.append(f"- {region['name']}: {text}")
    
    return "\n".join(results)


def cleanup_old_files():
    """Deletes files in SCREENSHOT_DIR older than X days."""
    retention_days = CONFIG.get('max_retention_days', 3)
    
    now = time.time()
    cutoff = now - (retention_days * 86400)
    
    count = 0
    try:
        if os.path.exists(SCREENSHOT_DIR):
            for filename in os.listdir(SCREENSHOT_DIR):
                filepath = os.path.join(SCREENSHOT_DIR, filename)
                if os.path.isfile(filepath):
                    file_mtime = os.path.getmtime(filepath)
                    if file_mtime < cutoff:
                        os.remove(filepath)
                        count += 1
        if count > 0:
            log(f"Cleanup: Removed {count} old files.", "DEBUG")
    except Exception as e:
        log(f"Cleanup error: {e}", "ERROR")


def job():
    """The main task to be executed periodically."""
    print("\n" + "═"*50)
    log(f"BOT TASK STARTED", "ACTION")
    
    cfg = load_config()
    cleanup_old_files()

    img, path = capture_screen()
    timestamp_file = datetime.now().strftime('%Y%m%d_%H%M%S')
    timestamp_msg = datetime.now().strftime('%H:%M %d/%m/%Y')
    
    info_text = perform_ocr(img, timestamp_file)
    content = f"Thông báo tự động ({timestamp_msg}):\n{info_text}"
    
    client = WPPConnectClient(
        cfg['wpp_base_url'], 
        cfg['wpp_session'], 
        cfg['wpp_secret_key']
    )
    client.send_image_file(cfg['phone_number'], path, content)
    log("BOT TASK COMPLETED", "SUCCESS")
    print("═"*50 + "\n")


def start_app():
    """Starts the scheduler."""
    if not os.path.exists(TESS_PATH):
        log(f"Tesseract not found at {TESS_PATH}", "ERROR")
        return

    # Job runs every hour at the 5th minute (e.g. 10:05, 11:05)
    schedule.every().hour.at(":05").do(job)
    
    print("\n" + "🚀 " + "WhatsApp Screenshot Bot is Running".center(46) + " 🚀")
    print("─"*50)
    log("Schedule: Every hour at :05")
    log(f"Target: '{CONFIG.get('window_title', 'None')}'")
    log("Press CTRL+C to stop")
    print("─"*50)
    
    # Run once immediately if you want to test, or wait for the next :05
    # job() 
    
    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    # Check for test mode
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("\n" + "🧪 " + "Running in TEST MODE".center(46) + " 🧪")
        print("─"*50)
        try:
            job()
            log("Test completed successfully.", "SUCCESS")
        except Exception as e:
            log(f"Test failed: {e}", "ERROR")
        sys.exit(0)
        
    try:
        start_app()
    except KeyboardInterrupt:
        print("\n" + "─"*50)
        log("Bot stopped by user.", "INFO")
        print("─"*50)
