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

| File | Responsibility |
|---|---|
| `approvalreport.py` | Entry point only — `main()`, DB init, CTk theme setup |
| `constants.py` | All constants and UI color palette; no imports |
| `db.py` | All SQLite operations — schema, CRUD, migrations |
| `msrc.py` | KB fetching, parsing, classifying (MSRC API + catalog scraping) |
| `report.py` | Outlook email report building |
| `reports_pdf.py` | Pre/post patch PDF report building (reportlab) |
| `ui.py` | `ApprovalReportApp` — main window, sidebar, layout shell |
| `ui_customer.py` | `CustomerDialog` — modal add/edit customer dialog |
| `ui_patches.py` | `PatchPanel` — patch pull, KB treeview, product filters |
| `ui_servers.py` | `ServerPanel` — server inventory, patch sessions, PDF generation |

Dependency flow (no circular imports):
`approvalreport` → `ui` → `ui_patches` / `ui_servers` / `ui_customer` → `db` / `msrc` / `report` / `reports_pdf` → `constants`

**`ui.py`** — `ApprovalReportApp` owns the top-level layout and wiring. Customer selection state is tracked via `current_customer_idx: int | None`. The sidebar is a `CTkScrollableFrame` with one `CTkButton` per customer; `refresh_customer_list()` destroys and recreates all buttons on any change. The main area uses a `CTkTabview` with "Patch Management" and "Server Status" tabs hosting `PatchPanel` and `ServerPanel` respectively.

**`ui_customer.py`** — `CustomerDialog(ctk.CTkToplevel)` — modal add/edit dialog. Uses `after(50, self.grab_set)` to avoid a CTkToplevel timing bug. Patch policies are stored as a list of `{name, schedule}` dicts.

**`ui_patches.py`** — `PatchPanel` — handles KB pull, treeview display, and per-customer product/arch filters. Filters are saved to the DB automatically on change and applied both to pull queries and treeview display.

**`ui_servers.py`** — `ServerPanel` — CSV server import, monthly patch sessions, per-server KB auto-fill via `find_patch_for_server()`, bulk status apply, and pre/post PDF generation. `_PatchOverrideDialog` handles manual KB override for selected servers.

**`msrc.py`** — pure functions, no UI dependencies:
- `fetch_current_month_updates(filters)` — product-targeted catalog queries. Tries current month, falls back to previous month automatically.
- `search_update_catalog()` — scrapes Microsoft Update Catalog HTML; fragile to markup changes.
- `classify_update()` / `matches_product_filter()` — categorize and filter KB titles.
- `find_patch_for_server(os_version, updates)` — matches a server's OS string to the correct CU from pulled data.

**`report.py`** — pure functions, no UI dependencies:
- `build_report_email()` — builds the HTML email body.
- `normalize_email_list()` — parses and normalizes semicolon/comma-separated addresses.

## Database

`patchreport.db` (SQLite) created on first run via `db.init_db()`. Tables: `customers`, `kb_entries`, `servers`, `patch_sessions`, `server_patch_status`. Additive column migrations are wrapped in try/except so existing DBs upgrade silently. Each customer dict in memory carries an `"id"` field mapping to the DB primary key. `current_customer_idx` in `ApprovalReportApp` is a list index, not the DB id. If `customers.json` exists on first run it is automatically imported and renamed to `customers.json.migrated`.

## Key constraints

- **ttk.Treeview is intentionally kept** — CustomTkinter has no Treeview equivalent. It is styled via `ttk.Style("clam")` with the custom style name `"Patch.Treeview"`. Do not attempt to replace it with a CTk widget.
- **tk.Menu is intentionally kept** — CTk has no menu widget. The right-click context menu on customer buttons uses standard `tk.Menu`.
- **`customers.json`** is written to the current working directory at runtime. When running as a packaged `.exe`, this means the directory containing the executable.
- **`win32com.client` is a lazy import** inside `draft_outlook_email()` — this is intentional so the app runs on non-Windows platforms for development. PyInstaller needs explicit `--hidden-import` flags for pywin32 as a result (already in `build.bat`).
- All business logic functions treat `requests` and `BeautifulSoup` as optional (guarded at import time) so the app loads even without them installed.

## Color palette

Defined as module-level constants (`_SIDEBAR_FG`, `_CARD_FG`, `_TREE_BG`, etc.) near the top of the file. Modify these to retheme the app rather than hunting through widget definitions.
