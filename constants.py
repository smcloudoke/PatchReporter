APP_TITLE = "Patch Reporter"
CUSTOMERS_FILE = "customers.json"   # legacy — used only for one-time JSON migration
DB_FILE        = "patchreport.db"

CATEGORY_CUMULATIVE = "Cumulative Update"
CATEGORY_SSU        = "Servicing Stack Update"
CATEGORY_DOTNET     = ".NET Framework"
ALL_CATEGORIES      = [CATEGORY_CUMULATIVE, CATEGORY_SSU, CATEGORY_DOTNET]

MSRC_CVRF_BASE = "https://api.msrc.microsoft.com/cvrf/v3.0"

# ── Server patch statuses ──────────────────────────────────────────────────────
PATCH_STATUSES = ["Pending", "Patch Successful", "Patch Failed", "Reboot Required"]
STATUS_TAG = {
    "Pending":          "status_pending",
    "Patch Successful": "status_success",
    "Patch Failed":     "status_failed",
    "Reboot Required":  "status_reboot",
}
STATUS_ROW_FG = {
    "Pending":          "#8b8fa8",
    "Patch Successful": "#4ade80",
    "Patch Failed":     "#f87171",
    "Reboot Required":  "#fb923c",
}
STATUS_ROW_BG = {
    "Pending":          "#22253a",
    "Patch Successful": "#1a3a2a",
    "Patch Failed":     "#3a1a1a",
    "Reboot Required":  "#3a2a14",
}

# ── Patch filters ─────────────────────────────────────────────────────────────
PRODUCT_FAMILIES = [
    "Windows 10",
    "Windows 11",
    "Windows Server 2016",
    "Windows Server 2019",
    "Windows Server 2022",
    "Windows Server 2025",
]
ARCHITECTURES   = ["x64", "x86", "ARM64"]
DEFAULT_FILTERS = {"products": [], "architecture": "x64"}
# empty products list = no filter = show all (backward compatible)

# ── UI color palette ──────────────────────────────────────────────────────────
_SIDEBAR_FG    = ("#dce4ee", "#1e2030")
_CARD_FG       = ("gray96", "#24273a")
_TREE_BG       = "#22253a"
_TREE_ALT_BG   = "#1e2133"
_TREE_HEAD_BG  = "#1f538d"
_TREE_SEL_BG   = "#1f6aa5"
_BTN_MUTED     = ("gray75", "#3a3a4a")
_BTN_MUTED_HOV = ("gray65", "#4a4a5a")
_BTN_MUTED_TXT = ("gray10", "gray90")
