# Windows Temp Cleaner

A robust, silent background utility with a modern graphical interface designed to automate folder cleanup. It monitors a target directory (like a Temp or Downloads folder) and moves files to the Windows Recycle Bin based on user-defined schedules or size limits, ensuring background tasks only run when system resources (CPU/RAM) are safely available.

## Features
* **Modern Interface:** Built with CustomTkinter for a sleek, native Windows look.
* **Automated & Manual Triggers:** Clean folders based on a day-of-the-week schedule, a folder size threshold (GB), or instantly via the manual override.
* **Resource Monitoring:** Background automated cleans wait until CPU and RAM usage are safely below 85% before executing.
* **Recycle Bin Management:** Safely moves files to the Recycle Bin instead of permanent deletion, with an option to automatically empty the bin after a set number of hours.
* **Silent Autostart:** Integrates directly with the Windows Registry to run silently in the background on startup.
* **Native Notifications:** Sends Windows desktop alerts when a cleanup completes successfully.

## Prerequisites
Ensure you have Python 3.8+ installed on your system. 

## Installation
Clone this repository and install the required dependencies using pip:

```bash
git clone https://github.com/yourusername/windows-temp-cleaner.git
cd windows-temp-cleaner
pip install -r requirements.txt
```

## Usage
To run the application from the source code:
```bash
python temp_cleaner.py
```
To run the application silently (background mode):
```bash
python temp_cleaner.py --silent
```

## Building the Executable (.exe)
If you want to compile the application into a standalone executable that doesn't require Python to be installed, use PyInstaller. Run the following command in your terminal:

```bash
pyinstaller --noconsole --onefile --collect-all customtkinter --hidden-import send2trash --hidden-import plyer temp_cleaner.py
```
Once compiled, you will find your standalone `temp_cleaner.exe` inside the newly generated `dist/` folder.

## Configuration
All user preferences, schedules, and targets are persistently saved in your local AppData folder at `C:\Users\<YourUsername>\AppData\Local\TempCleanerApp\config.json`. Log files for troubleshooting are also stored in this directory.