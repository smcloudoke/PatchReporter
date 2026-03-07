import customtkinter as ctk

from constants import _CARD_FG


class ServerPanel(ctk.CTkFrame):
    """
    Server management panel — home for the upcoming pre/post patch report feature.

    Planned functionality:
    - CSV import of server inventory per customer (hostname, OS version, role)
    - Per-server patch status selection (Patch Successful / Failed / Reboot Required)
    - Pre-patch and post-patch report generation
    - Servers grouped/sorted by OS version and relevant KBs
    """

    def __init__(self, parent, app):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.app = app
        self._build_placeholder()

    def _build_placeholder(self):
        card = ctk.CTkFrame(self, fg_color=_CARD_FG, corner_radius=14)
        card.pack(fill="both", expand=True)
        ctk.CTkLabel(
            card,
            text="Server management — coming soon",
            font=ctk.CTkFont(size=14),
            text_color=("gray45", "gray55"),
        ).pack(expand=True)
