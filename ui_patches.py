import re
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import customtkinter as ctk

import db
from constants import (
    ALL_CATEGORIES,
    ARCHITECTURES,
    DEFAULT_FILTERS,
    PRODUCT_FAMILIES,
    _BTN_MUTED,
    _BTN_MUTED_HOV,
    _BTN_MUTED_TXT,
    _CARD_FG,
    _TREE_ALT_BG,
    _TREE_BG,
    _TREE_HEAD_BG,
    _TREE_SEL_BG,
)
from msrc import classify_update, fetch_current_month_updates, matches_product_filter


def style_treeview():
    """Apply the dark Patch.Treeview style. Call once before any Treeview is created."""
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
    style.map("Patch.Treeview.Heading", background=[("active", "#2980b9")])
    style.configure(
        "Vertical.TScrollbar",
        background="#3a3d52",
        troughcolor=_TREE_BG,
        arrowcolor="#d8dce8",
        borderwidth=0,
    )


class PatchPanel(ctk.CTkFrame):
    """
    Owns the Product Scope filter card, Automated Pull tab, and Manual KB Input tab.
    Communicates with the parent app via the `app` reference for customer state and
    status bar updates.
    """

    def __init__(self, parent, app):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app
        self.current_updates: dict = {cat: [] for cat in ALL_CATEGORIES}
        self._filter_product_vars: dict[str, tk.BooleanVar] = {}
        self._filter_arch_var = tk.StringVar(value=DEFAULT_FILTERS["architecture"])
        self._loading_filters = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # tabs expand vertically

        self._build_filter_card()
        self._build_tabs()
        self._build_bottom_bar()

    # ── Bottom bar ────────────────────────────────────────────────────────────

    def _build_bottom_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent", height=54)
        bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_propagate(False)

        ctk.CTkButton(
            bar,
            text="  Draft Outlook Email  ",
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self.app.draft_outlook_email(),
        ).grid(row=0, column=1, sticky="e")

    # ── Filter card ───────────────────────────────────────────────────────────

    def _build_filter_card(self):
        card = ctk.CTkFrame(self, fg_color=_CARD_FG, corner_radius=14)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

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

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(self, height=320, fg_color=_CARD_FG)
        self.tabview.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

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
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="Known Patch Issues",
            height=34,
            fg_color=_BTN_MUTED,
            hover_color=_BTN_MUTED_HOV,
            text_color=_BTN_MUTED_TXT,
            command=self._open_patch_issues,
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

    # ── Customer display ──────────────────────────────────────────────────────

    def display_customer(self, customer: dict):
        """Load filter state and KB data for the given customer into the panel."""
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
        if self._loading_filters:
            return
        if self.app.current_customer_idx is None:
            return

        filters = {
            "products": [p for p, v in self._filter_product_vars.items() if v.get()],
            "architecture": self._filter_arch_var.get(),
        }
        customer = self.app.customers[self.app.current_customer_idx]
        customer["filters"] = filters
        db.update_customer(customer)

        self._populate_tree(self.auto_tree, self.current_updates)
        self._populate_tree(self.manual_tree, self.current_updates)

    # ── Tree population ───────────────────────────────────────────────────────

    def _populate_tree(self, tree: ttk.Treeview, updates_by_category: dict):
        for item in tree.get_children():
            tree.delete(item)

        filters = None
        if self.app.current_customer_idx is not None:
            filters = self.app.customers[self.app.current_customer_idx].get("filters")

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

    # ── Known patch issues ────────────────────────────────────────────────────

    def _open_patch_issues(self):
        if self.app.current_customer_idx is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
            return
        customer = self.app.customers[self.app.current_customer_idx]

        def on_save(notes: str):
            customer["patch_notes"] = notes
            db.update_customer(customer)
            self.app.status_var.set("Patch issues saved.")

        _KnownIssuesDialog(self, current_notes=customer.get("patch_notes", ""), on_save=on_save)

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

        self.app.status_var.set("Pulling current month KBs from Microsoft Update Catalog…")
        self.app.root.update_idletasks()

        try:
            filters = (
                self.app.customers[self.app.current_customer_idx].get("filters")
                if self.app.current_customer_idx is not None else None
            )
            updates = fetch_current_month_updates(filters=filters)
            self.current_updates = updates
            self._populate_tree(self.auto_tree, updates)
            self._populate_tree(self.manual_tree, updates)
            self._store_current_updates()

            total = sum(len(v) for v in updates.values())
            self.app.status_var.set(
                f"Pull complete — {total} update(s) found for {datetime.now():%B %Y}."
            )
            if total == 0:
                messagebox.showwarning(
                    "No Updates Found",
                    "No current-month Cumulative / SSU / .NET updates were found.\n"
                    "You can add entries via Manual KB Input.",
                )
        except Exception as exc:
            self.app.status_var.set("Pull failed.")
            messagebox.showerror("Pull Failed", f"Unable to fetch updates:\n\n{exc}")

    def _store_current_updates(self):
        if self.app.current_customer_idx is None:
            return
        customer = self.app.customers[self.app.current_customer_idx]
        customer["updates"] = self.current_updates
        customer["last_updated"] = datetime.now().isoformat()
        db.update_customer(customer)

    # ── Manual KB ─────────────────────────────────────────────────────────────

    def add_manual_kb(self):
        if self.app.current_customer_idx is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
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
        self.app.status_var.set("Manual KB added.")

    def remove_selected_manual_kb(self):
        if self.app.current_customer_idx is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
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
        self.app.status_var.set("Selected manual KB entries removed.")

    def remove_selected_auto_kb(self):
        if self.app.current_customer_idx is None:
            messagebox.showinfo("No Customer", "Please select a customer first.")
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
        self.app.status_var.set("Selected KB entries removed.")


# ── Known patch issues dialog ──────────────────────────────────────────────────

class _KnownIssuesDialog(ctk.CTkToplevel):
    def __init__(self, parent, current_notes: str, on_save):
        super().__init__(parent)
        self.title("Known Patch Issues")
        self.geometry("640x360")
        self.resizable(True, True)
        self.after(50, self.grab_set)
        self.lift()
        self._on_save = on_save

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="Enter any known issues or notes for this month's patches.\nThis will appear in the Patch Issues section of the Outlook email draft.",
            font=ctk.CTkFont(size=12),
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))

        self._textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(size=12), wrap="word")
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        if current_notes:
            self._textbox.insert("1.0", current_notes)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 16))

        ctk.CTkButton(
            btn_frame, text="Cancel", width=90, height=36,
            fg_color=_BTN_MUTED, hover_color=_BTN_MUTED_HOV, text_color=_BTN_MUTED_TXT,
            command=self.destroy,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btn_frame, text="Save", width=90, height=36,
            command=self._save,
        ).pack(side="right")

    def _save(self):
        self._on_save(self._textbox.get("1.0", "end").rstrip())
        self.destroy()
