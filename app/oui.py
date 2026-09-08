"""Small seeded OUI catalog. Replace with a reviewed IEEE import during operations."""
OUI_VERSION = "seed-2026-09"
PREFIXES = {
    "00163E": "Cisco Systems, Inc",
    "3C5A37": "Google, Inc.",
    "F4F5D8": "Google, Inc.",
    "A4C138": "Cisco Systems, Inc",
    "B827EB": "Raspberry Pi Foundation",
    "D850E6": "Apple, Inc.",
}

def vendor_for(prefix: str | None) -> str:
    return PREFIXES.get(prefix or "", "unattributable")
