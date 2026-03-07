import tkinter as tk
from email.utils import getaddresses
from tkinter import messagebox

import customtkinter as ctk

from constants import _BTN_MUTED, _BTN_MUTED_HOV, _BTN_MUTED_TXT


class CustomerDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, customer=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("580x560")
        self.resizable(False, False)
        self.after(50, self.grab_set)
        self.focus_set()
        self.lift()

        self.customer = customer or {
            "company_name": "",
            "emails": "",
            "policy_schedule": "",
        }
        self.result_customer = None

        self._build_ui()
        self.wait_window()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text=self.title(),
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=24, pady=(22, 18))

        ctk.CTkLabel(self, text="Company Name", anchor="w",
                     font=ctk.CTkFont(size=13)).pack(fill="x", padx=24, pady=(0, 4))
        self.company_name_var = tk.StringVar(value=self.customer.get("company_name", ""))
        ctk.CTkEntry(
            self,
            textvariable=self.company_name_var,
            placeholder_text="Acme Corp",
            height=36,
        ).pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkLabel(
            self,
            text="Customer Email Addresses  (comma or semicolon separated)",
            anchor="w",
            font=ctk.CTkFont(size=13),
        ).pack(fill="x", padx=24, pady=(0, 4))
        self.emails_text = ctk.CTkTextbox(self, height=76, font=ctk.CTkFont(size=12))
        self.emails_text.pack(fill="x", padx=24, pady=(0, 16))
        self.emails_text.insert("1.0", self.customer.get("emails", ""))

        ctk.CTkLabel(
            self,
            text="Patch Policies + Schedule Dates",
            anchor="w",
            font=ctk.CTkFont(size=13),
        ).pack(fill="x", padx=24, pady=(0, 4))
        self.policy_text = ctk.CTkTextbox(self, height=156, font=ctk.CTkFont(size=12))
        self.policy_text.pack(fill="x", padx=24, pady=(0, 22))
        self.policy_text.insert("1.0", self.customer.get("policy_schedule", ""))

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

        self.result_customer = {
            "company_name": company_name,
            "emails": emails,
            "policy_schedule": self.policy_text.get("1.0", "end").strip(),
            "updates": self.customer.get("updates", {}),
            "last_updated": self.customer.get("last_updated", ""),
        }
        self.destroy()
