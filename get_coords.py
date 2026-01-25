import pyautogui
import time
import sys
import json
import os

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"phone_number": "", "tesseract_path": "", "regions": [], "interval_hours": 1}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def main():
    print("=== Coordinate Capture & Config Tool ===")
    
    config = load_config()
    
    # Input region name
    region_name = input("\nEnter name for this region (e.g., Balance, Transaction ID...): ").strip()
    if not region_name:
        region_name = f"Region_{len(config['regions']) + 1}"

    # Get Point 1
    input(f"\n--- Step 1: Capture TOP-LEFT coordinate for '{region_name}' --- \nMove mouse to position and press ENTER here...")
    x1, y1 = pyautogui.position()
    print(f">> Point 1 set: X={x1}, Y={y1}")
    
    # Get Point 2
    input(f"\n--- Step 2: Capture BOTTOM-RIGHT coordinate for '{region_name}' --- \nMove mouse to position and press ENTER here...")
    x2, y2 = pyautogui.position()
    print(f">> Point 2 set: X={x2}, Y={y2}")
    
    # Calculate
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    x = min(x1, x2)
    y = min(y1, y2)
    
    new_region = {
        "name": region_name,
        "x": int(x),
        "y": int(y),
        "width": int(width),
        "height": int(height)
    }
    
    # Update config
    config['regions'].append(new_region)
    save_config(config)
    
    print("\n" + "="*40)
    print(f"REGION SAVED SUCCESSFULLY: '{region_name}'")
    print(json.dumps(new_region, indent=4, ensure_ascii=False))
    print(f"All configuration has been updated in {CONFIG_FILE}")
    print("="*40)
    
    choice = input("\nDo you want to capture another region? (y/n): ").lower()
    if choice == 'y':
        main()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExited.")
