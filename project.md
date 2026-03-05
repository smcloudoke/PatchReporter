# Patch Reporter — Project Status

## Overview
This project started from a CLI script (`approvalreport.py`) that read KBs from a text file and generated a DOCX patch report.
It has been upgraded into a fully packaged GUI desktop application for Windows, distributed as a single `PatchReporter.exe`.

## Accomplishments

### 1. Replaced text-file workflow with a GUI app
- Converted `approvalreport.py` into a Tkinter desktop application.
- Added a two-pane layout:
  - Left sidebar: customer list
  - Right panel: customer details + tabbed KB management

### 2. Added customer management
- Added **File menu** with `Add Customer` and `Quit`.
- Built Add/Edit customer dialog with fields: Company Name, Email Addresses, Patch Policies + Schedule Dates.
- Added right-click context menu on customer list for editing.
- Added local persistence via `customers.json`.

### 3. Added customer detail view
- Selecting a customer displays company name, email addresses, and patch policy/schedule notes.
- Per-customer KB data is loaded/saved automatically.

### 4. Added tabbed KB workflow
- **Automated Pull** tab: `Pull Current Month KBs` button + KB results table (Category, KB, Title).
- **Manual KB Input** tab: input fields for KB Name/Number, `Add Manual KB`, `Remove Selected`, shared KB list view.

### 5. Added Outlook draft export
- Replaced DOCX output with Outlook message drafting via `win32com.client`.
- Uses customer email addresses to populate `To`.
- Builds HTML body using the existing report wording/style as baseline.
- Added a customer-specific **Current Month Schedule** section.

### 6. Added automated monthly KB discovery
- Uses **MSRC CVRF API** for monthly KB discovery.
- Microsoft Update Catalog scraping to enrich/resolve update titles and categories.
- Tries current month first; falls back to previous month if no qualifying KBs are found.

### 7. Expanded pull coverage
- Cumulative Updates
- Servicing Stack Updates (SSU — standalone releases for Server 2016 only; baked into CU for 2019/2022+)
- .NET Framework updates (including security/quality rollups)

### 8. Added KB deletion in automated tab
- `Remove KB` button in Automated Pull tab.
- Updates are persisted per customer.

### 9. Migrated UI from Tkinter to CustomTkinter
- Replaced all `tkinter`/`ttk` widgets with `customtkinter` equivalents.
- Dark mode with blue accent theme.
- **Sidebar:** Fixed-width (248px) dark navy, `CTkScrollableFrame` customer list, one `CTkButton` per customer, `Add Customer` anchored at bottom.
- **Main panel:** Company name card with inline Edit button, policy card, `CTkTabview` tabs, footer bar with status + Draft Outlook Email button.
- **KB tables:** `ttk.Treeview` retained (CTk has no Treeview equivalent), styled with custom `"Patch.Treeview"` dark theme and alternating row colors.
- **Customer dialog:** `CTkToplevel` modal; `grab_set()` deferred via `after(50, ...)` to avoid `grab failed: window not viewable` error.
- File menu removed; replaced by sidebar Add button and inline Edit button.

### 10. Packaged as a standalone Windows executable
- Added `requirements.txt` and `build.bat` for one-click building on Windows.
- PyInstaller flags: `--onefile`, `--windowed`, `--collect-data customtkinter`, `--hidden-import` for pywin32 modules.
- Output: `dist\PatchReporter.exe`

### 11. Separated into modules (separation of concerns)
Split single-file app into focused modules:
| File | Purpose |
|---|---|
| `approvalreport.py` | Entry point only — initialises DB, sets CTk theme, launches app |
| `constants.py` | All constants, color palette, filter configuration |
| `db.py` | All SQLite persistence (CRUD, schema, migration) |
| `msrc.py` | KB fetching, parsing, classifying, product filtering |
| `report.py` | Outlook email body building |
| `ui.py` | All UI — `CustomerDialog` + `ApprovalReportApp` |

### 12. Migrated data persistence from JSON to SQLite
- Replaced `customers.json` flat file with `patchreport.db` (SQLite via stdlib `sqlite3`).
- Schema: `customers` table + `kb_entries` table with `ON DELETE CASCADE`.
- One-time automatic migration: existing `customers.json` is imported on first run and renamed to `customers.json.migrated`.
- `PRAGMA foreign_keys = ON` enforced on every connection.

### 13. Added per-customer patch filters
- Filter card in the main panel (between policy card and tabs) with:
  - 6 product family checkboxes: Windows 10, 11, Server 2016/2019/2022/2025
  - Architecture dropdown: x64 (default), x86, ARM64
- Filters are stored as JSON in a `filters` column on the `customers` table (additive migration — safe for existing DBs).
- Applied in two places:
  - **Pre-pull:** catalog queries are scoped to selected server products (SSU queries generated per selected server, .NET always included).
  - **Post-pull:** Treeview display filters rows using `matches_product_filter()` so only matching titles are shown.
- Auto-saves on every checkbox/dropdown change; re-filters the table immediately.
- Empty product selection = no filter (shows all), preserving backward compatibility.

### 14. Fixed product filter matching for catalog title variants
- Microsoft Update Catalog uses non-obvious naming for some products:
  - Server 2022 → "Microsoft server operating system version 21H2" (not "Windows Server 2022")
  - Server 2025 → "Microsoft server operating system version 24H2" (not "Windows Server 2025")
- Added specific aliases to `PRODUCT_KEYWORDS` in `msrc.py` to match these catalog title formats.
- Removed ambiguous version aliases (`version 1607`, `version 1809`) that caused Windows 10 entries to leak through when only server products were selected.

### 15. Renamed app to Patch Reporter
- `APP_TITLE` updated in `constants.py`.
- Sidebar branding updated in `ui.py`.
- `build.bat` updated to produce `PatchReporter.exe`.

### 16. Version control and GitHub
- Initialized git repository with `main` branch.
- `.gitignore` excludes: `*.db`, `venv/`, `__pycache__/`, `dist/`, `build/`, `.claude/`, `customers.json`.
- Repository: https://github.com/smcloudoke/PatchReporter

## Current App Behavior
- Customer records persist in `patchreport.db` (SQLite, created alongside the `.exe` on first run).
- Per-customer product/architecture filters scope both the pull and the table display.
- KBs can come from automated pull (MSRC CVRF API + catalog) or manual entry.
- Entries can be removed from both automated and manual tabs.
- Report content is generated into an Outlook draft with full HTML formatting.
- App ships as a single `PatchReporter.exe` — no Python install required on the target machine.

## File Overview
| File | Purpose |
|---|---|
| `approvalreport.py` | Entry point |
| `constants.py` | Constants, color palette, filter config |
| `db.py` | SQLite persistence |
| `msrc.py` | KB fetching, parsing, classifying, filtering |
| `report.py` | Outlook email builder |
| `ui.py` | All UI classes |
| `requirements.txt` | Python dependencies |
| `build.bat` | Windows build script → `PatchReporter.exe` |
| `project.md` | This file |
| `CLAUDE.md` | Guidance for Claude Code |

## Technical Notes
- Language/runtime: Python 3
- UI: CustomTkinter (dark mode, blue theme) + `ttk.Treeview` (custom dark styling) + `tk.Menu` (right-click context)
- Networking/parsing: `requests`, `beautifulsoup4`
- Outlook integration: `pywin32` (`win32com.client`) — Windows only
- Data: SQLite via stdlib `sqlite3`
- External data: MSRC CVRF API + Microsoft Update Catalog scraping
- Distribution: PyInstaller `--onefile --windowed`

## Known Limitations / Risks
- Microsoft Update Catalog HTML structure can change and may require parser adjustments.
- Outlook draft requires installed Outlook desktop client and COM availability (Windows only).
- `--onefile` executables have a 2–5 second cold-start delay while assets extract to a temp folder — normal PyInstaller behavior.
- Keep `PatchReporter.exe` in a stable location (e.g., `Documents\PatchReporter\`) so the SQLite DB persists between runs.

## Suggested Next Steps
1. Add a visible indicator showing whether current or previous month data was used for the pull.
2. Add logging/debug export panel for pull diagnostics.
