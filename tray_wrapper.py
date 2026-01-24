import os
import sys
import threading
import queue
from datetime import datetime
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# Global variables
log_queue = queue.Queue(maxsize=100)
bot_thread = None
stop_event = threading.Event()
original_print = print

def create_icon():
    """Create a simple icon for the system tray"""
    # Create a 64x64 icon with a simple design
    width = 64
    height = 64
    color1 = (34, 139, 34)  # Green
    color2 = (255, 255, 255)  # White
    
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    
    # Draw a simple "W" for WhatsApp
    dc.rectangle([10, 15, 15, 50], fill=color2)
    dc.rectangle([15, 45, 25, 50], fill=color2)
    dc.rectangle([25, 30, 30, 50], fill=color2)
    dc.rectangle([30, 45, 40, 50], fill=color2)
    dc.rectangle([40, 15, 45, 50], fill=color2)
    
    return image

def custom_print(*args, **kwargs):
    """Override print to capture logs"""
    # Call original print
    original_print(*args, **kwargs)
    
    # Capture to queue
    message = ' '.join(str(arg) for arg in args)
    try:
        log_queue.put_nowait(message)
    except queue.Full:
        # Remove oldest and add new
        try:
            log_queue.get_nowait()
            log_queue.put_nowait(message)
        except:
            pass

def run_bot():
    """Run the bot in a separate thread"""
    global stop_event
    
    import subprocess
    import sys
    
    # Get the path to the Python interpreter in venv
    python_exe = sys.executable
    main_script = os.path.join(os.path.dirname(__file__), 'main.py')
    
    try:
        # Set environment to force UTF-8 encoding and unbuffered output
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUNBUFFERED'] = '1'  # Force unbuffered output
        
        # Run main.py as a subprocess with -u flag for unbuffered
        process = subprocess.Popen(
            [python_exe, '-u', main_script],  # -u for unbuffered output
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace unencodable characters instead of crashing
            bufsize=0,  # Unbuffered
            universal_newlines=True,
            env=env
        )
        
        # Read output line by line and add to queue
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.rstrip('\n\r')
                if line.strip():  # Only add non-empty lines
                    custom_print(line)
                
        process.wait()
        
    except Exception as e:
        custom_print(f"Bot error: {e}")

def show_logs(icon, item):
    """Show logs in a real-time updating window"""
    import tkinter as tk
    from tkinter import scrolledtext
    
    # Create a window to show logs
    window = tk.Tk()
    window.title("WhatsApp Bot Logs - Real-time")
    window.geometry("900x600")
    
    # Make window stay on top initially
    window.attributes('-topmost', True)
    window.after(100, lambda: window.attributes('-topmost', False))
    
    # Create frame for controls
    control_frame = tk.Frame(window)
    control_frame.pack(fill=tk.X, padx=10, pady=5)
    
    # Auto-scroll checkbox
    auto_scroll_var = tk.BooleanVar(value=True)
    auto_scroll_check = tk.Checkbutton(control_frame, text="Auto-scroll", variable=auto_scroll_var)
    auto_scroll_check.pack(side=tk.LEFT)
    
    # Clear button
    def clear_logs():
        text_area.config(state=tk.NORMAL)
        text_area.delete(1.0, tk.END)
        text_area.insert(tk.END, "Logs cleared. Waiting for new logs...\n")
        text_area.config(state=tk.DISABLED)
    
    clear_btn = tk.Button(control_frame, text="Clear", command=clear_logs)
    clear_btn.pack(side=tk.LEFT, padx=5)
    
    # Status label
    status_label = tk.Label(control_frame, text="● Live", fg="green", font=("Segoe UI", 9, "bold"))
    status_label.pack(side=tk.RIGHT)
    
    # Create scrolled text widget
    text_area = scrolledtext.ScrolledText(window, wrap=tk.WORD, width=100, height=30, 
                                          font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
    text_area.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
    
    # Track displayed logs count
    displayed_count = [0]
    
    def update_logs():
        """Update logs from queue"""
        if not window.winfo_exists():
            return
        
        # Get all current logs
        all_logs = []
        temp_queue = []
        
        while not log_queue.empty():
            try:
                log = log_queue.get_nowait()
                all_logs.append(log)
                temp_queue.append(log)
            except:
                break
        
        # Put them back
        for log in temp_queue:
            try:
                log_queue.put_nowait(log)
            except:
                pass
        
        # Check if there are new logs
        if len(all_logs) > displayed_count[0]:
            # Enable editing
            text_area.config(state=tk.NORMAL)
            
            # Add only new logs
            new_logs = all_logs[displayed_count[0]:]
            for log in new_logs:
                text_area.insert(tk.END, log + '\n')
            
            displayed_count[0] = len(all_logs)
            
            # Auto-scroll if enabled
            if auto_scroll_var.get():
                text_area.see(tk.END)
            
            # Disable editing
            text_area.config(state=tk.DISABLED)
        
        # Schedule next update (500ms)
        window.after(500, update_logs)
    
    # Initial display
    all_logs = []
    temp_queue = []
    
    while not log_queue.empty():
        try:
            log = log_queue.get_nowait()
            all_logs.append(log)
            temp_queue.append(log)
        except:
            break
    
    # Put them back
    for log in temp_queue:
        try:
            log_queue.put_nowait(log)
        except:
            pass
    
    # Display initial logs
    if all_logs:
        text_area.insert(tk.END, '\n'.join(all_logs) + '\n')
        displayed_count[0] = len(all_logs)
    else:
        text_area.insert(tk.END, "Waiting for logs...\n")
    
    text_area.config(state=tk.DISABLED)
    text_area.see(tk.END)
    
    # Start auto-update
    window.after(500, update_logs)
    
    window.mainloop()

def exit_action(icon, item):
    """Exit the application"""
    global stop_event
    stop_event.set()
    icon.stop()
    os._exit(0)

def setup_tray():
    """Setup system tray icon"""
    icon_image = create_icon()
    
    menu = pystray.Menu(
        item('Show Logs', show_logs),
        item('Exit', exit_action)
    )
    
    icon = pystray.Icon("whatsapp_bot", icon_image, "WhatsApp Screenshot Bot", menu)
    return icon

if __name__ == "__main__":
    # Start bot in separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Setup and run system tray
    icon = setup_tray()
    icon.run()
