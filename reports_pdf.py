from collections import Counter

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from constants import ALL_CATEGORIES

# ── Shared style helpers ───────────────────────────────────────────────────────

_HEAD_BG    = "#1f538d"
_ROW_A      = "#f5f7fa"
_ROW_B      = "#ffffff"
_GRID_COLOR = "#d0d4dc"

_STATUS_ROW_BG = {
    "Installed": "#d4edda",
    "Failed":     "#f8d7da",
    "Reboot Required":  "#fff3cd",
    "Pending":          "#f5f5f5",
}

def _doc(filepath: str, title: str) -> "SimpleDocTemplate":
    return SimpleDocTemplate(
        filepath,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=title,
    )


def _table_base_style() -> list:
    return [
        ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor(_HEAD_BG)),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor(_GRID_COLOR)),
        ("ALIGN",       (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]


def _alternating_rows(n_rows: int) -> list:
    cmds = []
    for i in range(1, n_rows):
        bg = _ROW_A if i % 2 else _ROW_B
        cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(bg)))
    return cmds


# ── Public report builders ─────────────────────────────────────────────────────

def build_pre_patch_pdf(filepath: str, customer: dict, month: str,
                        updates: dict, servers: list, policy: str = ""):
    """
    Pre-patch report: KBs to be applied + server inventory.
    `updates` is the standard {category: [{kb, title}]} dict.
    `servers` is a list of {hostname, os_version} dicts.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab is not installed. Run: pip install reportlab")

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Pre-Patch Report", styles["Title"]))
    elements.append(Paragraph(
        f"{customer.get('company_name', '')}  —  {month}",
        styles["Heading2"],
    ))
    if policy and policy != "—":
        elements.append(Paragraph(f"Policy: {policy}", styles["Normal"]))
    elements.append(Spacer(1, 0.2 * inch))

    # ── KBs to be applied ─────────────────────────────────────────────────────
    elements.append(Paragraph("Patches to be Applied", styles["Heading3"]))
    elements.append(Spacer(1, 0.05 * inch))

    normal = getSampleStyleSheet()["Normal"]
    normal.fontSize = 9
    kb_rows = [["Category", "KB", "Title"]]
    for category in ALL_CATEGORIES:
        for entry in updates.get(category, []):
            kb_rows.append([category, entry.get("kb", ""), Paragraph(entry.get("title", ""), normal)])

    if len(kb_rows) > 1:
        kb_table = Table(kb_rows, colWidths=[1.4 * inch, 1.0 * inch, 4.6 * inch])
        style_cmds = _table_base_style() + _alternating_rows(len(kb_rows))
        kb_table.setStyle(TableStyle(style_cmds))
        elements.append(kb_table)
    else:
        elements.append(Paragraph("No KBs loaded for this customer.", styles["Normal"]))

    elements.append(Spacer(1, 0.3 * inch))

    # ── Server inventory ──────────────────────────────────────────────────────
    elements.append(Paragraph("Server Inventory", styles["Heading3"]))
    elements.append(Spacer(1, 0.05 * inch))

    if servers:
        srv_rows = [["Hostname", "OS Version"]]
        for srv in servers:
            srv_rows.append([srv.get("hostname", ""), srv.get("os_version", "")])

        srv_table = Table(srv_rows, colWidths=[3.0 * inch, 4.0 * inch])
        style_cmds = _table_base_style() + _alternating_rows(len(srv_rows))
        srv_table.setStyle(TableStyle(style_cmds))
        elements.append(srv_table)
    else:
        elements.append(Paragraph("No servers imported for this customer.", styles["Normal"]))

    _doc(filepath, f"Pre-Patch — {customer.get('company_name', '')} — {month}").build(elements)


def build_post_patch_pdf(filepath: str, customer: dict, month: str,
                         server_statuses: list, policy: str = ""):
    """
    Post-patch report: summary counts + per-server status table.
    `server_statuses` is a list of {hostname, os_version, patch_kb, patch_name, status} dicts.
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab is not installed. Run: pip install reportlab")

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Post-Patch Report", styles["Title"]))
    elements.append(Paragraph(
        f"{customer.get('company_name', '')}  —  {month}",
        styles["Heading2"],
    ))
    if policy and policy != "—":
        elements.append(Paragraph(f"Policy: {policy}", styles["Normal"]))
    elements.append(Spacer(1, 0.2 * inch))

    # ── Summary ───────────────────────────────────────────────────────────────
    elements.append(Paragraph("Summary", styles["Heading3"]))
    counts = Counter(s["status"] for s in server_statuses)
    total  = len(server_statuses)
    for line in [
        f"Total Servers: {total}",
        f"Installed: {counts.get('Installed', 0)}",
        f"Failed: {counts.get('Failed', 0)}",
        f"Reboot Required: {counts.get('Reboot Required', 0)}",
        f"Pending: {counts.get('Pending', 0)}",
    ]:
        elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 0.25 * inch))

    # ── Server status table ───────────────────────────────────────────────────
    elements.append(Paragraph("Server Patch Status", styles["Heading3"]))
    elements.append(Spacer(1, 0.05 * inch))

    if server_statuses:
        normal = getSampleStyleSheet()["Normal"]
        normal.fontSize = 9
        srv_rows = [["Hostname", "OS Version", "KB", "Patch Name", "Status"]]
        for srv in server_statuses:
            srv_rows.append([
                srv.get("hostname", ""),
                srv.get("os_version", ""),
                srv.get("patch_kb", ""),
                Paragraph(srv.get("patch_name", ""), normal),
                srv.get("status", ""),
            ])

        srv_table = Table(srv_rows, colWidths=[1.4 * inch, 1.5 * inch, 0.8 * inch, 2.3 * inch, 1.0 * inch])
        style_cmds = _table_base_style()
        for i, srv in enumerate(server_statuses, start=1):
            bg = _STATUS_ROW_BG.get(srv.get("status", ""), _ROW_B)
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(bg)))
        srv_table.setStyle(TableStyle(style_cmds))
        elements.append(srv_table)
    else:
        elements.append(Paragraph("No server data available.", styles["Normal"]))

    _doc(filepath, f"Post-Patch — {customer.get('company_name', '')} — {month}").build(elements)
