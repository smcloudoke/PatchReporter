# Patch Reporter

A Windows desktop app for tracking and approving monthly Microsoft patch releases per customer. Pulls updates automatically from the MSRC CVRF API and Microsoft Update Catalog, organizes them by category, and generates Outlook draft emails ready to send.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-informational) ![UI](https://img.shields.io/badge/UI-CustomTkinter-blueviolet)

---

## Features

- **Automated KB pull** — fetches current month's Cumulative Updates, Servicing Stack Updates, and .NET Framework updates via MSRC CVRF API + Microsoft Update Catalog
- **Per-customer product filters** — scope pulls and table display to specific OS families (Windows 10/11, Server 2016/2019/2022/2025) and architecture (x64/x86/ARM64)
- **Manual KB entry** — add any KB manually if it isn't caught by the automated pull
- **Outlook draft export** — generates a formatted HTML email draft addressed to the customer's contacts
- **Customer management** — add, edit, and delete customers; all data persists locally in SQLite
- **Dark mode UI** — built with CustomTkinter

---

## Requirements

- Windows 10/11 or Windows Server
- Microsoft Outlook (desktop client) for email draft export
- Python 3.10+ *(only needed if running from source)*

---

## Running from Source

```bash
pip install -r requirements.txt
python approvalreport.py
```

---

## Building the Executable

Run `build.bat` on a Windows machine. It installs all dependencies and produces a single self-contained `PatchReporter.exe` via PyInstaller.

```bat
build.bat
```

Output: `dist\PatchReporter.exe`

> **Note:** Keep `PatchReporter.exe` in a stable folder (e.g. `Documents\PatchReporter\`) so the database file persists between runs.

---

## Project Structure

| File | Purpose |
|---|---|
| `approvalreport.py` | Entry point |
| `constants.py` | App-wide constants and configuration |
| `db.py` | SQLite persistence (customers, KB entries) |
| `msrc.py` | KB fetching, parsing, classifying, and filtering |
| `report.py` | Outlook email body builder |
| `ui.py` | All UI — main app and customer dialog |
| `requirements.txt` | Python dependencies |
| `build.bat` | Windows build script |

---

## Data Storage

Customer records and KB entries are stored in `patchreport.db` (SQLite), created automatically in the same directory as the executable on first run. This file is local only and not committed to the repository.
