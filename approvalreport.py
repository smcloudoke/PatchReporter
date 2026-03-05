import customtkinter as ctk

import db
from ui import ApprovalReportApp


def main():
    db.init_db()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = ApprovalReportApp(root)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
