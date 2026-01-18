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
    print("=== Công cụ lấy tọa độ & Lưu cấu hình ===")
    
    config = load_config()
    
    # Nhập tên vùng
    region_name = input("\nNhập tên cho vùng này (VD: Số dư, Mã GD...): ").strip()
    if not region_name:
        region_name = f"Region_{len(config['regions']) + 1}"

    # Lấy điểm 1
    input(f"\n--- Bước 1: Lấy tọa độ GÓC TRÊN BÊN TRÁI cho '{region_name}' --- \nDi chuyển chuột đến vị trí và nhấn ENTER tại đây...")
    x1, y1 = pyautogui.position()
    print(f">> Đã chốt Điểm 1: X={x1}, Y={y1}")
    
    # Lấy điểm 2
    input(f"\n--- Bước 2: Lấy tọa độ GÓC DƯỚI BÊN PHẢI cho '{region_name}' --- \nDi chuyển chuột đến vị trí và nhấn ENTER tại đây...")
    x2, y2 = pyautogui.position()
    print(f">> Đã chốt Điểm 2: X={x2}, Y={y2}")
    
    # Tính toán
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
    
    # Cập nhật config
    config['regions'].append(new_region)
    save_config(config)
    
    print("\n" + "="*40)
    print(f"ĐÃ LƯU THÀNH CÔNG VÙNG: '{region_name}'")
    print(json.dumps(new_region, indent=4, ensure_ascii=False))
    print(f"Toàn bộ cấu hình đã được cập nhật vào {CONFIG_FILE}")
    print("="*40)
    
    choice = input("\nBạn có muốn lấy thêm vùng khác không? (y/n): ").lower()
    if choice == 'y':
        main()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã thoát.")
