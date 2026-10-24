import os
import sys
import json
import time
import datetime
import threading
import ctypes
import logging
import winreg
import pathlib
from tkinter import messagebox, filedialog
import customtkinter as ctk
import psutil
from send2trash import send2trash
from plyer import notification

# --- Configuration & Constants ---
APP_DATA_DIR = os.path.join(pathlib.Path.home(), 'AppData', 'Local', 'TempCleanerApp')
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')
LOG_FILE = os.path.join(APP_DATA_DIR, 'cleaner.log')
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

os.makedirs(APP_DATA_DIR, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

def get_system_metrics():
    return psutil.cpu_percent(interval=0.5), psutil.virtual_memory().percent

def is_safe_to_clean(cpu, ram):
    return cpu < 86.0 and ram < 85.0

def get_folder_size_gb(path):
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                try: total_size += os.path.getsize(fp)
                except: pass
    return total_size / (1024 ** 3)

class ConfigManager:
    def __init__(self):
        self.config = {
            "schedule": ["Monday", "Thursday"], 
            "last_auto_clean_date": "", 
            "autostart": False, 
            "target_directory": "", 
            "clean_by_size": False, 
            "size_limit_gb": 5.0,
            "empty_rb_hours": "24",
            "last_rb_empty_time": time.time()
        }
        self.load()
    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f: self.config.update(json.load(f))
            except Exception as e:
                logging.error(f"Load error: {e}")
        else: 
            self.save()
    def save(self):
        try:
            with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f, indent=4)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

class TempCleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Windows Temp Cleaner")
        self.geometry("550x700")
        self.minsize(450, 500)
        self.resizable(True, True)
        
        self.config_mgr = ConfigManager()
        
        self.setup_gui()
        self.monitor_thread = threading.Thread(target=self.background_monitor, daemon=True)
        self.monitor_thread.start()

    def setup_gui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) 
        
        main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_scroll.grid(row=0, column=0, sticky="nsew")
        main_scroll.grid_columnconfigure(0, weight=1)
        
        # Target Directory
        dir_frame = ctk.CTkFrame(main_scroll)
        dir_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        dir_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(dir_frame, text="Target Directory", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")
        
        saved_dir = self.config_mgr.config.get("target_directory", "")
        self.dir_var = ctk.StringVar(value=saved_dir)
        self.dir_entry = ctk.CTkEntry(dir_frame, textvariable=self.dir_var)
        self.dir_entry.grid(row=1, column=0, padx=(10, 5), pady=(0, 10), sticky="ew")
        self.dir_entry.configure(state="readonly")
        
        ctk.CTkButton(dir_frame, text="Browse", width=80, command=self.browse_directory).grid(row=1, column=1, padx=(0, 10), pady=(0, 10))

        # Triggers
        trigger_frame = ctk.CTkFrame(main_scroll)
        trigger_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(trigger_frame, text="Automatic Triggers", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        size_frame = ctk.CTkFrame(trigger_frame, fg_color="transparent")
        size_frame.pack(fill="x", padx=10, pady=5)
        self.size_trigger_var = ctk.BooleanVar(value=self.config_mgr.config.get("clean_by_size", False))
        ctk.CTkSwitch(size_frame, text="Clean when size exceeds (GB):", variable=self.size_trigger_var).pack(side="left")
        self.size_limit_var = ctk.StringVar(value=str(self.config_mgr.config.get("size_limit_gb", 5.0)))
        ctk.CTkEntry(size_frame, textvariable=self.size_limit_var, width=60).pack(side="left", padx=10)

        ctk.CTkLabel(trigger_frame, text="Scheduled Days:").pack(anchor="w", padx=10, pady=(10, 0))
        self.day_vars = {}
        for day in DAYS_OF_WEEK:
            var = ctk.BooleanVar(value=(day in self.config_mgr.config["schedule"]))
            self.day_vars[day] = var
            ctk.CTkCheckBox(trigger_frame, text=day, variable=var).pack(anchor="w", padx=15, pady=2)

        # Settings
        settings_frame = ctk.CTkFrame(main_scroll)
        settings_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(settings_frame, text="System Actions", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.autostart_var = ctk.BooleanVar(value=self.config_mgr.config["autostart"])
        ctk.CTkSwitch(settings_frame, text="Run silently at Windows Startup", variable=self.autostart_var, command=self.toggle_autostart).pack(anchor="w", padx=10, pady=5)
        
        rb_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        rb_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(rb_frame, text="Empty Recycle Bin After:").pack(side="left")
        self.rb_var = ctk.StringVar(value=self.config_mgr.config.get("empty_rb_hours", "24"))
        ctk.CTkOptionMenu(rb_frame, variable=self.rb_var, values=["24", "48", "72", "Never"]).pack(side="left", padx=10)

        ctk.CTkButton(settings_frame, text="Save Settings", command=self.save_settings).pack(pady=(15, 5))
        
        btn_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(btn_frame, text="Clean Now", fg_color="#2b7b4a", hover_color="#1e5c36", command=self.request_manual_clean).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkButton(btn_frame, text="View Logs", command=self.view_logs).pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Status
        status_frame = ctk.CTkFrame(main_scroll)
        status_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        main_scroll.grid_rowconfigure(3, weight=1)
        
        ctk.CTkLabel(status_frame, text="Real-Time Status", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        initial_status = "Status: Monitoring..." if saved_dir else "Waiting for configuration..."
        self.status_var = ctk.StringVar(value=initial_status)
        ctk.CTkLabel(status_frame, textvariable=self.status_var, text_color="#3a7ebf", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10)
        self.last_run_var = ctk.StringVar(value=f"Last Auto Run: {self.config_mgr.config['last_auto_clean_date'] or 'Never'}")
        ctk.CTkLabel(status_frame, textvariable=self.last_run_var).pack(anchor="w", padx=10)
        self.summary_var = ctk.StringVar(value="Last Result - Binned: 0 | Skipped: 0")
        ctk.CTkLabel(status_frame, textvariable=self.summary_var).pack(anchor="w", padx=10, pady=(0, 10))

    def browse_directory(self):
        d = filedialog.askdirectory(title="Select Folder")
        if d:
            self.dir_entry.configure(state="normal")
            self.dir_var.set(d)
            self.dir_entry.configure(state="readonly")
            self.config_mgr.config["target_directory"] = d
            self.config_mgr.save()
            self.update_status("Status: Directory configured. Waiting...")

    def save_settings(self):
        self.config_mgr.config["schedule"] = [d for d, v in self.day_vars.items() if v.get()]
        self.config_mgr.config["clean_by_size"] = self.size_trigger_var.get()
        self.config_mgr.config["empty_rb_hours"] = self.rb_var.get()
        try: self.config_mgr.config["size_limit_gb"] = float(self.size_limit_var.get())
        except: return messagebox.showerror("Error", "Size must be a number.")
        self.config_mgr.save()
        messagebox.showinfo("Success", "Settings saved.")

    def toggle_autostart(self):
        enable = self.autostart_var.get()
        key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                cmd = f'"{sys.executable}" --silent' if sys.executable.lower().endswith("exe") else f'"{sys.executable}" "{os.path.abspath(__file__)}" --silent'
                winreg.SetValueEx(k, "WindowsTempCleaner", 0, winreg.REG_SZ, cmd)
            else:
                try: winreg.DeleteValue(k, "WindowsTempCleaner")
                except: pass
            winreg.CloseKey(k)
            self.config_mgr.config["autostart"] = enable
            self.config_mgr.save()
        except Exception as e:
            self.autostart_var.set(not enable)

    def request_manual_clean(self):
        if not self.config_mgr.config.get("target_directory"): 
            return messagebox.showwarning("Error", "Select a directory first.")
            
        self.update_status("Status: Moving to Recycle Bin immediately...")
        self.perform_cleanup(is_manual=True) 

    def perform_cleanup(self, is_manual=False):
        tgt = self.config_mgr.config.get("target_directory")
        
        if tgt:
            tgt = os.path.normpath(tgt)
            
        if not tgt or not os.path.exists(tgt): 
            return self.update_status("Status: Target missing. Please reselect folder.")
            
        self.update_status("Status: Moving files to Recycle Bin...")
        d, s = 0, 0
        for item in os.listdir(tgt):
            p = os.path.normpath(os.path.join(tgt, item))
            try:
                send2trash(p)
                d += 1
            except: s += 1
            
        self.after(0, self.summary_var.set, f"Last Result - Binned: {d} | Skipped: {s}")
        if not is_manual:
            today = datetime.date.today().isoformat()
            self.config_mgr.config["last_auto_clean_date"] = today
            self.config_mgr.save()
            self.after(0, self.last_run_var.set, f"Last Auto Run: {today}")
            
        rb_hours = self.config_mgr.config.get("empty_rb_hours", "24")
        retention_text = "until you manually empty it." if rb_hours == "Never" else f"for {rb_hours} hours."
        
        try:
            notification.notify(
                title="Temp Cleaner",
                message=f"Cleaned {d} items. They will remain in your Recycle Bin {retention_text}",
                app_name="Temp Cleaner",
                timeout=7
            )
        except Exception as e:
            logging.error(f"Failed to send notification: {e}")
            
        self.update_status("Status: Finished. Monitoring...")

    def update_status(self, txt): self.after(0, self.status_var.set, txt)

    def background_monitor(self):
        while True:
            try:
                rb_hours_str = self.config_mgr.config.get("empty_rb_hours", "24")
                if rb_hours_str != "Never":
                    hours = int(rb_hours_str)
                    last_empty = self.config_mgr.config.get("last_rb_empty_time", 0.0)
                    if time.time() - last_empty >= (hours * 3600):
                        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
                        self.config_mgr.config["last_rb_empty_time"] = time.time()
                        self.config_mgr.save()

                tgt = self.config_mgr.config.get("target_directory")
                if not tgt:
                    time.sleep(30)
                    continue
                
                today = datetime.date.today().isoformat()
                if self.config_mgr.config.get("last_auto_clean_date") != today:
                    run = False
                    if self.config_mgr.config.get("clean_by_size") and os.path.exists(tgt):
                        if get_folder_size_gb(tgt) >= self.config_mgr.config.get("size_limit_gb", 5.0): run = True
                    if not run and datetime.date.today().strftime("%A") in self.config_mgr.config.get("schedule", []): run = True
                    
                    if run: 
                        c, r = get_system_metrics()
                        safe = is_safe_to_clean(c, r)
                        if safe:
                            self.perform_cleanup(False) 
                        else:
                            self.update_status("Status: Waiting for resources (Auto)")
                    else: 
                        self.update_status("Status: Monitoring...")
                else: 
                    self.update_status("Status: Already ran today. Sleeping...")
            except: pass
            time.sleep(30)

    def view_logs(self):
        w = ctk.CTkToplevel(self)
        w.title("Logs")
        w.geometry("600x400")
        t = ctk.CTkTextbox(w)
        t.pack(fill="both", expand=True, padx=10, pady=10)
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f: t.insert("0.0", f.read())
        t.configure(state="disabled")

if __name__ == "__main__":
    app = TempCleanerApp()
    if "--silent" in sys.argv:
        app.withdraw()
    app.mainloop()