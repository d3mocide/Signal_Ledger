"""Reversible encryption for the real device address, used only for
policy-approved "exact" areas. Everywhere else the app only ever handles the
one-way HMAC token; this module is the sole place a real MAC/BSSID can be
recovered, and only when ADDRESS_ENCRYPTION_KEY is configured."""
import os
from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet | None:
    key = os.getenv("ADDRESS_ENCRYPTION_KEY")
    return Fernet(key.encode()) if key else None


def address_encryption_configured() -> bool:
    return _fernet() is not None


def encrypt_address(normalized_mac: str) -> str | None:
    fernet = _fernet()
    return fernet.encrypt(normalized_mac.encode()).decode() if fernet else None


def decrypt_address(token: str) -> str:
    fernet = _fernet()
    if not fernet:
        raise ValueError("Address encryption is not configured")
    try:
        raw = fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("Stored address could not be decrypted with the current key")
    return ":".join(raw[i : i + 2] for i in range(0, len(raw), 2))
