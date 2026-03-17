from datetime import datetime
from email.utils import getaddresses

from constants import ALL_CATEGORIES, PRODUCT_FAMILIES
from msrc import PRODUCT_KEYWORDS

# Display order for OS version sections — mirrors PRODUCT_FAMILIES in constants.py
_OS_ORDER = PRODUCT_FAMILIES


def normalize_email_list(raw: str) -> str:
    emails = [addr for _, addr in getaddresses([raw]) if addr]
    return "; ".join(emails)


def build_report_email(customer: dict, updates: dict) -> tuple[str, str]:
    now        = datetime.now()
    month_year = now.strftime("%B %Y")
    company    = customer.get("company_name", "Customer")

    subject = f"Information Regarding the {month_year} Cumulative Updates From Microsoft"

    # Flatten all KB entries across categories, preserving their category label
    all_entries: list[dict] = []
    for category in ALL_CATEGORIES:
        for item in updates.get(category, []):
            all_entries.append({**item, "category": category})

    # Group by OS version using the same keyword matching as msrc.py
    grouped: dict[str, list[dict]] = {os: [] for os in _OS_ORDER}
    ungrouped: list[dict] = []

    for entry in all_entries:
        title_lower = entry["title"].lower()
        matched = False
        for os_name in _OS_ORDER:
            if any(kw in title_lower for kw in PRODUCT_KEYWORDS[os_name]):
                grouped[os_name].append(entry)
                matched = True
                break
        if not matched:
            ungrouped.append(entry)

    sections = []
    for os_name in _OS_ORDER:
        entries = grouped[os_name]
        if not entries:
            continue
        li = "".join(
            f"<li><strong>{e.get('kb', '')}</strong>: {escape_html(e.get('title', ''))}</li>"
            for e in entries
        )
        sections.append(f"<h3 style='color:#1e4e79;'>{os_name}</h3><ul>{li}</ul>")

    if ungrouped:
        li = "".join(
            f"<li><strong>{e.get('kb', '')}</strong>: {escape_html(e.get('title', ''))}</li>"
            for e in ungrouped
        )
        sections.append(f"<h3 style='color:#1e4e79;'>Other</h3><ul>{li}</ul>")

    if not sections:
        sections.append("<p><em>No KBs populated yet.</em></p>")

    schedule     = escape_html(customer.get("policy_schedule", "")).replace("\n", "<br>")
    patch_notes  = escape_html(customer.get("patch_notes", "")).replace("\n", "<br>")

    known_issues_section = (
        f"<p>{patch_notes}</p>"
        if patch_notes
        else "<p><em>No known issues for this month.</em></p>"
    )

    html_body = f"""
<html>
  <body style="font-family:Segoe UI,Arial,sans-serif;font-size:11pt;color:#222;">
    <h1 style="color:#00264d;">Information Regarding the {month_year} Cumulative Updates From Microsoft</h1>
    <p>We have reviewed the {month_year} patches for potential vulnerabilities and the likelihood of issues. Below are our findings and approvals:</p>

    <h2 style="color:#1e4e79;">Approved Updates</h2>
    <p>Cumulative Updates are approved for all server and workstation versions.</p>

    {''.join(sections)}

    <h2 style="color:#004080;">Known Patch Issues</h2>
    {known_issues_section}

    <h2 style="color:#004080;">Current Month Schedule ({company})</h2>
    <p>{schedule or 'No schedule/policy entered.'}</p>

    <h2 style="color:#004080;">End-of-Life Announcements</h2>
    <p><strong>Windows Server EOL</strong><br>Support for Server 2012 and 2012 R2 has ended. Extended services must be purchased from Microsoft for continued updates.</p>
    <p><strong>Windows 7 / 8 / 8.1</strong><br>Extended support for Windows 7 and Windows 8/8.1, including Server 2008 SP2/R2, has ceased.</p>
    <p><strong>Windows 11 End of Servicing</strong><br>Multiple editions of Windows 11 have reached their end of servicing.</p>

    <h2 style="color:#004080;">Additional Notes</h2>
    <p>For organizations not receiving Windows OS Patching through Presidio, this information may still provide value.<br>If you encounter any issues, please contact our Support Team at:<br>800-494-0118</p>
  </body>
</html>
""".strip()

    return subject, html_body


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )
