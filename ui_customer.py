import tkinter as tk
from email.utils import getaddresses
from tkinter import messagebox

import customtkinter as ctk

from constants import _BTN_MUTED, _BTN_MUTED_HOV, _BTN_MUTED_TXT


class CustomerDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, customer=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("620x680")
        self.resizable(False, False)
        self.after(50, self.grab_set)
        self.focus_set()
        self.lift()

        self.customer = customer or {"company_name": "", "emails": "", "policies": []}
        self.result_customer = None
        self._policy_rows: list[dict] = []  # each: {"name": StringVar, "schedule": StringVar}

        self._build_ui()
        self.wait_window()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text=self.title(),
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=24, pady=(22, 18))

        # ── Company Name ──────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Company Name", anchor="w",
                     font=ctk.CTkFont(size=13)).pack(fill="x", padx=24, pady=(0, 4))
        self.company_name_var = tk.StringVar(value=self.customer.get("company_name", ""))
        ctk.CTkEntry(
            self,
            textvariable=self.company_name_var,
            placeholder_text="Acme Corp",
            height=36,
        ).pack(fill="x", padx=24, pady=(0, 16))

        # ── Email Addresses ───────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Customer Email Addresses  (comma or semicolon separated)",
            anchor="w",
            font=ctk.CTkFont(size=13),
        ).pack(fill="x", padx=24, pady=(0, 4))
        self.emails_text = ctk.CTkTextbox(self, height=76, font=ctk.CTkFont(size=12))
        self.emails_text.pack(fill="x", padx=24, pady=(0, 16))
        self.emails_text.insert("1.0", self.customer.get("emails", ""))

        # ── Patch Policies ────────────────────────────────────────────────────
        policy_header = ctk.CTkFrame(self, fg_color="transparent")
        policy_header.pack(fill="x", padx=24, pady=(0, 6))
        policy_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            policy_header,
            text="Patch Policies",
            anchor="w",
            font=ctk.CTkFont(size=13),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            policy_header,
            text="＋ Add Policy",
            height=28,
            width=110,
            font=ctk.CTkFont(size=12),
            command=self._add_policy_row,
        ).grid(row=0, column=1, sticky="e")

        # Column labels
        col_labels = ctk.CTkFrame(self, fg_color="transparent")
        col_labels.pack(fill="x", padx=24, pady=(0, 2))
        ctk.CTkLabel(col_labels, text="Policy Name", anchor="w",
                     font=ctk.CTkFont(size=11), text_color=("gray50", "gray60"),
                     width=180).pack(side="left")
        ctk.CTkLabel(col_labels, text="Schedule / Notes", anchor="w",
                     font=ctk.CTkFont(size=11), text_color=("gray50", "gray60")).pack(side="left", padx=(8, 0))

        # Scrollable policy list
        self._policy_frame = ctk.CTkScrollableFrame(self, height=180, fg_color=("gray90", "#1e2133"))
        self._policy_frame.pack(fill="x", padx=24, pady=(0, 20))
        self._policy_frame.grid_columnconfigure(0, weight=1)
        self._policy_frame.grid_columnconfigure(1, weight=1)

        # Populate with existing policies
        for policy in self.customer.get("policies", []):
            self._add_policy_row(policy.get("name", ""), policy.get("schedule", ""))

        # ── Save / Cancel ─────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 24))
        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            fg_color=_BTN_MUTED,
            hover_color=_BTN_MUTED_HOV,
            text_color=_BTN_MUTED_TXT,
            width=90,
            height=36,
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_frame, text="Save", width=90, height=36,
                      command=self._on_save).pack(side="right")

    def _add_policy_row(self, name: str = "", schedule: str = ""):
        row_idx = len(self._policy_rows)

        row_frame = ctk.CTkFrame(self._policy_frame, fg_color="transparent")
        row_frame.grid(row=row_idx, column=0, columnspan=3, sticky="ew", pady=3)
        row_frame.grid_columnconfigure(0, weight=2)
        row_frame.grid_columnconfigure(1, weight=3)

        name_var     = tk.StringVar(value=name)
        schedule_var = tk.StringVar(value=schedule)

        ctk.CTkEntry(
            row_frame,
            textvariable=name_var,
            placeholder_text="e.g. Pilot",
            height=32,
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkEntry(
            row_frame,
            textvariable=schedule_var,
            placeholder_text="e.g. 2nd Tuesday of month",
            height=32,
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=1, sticky="ew", padx=(0, 6))

        row_data = {"name": name_var, "schedule": schedule_var, "frame": row_frame}

        ctk.CTkButton(
            row_frame,
            text="✕",
            width=32,
            height=32,
            fg_color=_BTN_MUTED,
            hover_color=_BTN_MUTED_HOV,
            text_color=_BTN_MUTED_TXT,
            font=ctk.CTkFont(size=12),
            command=lambda r=row_data: self._remove_policy_row(r),
        ).grid(row=0, column=2)

        self._policy_rows.append(row_data)

    def _remove_policy_row(self, row_data: dict):
        row_data["frame"].destroy()
        self._policy_rows.remove(row_data)

    def _on_save(self):
        company_name = self.company_name_var.get().strip()
        if not company_name:
            messagebox.showerror("Validation", "Company Name is required.", parent=self)
            return

        emails = self.emails_text.get("1.0", "end").strip()
        if emails:
            parsed = [addr for _, addr in getaddresses([emails]) if addr]
            if not parsed:
                messagebox.showerror(
                    "Validation",
                    "Please enter at least one valid email address or leave blank.",
                    parent=self,
                )
                return

        policies = [
            {"name": r["name"].get().strip(), "schedule": r["schedule"].get().strip()}
            for r in self._policy_rows
            if r["name"].get().strip()
        ]

        self.result_customer = {
            "company_name": company_name,
            "emails":       emails,
            "policies":     policies,
            "updates":      self.customer.get("updates", {}),
            "last_updated": self.customer.get("last_updated", ""),
        }
        self.destroy()
