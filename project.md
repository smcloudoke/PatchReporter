# Patch Report GUI Project Status

## Overview
This project started from a CLI script (`approvalreport.py`) that read KBs from a text file and generated a DOCX patch report.
It has now been upgraded to a fully packaged GUI desktop application for Windows, distributed as a single `PatchReport.exe`.

## Accomplishments So Far

### 1. Replaced text-file workflow with a GUI app
- Converted `approvalreport.py` into a Tkinter desktop application.
- Added a two-pane layout:
  - Left sidebar: customer list
  - Right panel: customer details + tabbed KB management

### 2. Added customer management
- Added **File menu** with:
  - `Add Customer`
  - `Quit`
- Built Add/Edit customer dialog with fields:
  - Company Name
  - Customer Email Addresses
  - Patch Policies + Schedule Dates
- Added right-click context menu on customer list for editing.
- Added local persistence via `customers.json`.

### 3. Added customer detail view
- Selecting a customer now displays:
  - Company name
  - Email addresses
  - Patch policy/schedule notes
- Per-customer KB data is loaded/saved automatically.

### 4. Added tabbed KB workflow
- **Automated Pull** tab:
  - `Pull Current Month KBs` button
  - KB results table (Category, KB, Title)
- **Manual KB Input** tab:
  - Input fields for KB Name and KB Number
  - `Add Manual KB`
  - `Remove Selected`
  - Shared KB list view and persistence

### 5. Added Outlook draft export
- Replaced DOCX output with Outlook message drafting.
- Uses customer email addresses to populate `To`.
- Builds HTML body using the existing report wording/style as baseline.
- Added a customer-specific **Current Month Schedule** section.

### 6. Added automated monthly KB discovery improvements
- Initial implementation used catalog scraping only.
- Pull logic was upgraded to use **MSRC CVRF API** for monthly KB discovery.
- Catalog search is still used to enrich/resolve update titles and categories.
- Implemented month behavior:
  - Try current month first
  - Fallback to previous month if current month returns no qualifying KBs

### 7. Expanded pull coverage beyond cumulative updates
- Added explicit query and matching logic to include:
  - Cumulative Updates
  - Servicing Stack Update (targeted to Server 2016 / version 1607 naming)
  - .NET Framework updates (including security/quality rollups)

### 8. Added KB deletion in automated tab
- Added `Remove KB` button in Automated Pull tab.
- Allows deleting unneeded pulled KB entries.
- Updates are persisted per customer.

### 9. Fixed manual tab UI defect
- Resolved scrollbar placement issue where scrollbar appeared in the middle of the KB area.
- Refactored KB table/scrollbar into a dedicated frame so scrollbar stays at far right.

### 10. Migrated UI from Tkinter to CustomTkinter
- Replaced all `tkinter`/`ttk` widgets with `customtkinter` equivalents.
- Applied dark mode appearance with blue accent theme globally.
- **Sidebar redesign:**
  - Fixed-width (248px) dark navy sidebar replaces the plain LabelFrame customer list.
  - App branding ("Patch Report / Approval Builder") displayed at top of sidebar.
  - Customer list is now a `CTkScrollableFrame` with one `CTkButton` per customer.
  - Selected customer highlights with a blue tint; right-click context menu retained.
  - `Add Customer` button anchored to the bottom of the sidebar.
- **Main panel redesign:**
  - Company name displayed in a card with 24pt bold font and an inline **Edit** button.
  - Email addresses shown as a subtitle beneath the company name.
  - Patch Policy / Schedule moved into its own card with a styled read-only textbox.
  - Tabs upgraded to `CTkTabview`.
  - Footer bar with status label on the left and **Draft Outlook Email** button on the right.
- **KB tables:**
  - `ttk.Treeview` retained (CustomTkinter has no Treeview equivalent).
  - Styled with a custom `"Patch.Treeview"` ttk style: dark background, blue column headings, alternating row colors.
- **Customer dialog:**
  - Replaced `simpledialog.Dialog` with a custom `CTkToplevel` modal window.
  - Fixed `grab failed: window not viewable` error by deferring `grab_set()` via `after(50, ...)`.
- **Button hierarchy:**
  - Primary actions (Pull KBs, Add Manual KB, Draft Outlook Email, Save) use the default blue CTk button.
  - Secondary/destructive actions (Remove KB, Remove Selected, Cancel, Edit) use a muted gray style.
- File menu removed; replaced by sidebar Add button and inline Edit button.

### 11. Packaged as a standalone Windows executable
- Added `requirements.txt` covering all runtime dependencies and PyInstaller.
- Added `build.bat` for one-click building on Windows:
  - Installs all dependencies via pip.
  - Runs PyInstaller with the correct flags.
- PyInstaller flags used:
  - `--onefile` — single self-contained `.exe`, no folder required.
  - `--windowed` — no console window on launch.
  - `--collect-data customtkinter` — bundles CustomTkinter theme/asset files.
  - `--hidden-import` entries for `win32com.client`, `win32api`, `win32con`, `pywintypes`.
- Output: `dist\PatchReport.exe` — verified working on Windows with Outlook integration confirmed.

## Current App Behavior
- Customer records persist in `customers.json` (created alongside the `.exe` on first run).
- KBs can come from automated pull (MSRC CVRF API + catalog) or manual entry.
- User can remove entries from both automated and manual tabs.
- Report content is generated into an Outlook draft with full HTML formatting.
- App ships as a single `PatchReport.exe` — no Python install required on the target machine.

## File Overview
| File | Purpose |
|---|---|
| `approvalreport.py` | Main application — all UI and business logic |
| `requirements.txt` | Python dependencies for pip |
| `build.bat` | Windows build script (run on target machine to produce `.exe`) |
| `customers.json` | Runtime data file — auto-created, not committed |
| `project.md` | This file |

## Technical Notes
- Language/runtime: Python 3
- UI: CustomTkinter (dark mode, blue theme) + ttk.Treeview (custom dark styling)
- Networking/parsing: `requests`, `beautifulsoup4`
- Outlook integration: `pywin32` (`win32com.client`)
- External data source: MSRC CVRF API + Microsoft Update Catalog search pages
- Distribution: PyInstaller `--onefile --windowed`

## Dependencies (Windows)
All dependencies are installed automatically by `build.bat`. To install manually:

```bash
pip install customtkinter requests beautifulsoup4 pywin32 pyinstaller
```

## Known Limitations / Risks
- Microsoft Update Catalog HTML structure can change and may require parser adjustments.
- Category matching for SSU/.NET depends on catalog title patterns and may need tuning for edge naming cases.
- Outlook draft requires installed Outlook desktop client and COM availability.
- `--onefile` executables have a 2–5 second cold-start delay while assets are extracted to a temp folder; this is normal PyInstaller behavior.
- `customers.json` is written to the working directory of the `.exe` — keep the executable in a stable location (e.g., `Documents\PatchReport\`) so data persists between runs.

## Suggested Next Steps
1. Add a visible status label indicating whether current month or previous month data was used.
2. Add logging panel / debug export for pull diagnostics.
3. Add product filters (e.g., explicit Windows 10/11/Server scopes).
