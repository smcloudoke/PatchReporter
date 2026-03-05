# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
# Activate the venv first (Linux/dev)
source venv/bin/activate

# Run the app
python approvalreport.py
```

On Windows (target platform), run directly or launch `PatchReport.exe` from `dist\`.

## Building the Windows executable

Must be done **on a Windows machine** — PyInstaller cannot cross-compile.

```bat
build.bat
```

Output: `dist\PatchReport.exe`. The `build\` folder and `.spec` file can be discarded.

## Architecture

The app is split across five files:

| File | Responsibility |
|---|---|
| `approvalreport.py` | Entry point only — `main()`, DB init, CTk theme setup |
| `constants.py` | All constants and UI color palette; no imports |
| `db.py` | All SQLite operations — schema, CRUD, one-time JSON migration |
| `msrc.py` | KB fetching, parsing, classifying (MSRC API + catalog scraping) |
| `report.py` | Email report building (`build_report_email`, `normalize_email_list`) |
| `ui.py` | All UI — `CustomerDialog` and `ApprovalReportApp` |

Dependency flow (no circular imports): `approvalreport` → `ui` / `db` → `msrc` / `report` → `constants`

**`ui.py`** — two classes:
- `CustomerDialog(ctk.CTkToplevel)` — modal add/edit dialog. Uses `after(50, self.grab_set)` (not `grab_set()` directly) to avoid a CTkToplevel timing bug where the window isn't viewable yet.
- `ApprovalReportApp` — owns all layout and wiring. Customer selection state is tracked via `current_customer_idx: int | None` (no Listbox/curselection). The customer sidebar is a `CTkScrollableFrame` populated with one `CTkButton` per customer; `refresh_customer_list()` destroys and recreates all buttons on any change.

**`msrc.py`** — pure functions, no UI dependencies:
- `fetch_current_month_updates()` — orchestrates the full pull: calls MSRC CVRF API first, then enriches via catalog scraping. Tries current month, falls back to previous month automatically.
- `fetch_msrc_month_kbs()` / `extract_kbs_from_cvrf_xml()` — parse the MSRC XML feed to get KB article IDs.
- `search_update_catalog()` — scrapes Microsoft Update Catalog HTML; fragile to markup changes.
- `classify_update()` / `matches_requested_families()` — categorize a KB title into Cumulative Update, Servicing Stack Update, or .NET Framework.

**`report.py`** — pure functions, no UI dependencies:
- `build_report_email()` — builds the HTML email body.
- `normalize_email_list()` — parses and normalizes semicolon/comma-separated addresses.

## Database

`patchreport.db` (SQLite) is created in the working directory on first run via `db.init_db()`. Schema: `customers` table (id, company_name, emails, policy_schedule, last_updated) + `kb_entries` table (customer_id FK with CASCADE, category, kb, title). Each customer dict in memory carries an `"id"` field that maps to the DB primary key. `current_customer_idx` in `ApprovalReportApp` is a list index, not the DB id — the DB id is accessed via `self.customers[idx]["id"]`. If `customers.json` exists on first run it is automatically imported and renamed to `customers.json.migrated`.

## Key constraints

- **ttk.Treeview is intentionally kept** — CustomTkinter has no Treeview equivalent. It is styled via `ttk.Style("clam")` with the custom style name `"Patch.Treeview"`. Do not attempt to replace it with a CTk widget.
- **tk.Menu is intentionally kept** — CTk has no menu widget. The right-click context menu on customer buttons uses standard `tk.Menu`.
- **`customers.json`** is written to the current working directory at runtime. When running as a packaged `.exe`, this means the directory containing the executable.
- **`win32com.client` is a lazy import** inside `draft_outlook_email()` — this is intentional so the app runs on non-Windows platforms for development. PyInstaller needs explicit `--hidden-import` flags for pywin32 as a result (already in `build.bat`).
- All business logic functions treat `requests` and `BeautifulSoup` as optional (guarded at import time) so the app loads even without them installed.

## Color palette

Defined as module-level constants (`_SIDEBAR_FG`, `_CARD_FG`, `_TREE_BG`, etc.) near the top of the file. Modify these to retheme the app rather than hunting through widget definitions.
