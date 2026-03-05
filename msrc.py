import re
import xml.etree.ElementTree as ET
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - runtime dependency guard
    requests = None
    BeautifulSoup = None

from constants import (
    ALL_CATEGORIES,
    CATEGORY_CUMULATIVE,
    CATEGORY_DOTNET,
    CATEGORY_SSU,
    MSRC_CVRF_BASE,
)

# ── Filter matching tables ─────────────────────────────────────────────────────

# Keywords that must appear in a title for it to match each product family.
PRODUCT_KEYWORDS: dict[str, list[str]] = {
    "Windows 10":          ["windows 10"],
    "Windows 11":          ["windows 11"],
    "Windows Server 2016": ["windows server 2016"],
    "Windows Server 2019": ["windows server 2019"],
    "Windows Server 2022": ["windows server 2022", "server operating system version 21h2"],
    "Windows Server 2025": ["windows server 2025", "server operating system version 24h2"],
}

# Architecture keyword that must appear in the title when a specific arch is chosen.
# Titles that mention no arch keyword at all pass through (Server editions often omit it).
ARCH_KEYWORDS: dict[str, str] = {
    "x64":   "x64-based",
    "x86":   "x86-based",
    "ARM64": "arm64-based",
}


def matches_product_filter(title: str, filters: dict | None) -> bool:
    """
    Return True if the KB title matches the customer's product/arch filters.

    Rules:
    - No filters or empty products list → no filter applied, always True.
    - Architecture: if the title explicitly mentions any arch keyword, enforce
      the selected arch; if no arch keyword present, pass (implicitly correct).
    - Product: title must match at least one selected product's keywords.
    """
    if not filters:
        return True

    lower = title.lower()
    selected_products = filters.get("products", [])
    selected_arch     = filters.get("architecture", "x64")

    # Architecture check (only enforce when title is explicit about arch)
    arch_kw = ARCH_KEYWORDS.get(selected_arch, "")
    if arch_kw and any(kw in lower for kw in ARCH_KEYWORDS.values()):
        if arch_kw not in lower:
            return False

    # Product check
    if not selected_products:
        return True  # empty = no product filter

    return any(
        any(kw in lower for kw in PRODUCT_KEYWORDS.get(product, [product.lower()]))
        for product in selected_products
    )


# ─── Pull orchestration ───────────────────────────────────────────────────────

def fetch_current_month_updates(filters: dict | None = None) -> dict:
    now = datetime.now()
    month_candidates = [now, previous_month(now)]

    for month_date in month_candidates:
        collected = {cat: [] for cat in ALL_CATEGORIES}
        seen: set = set()
        yyyy_mm = f"{month_date.year}-{month_date.month:02d}"

        kbs = fetch_msrc_month_kbs(month_date)
        for kb in sorted(kbs):
            catalog_rows = search_update_catalog(kb)
            for row in catalog_rows:
                add_row_if_relevant(
                    collected, seen, row,
                    fallback_kb=kb, month_date=month_date, filters=filters,
                )

        # Supplemental queries for SSU and .NET — product-aware when filters set
        selected_products = (filters or {}).get("products", [])
        if selected_products:
            catalog_queries = []
            for product in selected_products:
                if "server" in product.lower():
                    catalog_queries.append(
                        f"{yyyy_mm} servicing stack update {product.lower()}"
                    )
            catalog_queries.append(f"{yyyy_mm} cumulative update .net framework")
            catalog_queries.append(f"{yyyy_mm} security and quality rollup .net framework")
        else:
            # Backward-compatible defaults (no product filter selected)
            catalog_queries = [
                f"{yyyy_mm} servicing stack update windows server 2016",
                f"{yyyy_mm} cumulative update .net framework",
                f"{yyyy_mm} security and quality rollup .net framework",
            ]

        for query in catalog_queries:
            rows = search_update_catalog(query)
            for row in rows:
                add_row_if_relevant(
                    collected, seen, row,
                    fallback_kb="", month_date=month_date, filters=filters,
                )

        for category in collected:
            collected[category].sort(key=lambda x: (x["kb"], x["title"]))

        if sum(len(v) for v in collected.values()) > 0:
            return collected

    return {cat: [] for cat in ALL_CATEGORIES}


# ─── MSRC CVRF API ────────────────────────────────────────────────────────────

def fetch_msrc_month_kbs(now: datetime) -> set:
    release_id = now.strftime("%Y-%b")
    url = f"{MSRC_CVRF_BASE}/cvrf/{release_id}"
    response = requests.get(url, timeout=60, headers={"Accept": "application/xml"})
    if response.status_code == 404:
        return set()
    response.raise_for_status()
    return extract_kbs_from_cvrf_xml(response.text)


def extract_kbs_from_cvrf_xml(xml_text: str) -> set:
    root = ET.fromstring(xml_text)
    found: set = set()

    for elem in root.iter():
        if local_name(elem.tag) != "Remediation":
            continue
        blob = " ".join((part or "").strip() for part in elem.itertext())
        for kb in extract_kbs_from_text(blob):
            found.add(kb)

    return found


def extract_kbs_from_text(text: str) -> set:
    normalized = text or ""
    found: set = set()

    for match in re.findall(r"KB\d{6,8}", normalized, flags=re.IGNORECASE):
        found.add(match.upper())

    # CVRF remediation descriptions sometimes contain only numeric KB article IDs.
    for match in re.findall(r"\b\d{6,8}\b", normalized):
        found.add(f"KB{match}")

    return found


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def previous_month(dt: datetime) -> datetime:
    year = dt.year
    month = dt.month - 1
    if month == 0:
        month = 12
        year -= 1
    return dt.replace(year=year, month=month)


# ─── Microsoft Update Catalog scraping ───────────────────────────────────────

def search_update_catalog(query: str) -> list:
    url = "https://www.catalog.update.microsoft.com/v7/site/Search.aspx"
    response = requests.get(
        url,
        params={"q": query},
        timeout=45,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table", id=re.compile(r"updateMatches|ctl00_catalogBody_updateMatches"))
    if table is None:
        table = soup.find("table")
        if table is None:
            return []

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue

        title = ""
        for a in tr.find_all("a"):
            text = clean_text(a.get_text(" ", strip=True))
            if text and "KB" in text.upper():
                title = text
                break
        if not title:
            title = clean_text(cells[1].get_text(" ", strip=True))

        products       = clean_text(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
        classification = clean_text(cells[3].get_text(" ", strip=True)) if len(cells) > 3 else ""
        updated        = clean_text(cells[4].get_text(" ", strip=True)) if len(cells) > 4 else ""

        if not title:
            continue

        rows.append({
            "title": title,
            "products": products,
            "classification": classification,
            "updated": updated,
        })

    return rows


# ─── Row filtering / classification ──────────────────────────────────────────

def add_row_if_relevant(collected: dict, seen: set, row: dict,
                         fallback_kb: str, month_date: datetime,
                         filters: dict | None = None):
    title   = row.get("title", "")
    updated = row.get("updated", "")
    row_kb  = extract_kb(title) or fallback_kb
    if not row_kb:
        return
    if not is_current_month_update(title, updated, month_date):
        return

    category = classify_update(title)
    if category not in ALL_CATEGORIES:
        return
    if not matches_requested_families(title, category):
        return
    if not matches_product_filter(title, filters):
        return

    key = (row_kb, title)
    if key in seen:
        return
    seen.add(key)
    collected[category].append({"kb": row_kb, "title": title})


def matches_requested_families(title: str, category: str) -> bool:
    lower = title.lower()

    if category == CATEGORY_CUMULATIVE:
        return "cumulative update" in lower

    if category == CATEGORY_SSU:
        return "servicing stack update" in lower

    if category == CATEGORY_DOTNET:
        return (
            ".net framework" in lower
            or " for .net " in f" {lower} "
            or ("security and quality rollup" in lower and ".net" in lower)
            or ("cumulative update" in lower and ".net" in lower)
        )

    return False


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_kb(title: str) -> str:
    match = re.search(r"KB\d{6,8}", title, flags=re.IGNORECASE)
    return match.group(0).upper() if match else ""


def classify_update(title: str) -> str:
    lower = title.lower()
    if "servicing stack update" in lower or re.search(r"\bssu\b", lower):
        return CATEGORY_SSU
    if (
        ".net framework" in lower
        or " for .net " in f" {lower} "
        or ("security and quality rollup" in lower and ".net" in lower)
    ):
        return CATEGORY_DOTNET
    if "cumulative update" in lower:
        return CATEGORY_CUMULATIVE
    return CATEGORY_CUMULATIVE


def is_current_month_update(title: str, updated_text: str, now: datetime) -> bool:
    title_lower  = title.lower()
    month_name   = now.strftime("%B").lower()
    month_abbrev = now.strftime("%b").lower()
    yyyy_mm      = f"{now.year}-{now.month:02d}"

    if yyyy_mm in title_lower:
        return True
    if f"{month_name} {now.year}" in title_lower or f"{month_abbrev} {now.year}" in title_lower:
        return True

    if updated_text:
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y"):
            try:
                dt = datetime.strptime(updated_text, fmt)
                return dt.year == now.year and dt.month == now.month
            except ValueError:
                continue

    return False
