import re
import tkinter as tk
from datetime import datetime
from email.utils import getaddresses
from tkinter import messagebox, ttk

import customtkinter as ctk

import db

from constants import (
    ALL_CATEGORIES,
    APP_TITLE,
    ARCHITECTURES,
    CUSTOMERS_FILE,
    DEFAULT_FILTERS,
    PRODUCT_FAMILIES,
    _BTN_MUTED,
    _BTN_MUTED_HOV,
    _BTN_MUTED_TXT,
    _CARD_FG,
    _SIDEBAR_FG,
    _TREE_ALT_BG,
    _TREE_BG,
    _TREE_HEAD_BG,
    _TREE_SEL_BG,
)
from msrc import classify_update, fetch_current_month_updates, matches_product_filter
from report import build_report_email, normalize_email_list


# ─── Customer dialog ──────────────────────────────────────────────────────────

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


# ─── Main application ─────────────────────────────────────────────────────────

class ApprovalReportApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1340x860")
        self.root.minsize(1020, 660)

        self.customers: list[dict] = []
        self.current_customer_idx: int | None = None
        self.current_updates: dict = {cat: [] for cat in ALL_CATEGORIES}
        self._customer_buttons: list[ctk.CTkButton] = []
        self._filter_product_vars: dict[str, tk.BooleanVar] = {}
        self._filter_arch_var = tk.StringVar(value=DEFAULT_FILTERS["architecture"])

        self._style_treeview()
        self._build_layout()
        self._load_customers()

    # ── Treeview dark styling ─────────────────────────────────────────────────

    def _style_treeview(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Patch.Treeview",
            background=_TREE_BG,
            foreground="#d8dce8",
            fieldbackground=_TREE_BG,
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Patch.Treeview.Heading",
            background=_TREE_HEAD_BG,
            foreground="white",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 6),
        )
        style.map(
            "Patch.Treeview",
            background=[("selected", _TREE_SEL_BG)],
            foreground=[("selected", "white")],
        )
        style.map("Patch.Treeview.Heading",
                  background=[("active", "#2980b9")])
        style.configure(
            "Vertical.TScrollbar",
            background="#3a3d52",
            troughcolor=_TREE_BG,
            arrowcolor="#d8dce8",
            borderwidth=0,
        )

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
        sidebar = ctk.CTkFrame(
            self.root, width=248, corner_radius=0, fg_color=_SIDEBAR_FG
        )
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
        main.grid_rowconfigure(3, weight=1)  # row 3 = tabs (filter card is row 2)

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

        # ── Filter card ───────────────────────────────────────────────────
        self._build_filter_card(main)

        # ── Tabs ──────────────────────────────────────────────────────────
        self.tabview = ctk.CTkTabview(main, height=320, fg_color=_CARD_FG)
        self.tabview.grid(row=3, column=0, sticky="nsew", padx=20, pady=(10, 0))

        self.tabview.add("  Automated Pull  ")
        self.tabview.add("  Manual KB Input  ")

        auto_tab = self.tabview.tab("  Automated Pull  ")
        auto_tab.grid_columnconfigure(0, weight=1)
        auto_tab.grid_rowconfigure(1, weight=1)

        manual_tab = self.tabview.tab("  Manual KB Input  ")
        manual_tab.grid_columnconfigure(1, weight=1)
        manual_tab.grid_rowconfigure(2, weight=1)

        self._build_auto_tab(auto_tab)
        self._build_manual_tab(manual_tab)

        # ── Footer ────────────────────────────────────────────────────────
        footer = ctk.CTkFrame(main, fg_color="transparent", height=54)
        footer.grid(row=4, column=0, sticky="ew", padx=20, pady=(8, 18))
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

    def _build_filter_card(self, parent: ctk.CTkFrame):
        card = ctk.CTkFrame(parent, fg_color=_CARD_FG, corner_radius=14)
        card.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 0))
        card.grid_columnconfigure(0, weight=1)

        # Header row
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Product Scope",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="affects pull queries and table display",
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray55"),
            anchor="e",
        ).grid(row=0, column=1, sticky="e")

        # Product checkboxes — 3 per row
        cb_frame = ctk.CTkFrame(card, fg_color="transparent")
        cb_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 6))
        for col in range(3):
            cb_frame.grid_columnconfigure(col, weight=1)

        for i, product in enumerate(PRODUCT_FAMILIES):
            var = tk.BooleanVar(value=False)
            self._filter_product_vars[product] = var
            ctk.CTkCheckBox(
                cb_frame,
                text=product,
                variable=var,
                font=ctk.CTkFont(size=12),
                command=self._on_filter_change,
            ).grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 12), pady=3)

        # Architecture row
        arch_row = ctk.CTkFrame(card, fg_color="transparent")
        arch_row.grid(row=2, column=0, sticky="w", padx=18, pady=(2, 12))

        ctk.CTkLabel(
            arch_row,
            text="Architecture:",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkOptionMenu(
            arch_row,
            values=ARCHITECTURES,
            variable=self._filter_arch_var,
            width=100,
            font=ctk.CTkFont(size=12),
            command=self._on_filter_change,
        ).pack(side="left")

    # ── Tab builders ──────────────────────────────────────────────────────────

    def _build_auto_tab(self, tab: ctk.CTkFrame):
        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="w", pady=(6, 8))

        ctk.CTkButton(
            btn_row,
            text="Pull Current Month KBs",
            height=34,
            command=self.pull_current_month_kbs,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="Remove KB",
            height=34,
            fg_color=_BTN_MUTED,
            hover_color=_BTN_MUTED_HOV,
            text_color=_BTN_MUTED_TXT,
            command=self.remove_selected_auto_kb,
        ).pack(side="left")

        tree_frame, self.auto_tree = self._build_kb_tree(tab)
        tree_frame.grid(row=1, column=0, sticky="nsew")

    def _build_manual_tab(self, tab: ctk.CTkFrame):
        ctk.CTkLabel(tab, text="KB Name", anchor="w",
                     font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", pady=(6, 2))
        self.manual_name_var = tk.StringVar()
        ctk.CTkEntry(
            tab,
            textvariable=self.manual_name_var,
            placeholder_text="e.g. Cumulative Update for Windows Server 2016",
            height=34,
        ).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(6, 2))

        ctk.CTkLabel(tab, text="KB Number", anchor="w",
                     font=ctk.CTkFont(size=13)).grid(row=1, column=0, sticky="w", pady=(8, 2))

        kb_row = ctk.CTkFrame(tab, fg_color="transparent")
        kb_row.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(8, 2))

        self.manual_kb_var = tk.StringVar()
        ctk.CTkEntry(
            kb_row,
            textvariable=self.manual_kb_var,
            placeholder_text="KB5034123",
            width=168,
            height=34,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            kb_row,
            text="Add Manual KB",
            height=34,
            command=self.add_manual_kb,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            kb_row,
            text="Remove Selected",
            height=34,
            fg_color=_BTN_MUTED,
            hover_color=_BTN_MUTED_HOV,
            text_color=_BTN_MUTED_TXT,
            command=self.remove_selected_manual_kb,
        ).pack(side="left")

        tree_frame, self.manual_tree = self._build_kb_tree(tab)
        tree_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))

    @staticmethod
    def _build_kb_tree(parent) -> tuple:
        frame = tk.Frame(parent, background=_TREE_BG)

        tree = ttk.Treeview(
            frame,
            columns=("category", "kb", "title"),
            show="headings",
            style="Patch.Treeview",
            height=14,
        )
        tree.heading("category", text="Category")
        tree.heading("kb", text="KB")
        tree.heading("title", text="Title")
        tree.column("category", width=190, stretch=False)
        tree.column("kb", width=120, stretch=False)
        tree.column("title", width=800, stretch=True)

        tree.tag_configure("odd",  background=_TREE_BG)
        tree.tag_configure("even", background=_TREE_ALT_BG)

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        return frame, tree

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
        self.policy_textbox.insert("1.0", customer.get("policy_schedule", ""))
        self.policy_textbox.configure(state="disabled")

        # Load filter state into widgets (suppress auto-save during load)
        self._loading_filters = True
        filters = customer.get("filters", DEFAULT_FILTERS)
        active_products = filters.get("products", [])
        for product, var in self._filter_product_vars.items():
            var.set(product in active_products)
        self._filter_arch_var.set(filters.get("architecture", DEFAULT_FILTERS["architecture"]))
        self._loading_filters = False

        self.current_updates = customer.get("updates", {cat: [] for cat in ALL_CATEGORIES})
        self._populate_tree(self.auto_tree, self.current_updates)
        self._populate_tree(self.manual_tree, self.current_updates)

    def _on_filter_change(self, *_):
        """Called when any filter checkbox or arch dropdown changes."""
        if getattr(self, "_loading_filters", False):
            return
        if self.current_customer_idx is None:
            return

        filters = {
            "products": [p for p, v in self._filter_product_vars.items() if v.get()],
            "architecture": self._filter_arch_var.get(),
        }
        customer = self.customers[self.current_customer_idx]
        customer["filters"] = filters
        db.update_customer(customer)

        # Re-apply display filter immediately without re-pulling
        self._populate_tree(self.auto_tree, self.current_updates)
        self._populate_tree(self.manual_tree, self.current_updates)

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
        idx = self.get_selected_customer_index()
        if idx is None:
            return
        dlg = CustomerDialog(self.root, "Edit Customer", customer=self.customers[idx])
        if dlg.result_customer:
            dlg.result_customer["id"] = self.customers[idx]["id"]
            self.customers[idx] = dlg.result_customer
            db.update_customer(self.customers[idx])
            self.refresh_customer_list()
            self._select_customer(idx)

    def get_selected_customer_index(self) -> int | None:
        if self.current_customer_idx is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
            return None
        return self.current_customer_idx

    # ── KB tree ───────────────────────────────────────────────────────────────

    def _populate_tree(self, tree: ttk.Treeview, updates_by_category: dict):
        for item in tree.get_children():
            tree.delete(item)

        filters = None
        if self.current_customer_idx is not None:
            filters = self.customers[self.current_customer_idx].get("filters")

        row_num = 0
        for category in ALL_CATEGORIES:
            for item in updates_by_category.get(category, []):
                if not matches_product_filter(item.get("title", ""), filters):
                    continue
                tag = "odd" if row_num % 2 else "even"
                tree.insert(
                    "", "end",
                    values=(category, item.get("kb", ""), item.get("title", "")),
                    tags=(tag,),
                )
                row_num += 1

    # ── KB pull ───────────────────────────────────────────────────────────────

    def pull_current_month_kbs(self):
        try:
            import requests as _r  # noqa: F401
        except ImportError:
            messagebox.showerror(
                "Missing Dependencies",
                "This feature requires 'requests' and 'beautifulsoup4'.\n\n"
                "Install with:  pip install requests beautifulsoup4",
            )
            return

        self.status_var.set("Pulling current month KBs from Microsoft Update Catalog…")
        self.root.update_idletasks()

        try:
            filters = self.customers[self.current_customer_idx].get("filters") if self.current_customer_idx is not None else None
            updates = fetch_current_month_updates(filters=filters)
            self.current_updates = updates
            self._populate_tree(self.auto_tree, updates)
            self._populate_tree(self.manual_tree, updates)
            self._store_current_updates()

            total = sum(len(v) for v in updates.values())
            self.status_var.set(
                f"Pull complete — {total} update(s) found for {datetime.now():%B %Y}."
            )
            if total == 0:
                messagebox.showwarning(
                    "No Updates Found",
                    "No current-month Cumulative / SSU / .NET updates were found.\n"
                    "You can add entries via Manual KB Input.",
                )
        except Exception as exc:
            self.status_var.set("Pull failed.")
            messagebox.showerror("Pull Failed", f"Unable to fetch updates:\n\n{exc}")

    def _store_current_updates(self):
        if self.current_customer_idx is None:
            return
        customer = self.customers[self.current_customer_idx]
        customer["updates"]      = self.current_updates
        customer["last_updated"] = datetime.now().isoformat()
        db.update_customer(customer)

    # ── Manual KB ─────────────────────────────────────────────────────────────

    def add_manual_kb(self):
        if self.get_selected_customer_index() is None:
            return

        name = self.manual_name_var.get().strip()
        kb   = self.manual_kb_var.get().strip().upper()

        if not name:
            messagebox.showerror("Validation", "KB Name is required.")
            return

        kb_match = re.search(r"KB\d{6,8}", kb)
        if not kb_match:
            messagebox.showerror("Validation", "KB Number must look like KB5034123.")
            return

        category = classify_update(name)
        entry    = {"kb": kb_match.group(0), "title": name}

        bucket = self.current_updates.setdefault(category, [])
        if any(x.get("kb") == entry["kb"] and x.get("title") == entry["title"] for x in bucket):
            messagebox.showinfo("Duplicate", "That KB entry already exists.")
            return

        bucket.append(entry)
        self._populate_tree(self.manual_tree, self.current_updates)
        self._populate_tree(self.auto_tree, self.current_updates)
        self._store_current_updates()

        self.manual_name_var.set("")
        self.manual_kb_var.set("")
        self.status_var.set("Manual KB added.")

    def remove_selected_manual_kb(self):
        if self.get_selected_customer_index() is None:
            return

        selected = self.manual_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select a KB row in the Manual KB Input table.")
            return

        for item_id in selected:
            category, kb, title = self.manual_tree.item(item_id, "values")
            self.current_updates[category] = [
                e for e in self.current_updates.get(category, [])
                if not (e.get("kb") == kb and e.get("title") == title)
            ]

        self._populate_tree(self.manual_tree, self.current_updates)
        self._populate_tree(self.auto_tree, self.current_updates)
        self._store_current_updates()
        self.status_var.set("Selected manual KB entries removed.")

    def remove_selected_auto_kb(self):
        if self.get_selected_customer_index() is None:
            return

        selected = self.auto_tree.selection()
        if not selected:
            messagebox.showinfo("No Selection", "Select a KB row in the Automated Pull table.")
            return

        for item_id in selected:
            category, kb, title = self.auto_tree.item(item_id, "values")
            self.current_updates[category] = [
                e for e in self.current_updates.get(category, [])
                if not (e.get("kb") == kb and e.get("title") == title)
            ]

        self._populate_tree(self.auto_tree, self.current_updates)
        self._populate_tree(self.manual_tree, self.current_updates)
        self._store_current_updates()
        self.status_var.set("Selected KB entries removed.")

    # ── Outlook draft ─────────────────────────────────────────────────────────

    def draft_outlook_email(self):
        idx = self.get_selected_customer_index()
        if idx is None:
            return

        customer = self.customers[idx]
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
