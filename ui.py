import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import db
from constants import (
    APP_TITLE,
    _BTN_MUTED,
    _BTN_MUTED_HOV,
    _BTN_MUTED_TXT,
    _CARD_FG,
    _SIDEBAR_FG,
)
from report import build_report_email, normalize_email_list
from ui_customer import CustomerDialog
from ui_patches import PatchPanel, style_treeview
from ui_servers import ServerPanel


class ApprovalReportApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1340x860")
        self.root.minsize(1020, 660)

        self.customers: list[dict] = []
        self.current_customer_idx: int | None = None
        self._customer_buttons: list[ctk.CTkButton] = []

        style_treeview()
        self._build_layout()
        self._load_customers()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_panel()

        self.customer_menu = tk.Menu(self.root, tearoff=0)
        self.customer_menu.add_command(label="Edit Customer",
                                       command=self.edit_selected_customer)

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self.root, width=248, corner_radius=0, fg_color=_SIDEBAR_FG)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(2, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=16, pady=(22, 0))
        ctk.CTkLabel(
            brand,
            text="Patch Reporter",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            brand,
            text="Windows Update Tracker",
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray55"),
            anchor="w",
        ).pack(fill="x")

        ctk.CTkFrame(sidebar, height=1, fg_color=("gray80", "gray25")).grid(
            row=1, column=0, sticky="ew", padx=14, pady=(14, 6)
        )

        self.customer_scroll = ctk.CTkScrollableFrame(
            sidebar,
            label_text="CUSTOMERS",
            label_font=ctk.CTkFont(size=11, weight="bold"),
            label_fg_color="transparent",
            fg_color="transparent",
        )
        self.customer_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))

        ctk.CTkButton(
            sidebar,
            text="＋  Add Customer",
            height=38,
            font=ctk.CTkFont(size=13),
            command=self.add_customer,
        ).grid(row=3, column=0, padx=12, pady=(4, 18), sticky="ew")

    def _build_main_panel(self):
        main = ctk.CTkFrame(self.root, corner_radius=0, fg_color=("gray93", "#191b2a"))
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)  # row 2 = patch panel

        # ── Customer header card ──────────────────────────────────────────
        header_card = ctk.CTkFrame(main, fg_color=_CARD_FG, corner_radius=14)
        header_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 0))
        header_card.grid_columnconfigure(0, weight=1)

        name_row = ctk.CTkFrame(header_card, fg_color="transparent")
        name_row.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 2))
        name_row.grid_columnconfigure(0, weight=1)

        self.company_name_value = ctk.CTkLabel(
            name_row,
            text="No customer selected",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w",
        )
        self.company_name_value.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            name_row,
            text="Edit",
            width=68,
            height=28,
            fg_color=_BTN_MUTED,
            hover_color=_BTN_MUTED_HOV,
            text_color=_BTN_MUTED_TXT,
            font=ctk.CTkFont(size=12),
            command=self.edit_selected_customer,
        ).grid(row=0, column=1, sticky="e", padx=(10, 0))

        self.email_value = ctk.CTkLabel(
            header_card,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray55"),
            anchor="w",
            wraplength=950,
        )
        self.email_value.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))

        # ── Policy card ───────────────────────────────────────────────────
        policy_card = ctk.CTkFrame(main, fg_color=_CARD_FG, corner_radius=14)
        policy_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 0))
        policy_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            policy_card,
            text="Patch Policy / Schedule",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(12, 4))

        self.policy_textbox = ctk.CTkTextbox(
            policy_card,
            height=86,
            font=ctk.CTkFont(size=12),
            state="disabled",
            fg_color=("gray88", "#1a1d2e"),
            border_width=0,
        )
        self.policy_textbox.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))

        # ── Content tabs (Patch Management / Server Status) ───────────────
        content_tabs = ctk.CTkTabview(main, fg_color=("gray93", "#191b2a"), corner_radius=8)
        content_tabs.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 0))
        content_tabs.add("  Patch Management  ")
        content_tabs.add("  Server Status  ")

        patch_tab = content_tabs.tab("  Patch Management  ")
        patch_tab.grid_columnconfigure(0, weight=1)
        patch_tab.grid_rowconfigure(0, weight=1)

        server_tab = content_tabs.tab("  Server Status  ")
        server_tab.grid_columnconfigure(0, weight=1)
        server_tab.grid_rowconfigure(0, weight=1)

        self.patch_panel = PatchPanel(patch_tab, app=self)
        self.patch_panel.grid(row=0, column=0, sticky="nsew")

        self.server_panel = ServerPanel(server_tab, app=self)
        self.server_panel.grid(row=0, column=0, sticky="nsew")

        # ── Footer ────────────────────────────────────────────────────────
        footer = ctk.CTkFrame(main, fg_color="transparent", height=54)
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(8, 18))
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_propagate(False)

        self.status_var = tk.StringVar(value="Ready")
        ctk.CTkLabel(
            footer,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=12),
            text_color=("gray45", "gray55"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            footer,
            text="  Draft Outlook Email  ",
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.draft_outlook_email,
        ).grid(row=0, column=1, sticky="e")

    # ── Customer list ─────────────────────────────────────────────────────────

    def refresh_customer_list(self):
        for btn in self._customer_buttons:
            btn.destroy()
        self._customer_buttons.clear()

        for i, customer in enumerate(self.customers):
            btn = ctk.CTkButton(
                self.customer_scroll,
                text=customer["company_name"],
                anchor="w",
                fg_color="transparent",
                hover_color=("gray82", "#2a2d45"),
                text_color=("gray10", "gray90"),
                font=ctk.CTkFont(size=13),
                height=36,
                corner_radius=8,
                command=lambda idx=i: self._select_customer(idx),
            )
            btn.pack(fill="x", padx=2, pady=2)
            btn.bind("<Button-3>", lambda e, idx=i: self._show_customer_context_menu(e, idx))
            self._customer_buttons.append(btn)

        self._highlight_customer_button(self.current_customer_idx)

    def _select_customer(self, idx: int):
        self.current_customer_idx = idx
        self._highlight_customer_button(idx)
        self._display_customer(idx)

    def _highlight_customer_button(self, idx: int | None):
        for i, btn in enumerate(self._customer_buttons):
            btn.configure(
                fg_color=("gray78", "#1f3a6e") if i == idx else "transparent"
            )

    def _show_customer_context_menu(self, event, idx: int):
        self._select_customer(idx)
        self.customer_menu.tk_popup(event.x_root, event.y_root)

    def _display_customer(self, idx: int):
        customer = self.customers[idx]
        self.company_name_value.configure(text=customer.get("company_name", ""))
        self.email_value.configure(text=customer.get("emails", ""))

        self.policy_textbox.configure(state="normal")
        self.policy_textbox.delete("1.0", "end")
        policies = customer.get("policies", [])
        if policies:
            policy_text = "\n".join(
                p["name"] + (f"  —  {p['schedule']}" if p.get("schedule") else "")
                for p in policies
            )
        else:
            policy_text = ""
        self.policy_textbox.insert("1.0", policy_text)
        self.policy_textbox.configure(state="disabled")

        self.patch_panel.display_customer(customer)
        self.server_panel.display_customer(customer)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_customers(self):
        try:
            self.customers = db.load_customers()
            self.refresh_customer_list()
            if self.customers:
                self._select_customer(0)
        except Exception as exc:
            messagebox.showerror("Load Error", f"Failed to load customers: {exc}")

    # ── Customer CRUD ─────────────────────────────────────────────────────────

    def add_customer(self):
        dlg = CustomerDialog(self.root, "Add Customer")
        if dlg.result_customer:
            new_id = db.save_customer(dlg.result_customer)
            dlg.result_customer["id"] = new_id
            self.customers.append(dlg.result_customer)
            self.refresh_customer_list()
            self._select_customer(len(self.customers) - 1)

    def edit_selected_customer(self):
        if self.current_customer_idx is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
            return
        idx = self.current_customer_idx
        dlg = CustomerDialog(self.root, "Edit Customer", customer=self.customers[idx])
        if dlg.result_customer:
            dlg.result_customer["id"] = self.customers[idx]["id"]
            self.customers[idx] = dlg.result_customer
            db.update_customer(self.customers[idx])
            self.refresh_customer_list()
            self._select_customer(idx)

    # ── Outlook draft ─────────────────────────────────────────────────────────

    def draft_outlook_email(self):
        if self.current_customer_idx is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
            return

        customer = self.customers[self.current_customer_idx]
        updates  = customer.get("updates", {})
        if sum(len(v) for v in updates.values()) == 0:
            if not messagebox.askyesno(
                "No KBs",
                "This customer has no KBs loaded yet. Continue drafting email anyway?",
            ):
                return

        subject, html_body = build_report_email(customer, updates)

        try:
            import win32com.client  # type: ignore  # noqa: F401
        except ImportError:
            messagebox.showerror(
                "Missing Dependency",
                "Outlook drafting requires pywin32 on Windows.\n\n"
                "Install with:  pip install pywin32",
            )
            return

        try:
            import win32com.client as win32
            outlook = win32.Dispatch("Outlook.Application")
            mail    = outlook.CreateItem(0)
            mail.To = normalize_email_list(customer.get("emails", ""))
            mail.Subject  = subject
            mail.HTMLBody = html_body
            mail.Display()
            self.status_var.set("Outlook draft opened.")
        except Exception as exc:
            messagebox.showerror("Outlook Error", f"Failed to open Outlook draft:\n\n{exc}")
