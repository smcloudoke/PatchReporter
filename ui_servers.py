import csv
import tkinter as tk
from collections import Counter
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import db
from constants import (
    ALL_CATEGORIES,
    PATCH_STATUSES,
    STATUS_ROW_BG,
    STATUS_ROW_FG,
    STATUS_TAG,
    _BTN_MUTED,
    _BTN_MUTED_HOV,
    _BTN_MUTED_TXT,
    _CARD_FG,
    _TREE_BG,
)
from msrc import find_patch_for_server
from reports_pdf import REPORTLAB_AVAILABLE, build_post_patch_pdf, build_pre_patch_pdf


class ServerPanel(ctk.CTkFrame):
    """
    Per-customer server inventory + monthly patch status tracking.
    Supports CSV import, auto-matched KB assignment (overridable),
    multi-select bulk status apply, and pre/post PDF reports.
    """

    def __init__(self, parent, app):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app

        self._customer:     dict | None      = None
        self._servers:      list[dict]       = []
        self._session_id:   int | None       = None
        self._session_data: dict[int, dict]  = {}   # {server_id: {status, patch_kb, patch_name}}
        self._current_month = datetime.now().replace(day=1)
        self._policy_var    = tk.StringVar(value="")
        self._loading_policy = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_controls()
        self._build_tree_area()
        self._build_bottom_bar()

    # ── Controls ──────────────────────────────────────────────────────────────

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
            font=ctk.CTkFont(size=13), command=self._prev_month,
        ).pack(side="left", padx=(0, 6))

        self._month_label = ctk.CTkLabel(
            nav, text=self._month_str(),
            font=ctk.CTkFont(size=14, weight="bold"), width=140, anchor="center",
        )
        self._month_label.pack(side="left")

        ctk.CTkButton(
            nav, text="▶", width=32, height=30,
            fg_color=_BTN_MUTED, hover_color=_BTN_MUTED_HOV, text_color=_BTN_MUTED_TXT,
            font=ctk.CTkFont(size=13), command=self._next_month,
        ).pack(side="left", padx=(6, 0))

        # Policy selector
        policy_row = ctk.CTkFrame(card, fg_color="transparent")
        policy_row.grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 12))

        ctk.CTkLabel(policy_row, text="Policy:",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))

        self._policy_menu = ctk.CTkOptionMenu(
            policy_row, values=["—"], variable=self._policy_var,
            width=200, height=30, font=ctk.CTkFont(size=12),
            command=self._on_policy_change,
        )
        self._policy_menu.pack(side="left")

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

        ctk.CTkButton(
            actions, text="Override Patch", height=32,
            fg_color=_BTN_MUTED, hover_color=_BTN_MUTED_HOV, text_color=_BTN_MUTED_TXT,
            command=self._override_patch,
        ).pack(side="left", padx=(0, 18))

        self._apply_status_var = tk.StringVar(value=PATCH_STATUSES[1])
        ctk.CTkOptionMenu(
            actions, values=PATCH_STATUSES, variable=self._apply_status_var,
            width=180, height=32, font=ctk.CTkFont(size=12),
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
            columns=("hostname", "os_version", "kb", "patch_name", "status"),
            show="headings",
            style="Patch.Treeview",
            selectmode="extended",
        )
        self._server_tree.heading("hostname",   text="Hostname")
        self._server_tree.heading("os_version", text="OS Version")
        self._server_tree.heading("kb",         text="KB")
        self._server_tree.heading("patch_name", text="Patch Name")
        self._server_tree.heading("status",     text="Status")
        self._server_tree.column("hostname",   width=200, stretch=True)
        self._server_tree.column("os_version", width=180, stretch=True)
        self._server_tree.column("kb",         width=90,  stretch=False)
        self._server_tree.column("patch_name", width=340, stretch=True)
        self._server_tree.column("status",     width=160, stretch=False)

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

    # ── Bottom bar ────────────────────────────────────────────────────────────

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
        self._current_month = datetime.now().replace(day=1)
        self._reload()

    def _reload(self):
        if self._customer is None:
            return

        customer_id = self._customer["id"]
        self._month_label.configure(text=self._month_str())
        self._servers = db.get_servers(customer_id)

        self._loading_policy = True
        policies = [p["name"] for p in self._customer.get("policies", []) if p.get("name")]
        policy_values = policies if policies else ["—"]
        self._policy_menu.configure(values=policy_values)

        if self._servers:
            self._session_id  = db.get_or_create_session(customer_id, self._month_key())
            self._session_data = db.get_session_data(self._session_id)
            saved_policy = db.get_session_policy(self._session_id)
            self._policy_var.set(
                saved_policy if saved_policy in policy_values else policy_values[0]
            )
            self._auto_fill_patches()
        else:
            self._session_id   = None
            self._session_data = {}
            self._policy_var.set(policy_values[0])
        self._loading_policy = False

        self._populate_tree()
        self._update_summary()

    def _auto_fill_patches(self):
        """Auto-assign patches to servers that don't have one yet."""
        if self._session_id is None:
            return
        updates = self._customer.get("updates", {})
        if not any(updates.get(cat) for cat in ALL_CATEGORIES):
            return  # No patches pulled yet — nothing to auto-fill

        needs_fill = [
            srv for srv in self._servers
            if not self._session_data.get(srv["id"], {}).get("patch_kb")
        ]
        if not needs_fill:
            return

        for srv in needs_fill:
            kb, name = find_patch_for_server(srv["os_version"], updates)
            if kb:
                db.set_server_patches(self._session_id, [srv["id"]], kb, name)

        self._session_data = db.get_session_data(self._session_id)

    def _populate_tree(self):
        for item in self._server_tree.get_children():
            self._server_tree.delete(item)

        for srv in self._servers:
            data       = self._session_data.get(srv["id"], {})
            status     = data.get("status", "Pending")
            patch_kb   = data.get("patch_kb", "")
            patch_name = data.get("patch_name", "")
            tag        = STATUS_TAG.get(status, "status_pending")
            self._server_tree.insert(
                "", "end",
                iid=str(srv["id"]),
                values=(srv["hostname"], srv["os_version"], patch_kb, patch_name, status),
                tags=(tag,),
            )

    def _update_summary(self):
        if not self._servers:
            self._summary_label.configure(text="No servers imported.")
            return
        counts = Counter(d.get("status", "Pending") for d in self._session_data.values())
        self._summary_label.configure(
            text=(
                f"✓ {counts.get('Installed', 0)}  "
                f"✗ {counts.get('Failed', 0)}  "
                f"↺ {counts.get('Reboot Required', 0)}  "
                f"⏳ {counts.get('Pending', 0)}"
            )
        )

    def _on_policy_change(self, value: str):
        if self._loading_policy or self._session_id is None:
            return
        if value != "—":
            db.set_session_policy(self._session_id, value)

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

    # ── Patch override ────────────────────────────────────────────────────────

    def _override_patch(self):
        if self._session_id is None:
            messagebox.showinfo("No Servers", "Import servers first.")
            return
        selected = self._server_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select one or more servers first.")
            return

        updates = self._customer.get("updates", {})
        # Build list of all available patches from loaded KBs
        choices = []
        for cat in ALL_CATEGORIES:
            for entry in updates.get(cat, []):
                label = f"{entry['kb']}  —  {entry['title']}"
                choices.append((entry["kb"], entry["title"], label))

        if not choices:
            messagebox.showwarning(
                "No Patches Loaded",
                "Pull patches in the Patch Management tab first.",
            )
            return

        _PatchOverrideDialog(
            self,
            choices=choices,
            server_count=len(selected),
            on_apply=lambda kb, name: self._apply_patch_override(
                [int(iid) for iid in selected], kb, name
            ),
        )

    def _apply_patch_override(self, server_ids: list[int], kb: str, name: str):
        db.set_server_patches(self._session_id, server_ids, kb, name)
        self._session_data = db.get_session_data(self._session_id)
        self._populate_tree()

    # ── Status application ────────────────────────────────────────────────────

    def _apply_status(self):
        if self._session_id is None:
            messagebox.showinfo("No Servers", "Import servers first.")
            return
        selected = self._server_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select one or more servers first.")
            return
        db.set_server_statuses(self._session_id, [int(iid) for iid in selected],
                               self._apply_status_var.get())
        self._session_data = db.get_session_data(self._session_id)
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
            build_pre_patch_pdf(
                filepath, self._customer, self._month_str(),
                self._customer.get("updates", {}), self._servers,
                policy=self._policy_var.get(),
            )
            self.app.status_var.set("Pre-patch report saved.")
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
                    "patch_kb":   self._session_data.get(srv["id"], {}).get("patch_kb", ""),
                    "patch_name": self._session_data.get(srv["id"], {}).get("patch_name", ""),
                    "status":     self._session_data.get(srv["id"], {}).get("status", "Pending"),
                }
                for srv in self._servers
            ]
            build_post_patch_pdf(filepath, self._customer, self._month_str(), server_statuses,
                                 policy=self._policy_var.get())
            self.app.status_var.set("Post-patch report saved.")
        except Exception as exc:
            messagebox.showerror("PDF Error", f"Failed to generate report:\n{exc}")


# ── Patch override dialog ──────────────────────────────────────────────────────

class _PatchOverrideDialog(ctk.CTkToplevel):
    def __init__(self, parent, choices: list[tuple], server_count: int, on_apply):
        super().__init__(parent)
        self.title("Override Patch")
        self.geometry("680x220")
        self.resizable(False, False)
        self.after(50, self.grab_set)
        self.lift()

        self._choices  = choices   # [(kb, title, label), ...]
        self._on_apply = on_apply
        self._var      = tk.StringVar(value=choices[0][2])

        ctk.CTkLabel(
            self,
            text=f"Select patch to assign to {server_count} server(s):",
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).pack(fill="x", padx=24, pady=(22, 10))

        ctk.CTkOptionMenu(
            self,
            values=[c[2] for c in choices],
            variable=self._var,
            font=ctk.CTkFont(size=12),
            width=630,
            height=34,
        ).pack(padx=24, pady=(0, 20))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=90, height=36,
            fg_color=_BTN_MUTED, hover_color=_BTN_MUTED_HOV, text_color=_BTN_MUTED_TXT,
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btn_frame, text="Apply", width=90, height=36,
            command=self._apply,
        ).pack(side="right")

    def _apply(self):
        label = self._var.get()
        for kb, name, lbl in self._choices:
            if lbl == label:
                self._on_apply(kb, name)
                break
        self.destroy()
