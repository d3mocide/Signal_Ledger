"""Optional encrypted raw-upload storage with a legacy plaintext path."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet | None:
    key = os.getenv("RAW_STORAGE_ENCRYPTION_KEY")
    return Fernet(key.encode()) if key else None


def encryption_configured() -> bool:
    return _fernet() is not None


def write_raw(path: Path, blob: bytes) -> bool:
    fernet = _fernet()
    path.write_bytes(fernet.encrypt(blob) if fernet else blob)
    return fernet is not None


@contextmanager
def materialize_raw(path: str, encrypted: bool):
    if not encrypted:
        yield path
        return
    fernet = _fernet()
    if not fernet:
        raise ValueError("Raw storage encryption is not configured")
    try:
        blob = fernet.decrypt(Path(path).read_bytes())
    except InvalidToken as error:
        raise ValueError("Raw upload could not be decrypted with the configured storage key") from error
    temporary = tempfile.NamedTemporaryFile(prefix="signal-ledger-raw-", suffix=".capture", delete=False)
    temporary_path = temporary.name
    try:
        temporary.write(blob)
        temporary.close()
        yield temporary_path
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
