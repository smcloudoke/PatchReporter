import csv
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import db
from constants import (
    PATCH_STATUSES,
    STATUS_ROW_BG,
    STATUS_ROW_FG,
    STATUS_TAG,
    _BTN_MUTED,
    _BTN_MUTED_HOV,
    _BTN_MUTED_TXT,
    _CARD_FG,
    _TREE_BG,
    _TREE_HEAD_BG,
    _TREE_SEL_BG,
)
from reports_pdf import REPORTLAB_AVAILABLE, build_post_patch_pdf, build_pre_patch_pdf


class ServerPanel(ctk.CTkFrame):
    """
    Per-customer server inventory + monthly patch status tracking.
    Supports CSV import, multi-select bulk status apply, and pre/post PDF reports.
    """

    def __init__(self, parent, app):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app

        self._customer: dict | None = None
        self._servers:  list[dict]  = []
        self._session_id: int | None = None
        self._statuses:  dict[int, str] = {}
        self._current_month = datetime.now().replace(day=1)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_controls()
        self._build_tree_area()
        self._build_bottom_bar()

    # ── Controls (month nav + action buttons) ─────────────────────────────────

    def _build_controls(self):
        card = ctk.CTkFrame(self, fg_color=_CARD_FG, corner_radius=14)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        # Month navigation
        nav = ctk.CTkFrame(card, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="w", padx=18, pady=12)

        ctk.CTkButton(
            nav, text="◀", width=32, height=30,
            fg_color=_BTN_MUTED, hover_color=_BTN_MUTED_HOV, text_color=_BTN_MUTED_TXT,
            font=ctk.CTkFont(size=13),
            command=self._prev_month,
        ).pack(side="left", padx=(0, 6))

        self._month_label = ctk.CTkLabel(
            nav, text=self._month_str(),
            font=ctk.CTkFont(size=14, weight="bold"), width=140, anchor="center",
        )
        self._month_label.pack(side="left")

        ctk.CTkButton(
            nav, text="▶", width=32, height=30,
            fg_color=_BTN_MUTED, hover_color=_BTN_MUTED_HOV, text_color=_BTN_MUTED_TXT,
            font=ctk.CTkFont(size=13),
            command=self._next_month,
        ).pack(side="left", padx=(6, 0))

        # Action buttons
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=18, pady=12)

        ctk.CTkButton(
            actions, text="Import CSV", height=32,
            command=self._import_csv,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions, text="Remove Selected", height=32,
            fg_color=_BTN_MUTED, hover_color=_BTN_MUTED_HOV, text_color=_BTN_MUTED_TXT,
            command=self._remove_selected_servers,
        ).pack(side="left", padx=(0, 18))

        # Status apply
        self._apply_status_var = tk.StringVar(value=PATCH_STATUSES[1])
        ctk.CTkOptionMenu(
            actions,
            values=PATCH_STATUSES,
            variable=self._apply_status_var,
            width=180,
            height=32,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions, text="Apply to Selected", height=32,
            command=self._apply_status,
        ).pack(side="left")

    # ── Server treeview ───────────────────────────────────────────────────────

    def _build_tree_area(self):
        frame = tk.Frame(self, background=_TREE_BG)
        frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self._server_tree = ttk.Treeview(
            frame,
            columns=("hostname", "os_version", "status"),
            show="headings",
            style="Patch.Treeview",
            selectmode="extended",
        )
        self._server_tree.heading("hostname",   text="Hostname")
        self._server_tree.heading("os_version", text="OS Version")
        self._server_tree.heading("status",     text="Status")
        self._server_tree.column("hostname",   width=280, stretch=True)
        self._server_tree.column("os_version", width=280, stretch=True)
        self._server_tree.column("status",     width=200, stretch=False)

        for status, tag in STATUS_TAG.items():
            self._server_tree.tag_configure(
                tag,
                foreground=STATUS_ROW_FG[status],
                background=STATUS_ROW_BG[status],
            )

        yscroll = ttk.Scrollbar(frame, orient="vertical",
                                command=self._server_tree.yview)
        self._server_tree.configure(yscrollcommand=yscroll.set)
        self._server_tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

    # ── Bottom bar (summary + PDF buttons) ────────────────────────────────────

    def _build_bottom_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent", height=48)
        bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_propagate(False)

        self._summary_label = ctk.CTkLabel(
            bar, text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray55"),
            anchor="w",
        )
        self._summary_label.grid(row=0, column=0, sticky="w")

        pdf_frame = ctk.CTkFrame(bar, fg_color="transparent")
        pdf_frame.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(
            pdf_frame, text="Pre-Patch PDF", height=36,
            fg_color=_BTN_MUTED, hover_color=_BTN_MUTED_HOV, text_color=_BTN_MUTED_TXT,
            command=self._generate_pre_patch_pdf,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            pdf_frame, text="Post-Patch PDF", height=36,
            command=self._generate_post_patch_pdf,
        ).pack(side="left")

    # ── Customer display ──────────────────────────────────────────────────────

    def display_customer(self, customer: dict):
        self._customer = customer
        self._reload()

    def _reload(self):
        if self._customer is None:
            return

        customer_id = self._customer["id"]
        self._month_label.configure(text=self._month_str())
        self._servers = db.get_servers(customer_id)

        if self._servers:
            self._session_id = db.get_or_create_session(customer_id, self._month_key())
            self._statuses   = db.get_session_statuses(self._session_id)
        else:
            self._session_id = None
            self._statuses   = {}

        self._populate_tree()
        self._update_summary()

    def _populate_tree(self):
        for item in self._server_tree.get_children():
            self._server_tree.delete(item)

        for srv in self._servers:
            status = self._statuses.get(srv["id"], "Pending")
            tag    = STATUS_TAG.get(status, "status_pending")
            self._server_tree.insert(
                "", "end",
                iid=str(srv["id"]),
                values=(srv["hostname"], srv["os_version"], status),
                tags=(tag,),
            )

    def _update_summary(self):
        if not self._servers:
            self._summary_label.configure(text="No servers imported.")
            return
        from collections import Counter
        counts = Counter(self._statuses.values())
        self._summary_label.configure(
            text=(
                f"✓ {counts.get('Patch Successful', 0)}  "
                f"✗ {counts.get('Patch Failed', 0)}  "
                f"↺ {counts.get('Reboot Required', 0)}  "
                f"⏳ {counts.get('Pending', 0)}"
            )
        )

    # ── Month navigation ──────────────────────────────────────────────────────

    def _prev_month(self):
        m = self._current_month
        self._current_month = m.replace(
            year=m.year if m.month > 1 else m.year - 1,
            month=m.month - 1 if m.month > 1 else 12,
        )
        self._reload()

    def _next_month(self):
        m = self._current_month
        self._current_month = m.replace(
            year=m.year if m.month < 12 else m.year + 1,
            month=m.month + 1 if m.month < 12 else 1,
        )
        self._reload()

    def _month_str(self) -> str:
        return self._current_month.strftime("%B %Y")

    def _month_key(self) -> str:
        return self._current_month.strftime("%Y-%m")

    # ── CSV import ────────────────────────────────────────────────────────────

    def _import_csv(self):
        if self._customer is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
            return

        filepath = filedialog.askopenfilename(
            title="Import Server List",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not filepath:
            return

        servers = []
        try:
            with open(filepath, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    hostname   = row.get("hostname",   "").strip()
                    os_version = row.get("os_version", "").strip()
                    if hostname and os_version:
                        servers.append({"hostname": hostname, "os_version": os_version})
        except Exception as exc:
            messagebox.showerror("CSV Error", f"Failed to read file:\n{exc}")
            return

        if not servers:
            messagebox.showwarning(
                "Empty CSV",
                "No valid rows found.\nExpected columns: hostname, os_version",
            )
            return

        existing = db.get_servers(self._customer["id"])
        if existing:
            if not messagebox.askyesno(
                "Replace Servers",
                f"This will replace {len(existing)} existing server(s) "
                f"with {len(servers)} from the CSV.\n\nContinue?",
            ):
                return

        count = db.import_servers(self._customer["id"], servers)
        self._reload()
        self.app.status_var.set(f"Imported {count} server(s).")

    # ── Server removal ────────────────────────────────────────────────────────

    def _remove_selected_servers(self):
        selected = self._server_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select one or more servers to remove.")
            return
        if not messagebox.askyesno(
            "Remove Servers",
            f"Remove {len(selected)} selected server(s)? This cannot be undone.",
        ):
            return
        db.delete_servers([int(iid) for iid in selected])
        self._reload()
        self.app.status_var.set(f"Removed {len(selected)} server(s).")

    # ── Status application ────────────────────────────────────────────────────

    def _apply_status(self):
        if self._session_id is None:
            messagebox.showinfo("No Servers", "Import servers first.")
            return
        selected = self._server_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select one or more servers first.")
            return
        status = self._apply_status_var.get()
        db.set_server_statuses(self._session_id, [int(iid) for iid in selected], status)
        self._statuses = db.get_session_statuses(self._session_id)
        self._populate_tree()
        self._update_summary()

    # ── PDF reports ───────────────────────────────────────────────────────────

    def _check_pdf_ready(self) -> bool:
        if self._customer is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
            return False
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "Missing Dependency",
                "PDF generation requires reportlab.\n\nInstall with:  pip install reportlab",
            )
            return False
        return True

    def _generate_pre_patch_pdf(self):
        if not self._check_pdf_ready():
            return

        filepath = filedialog.asksaveasfilename(
            title="Save Pre-Patch Report",
            defaultextension=".pdf",
            initialfile=f"Pre-Patch_{self._customer['company_name']}_{self._month_key()}.pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not filepath:
            return

        try:
            updates = self._customer.get("updates", {})
            build_pre_patch_pdf(filepath, self._customer, self._month_str(),
                                updates, self._servers)
            self.app.status_var.set(f"Pre-patch report saved.")
        except Exception as exc:
            messagebox.showerror("PDF Error", f"Failed to generate report:\n{exc}")

    def _generate_post_patch_pdf(self):
        if not self._check_pdf_ready():
            return

        filepath = filedialog.asksaveasfilename(
            title="Save Post-Patch Report",
            defaultextension=".pdf",
            initialfile=f"Post-Patch_{self._customer['company_name']}_{self._month_key()}.pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not filepath:
            return

        try:
            server_statuses = [
                {
                    "hostname":   srv["hostname"],
                    "os_version": srv["os_version"],
                    "status":     self._statuses.get(srv["id"], "Pending"),
                }
                for srv in self._servers
            ]
            build_post_patch_pdf(filepath, self._customer, self._month_str(), server_statuses)
            self.app.status_var.set(f"Post-patch report saved.")
        except Exception as exc:
            messagebox.showerror("PDF Error", f"Failed to generate report:\n{exc}")
