#!/usr/bin/env python3
"""
secrets_manager.py — Double-Fernet runtime decryption module with SecretSanitizer.

Double encryption: Fernet(PRIMARY).encrypt(Fernet(FALLBACK).encrypt(plaintext))
Both ENCRYPTION_KEY_PRIMARY and ENCRYPTION_KEY_FALLBACK must be set via env or .env file.
Zero hardcoded configuration values exist in codebase; all runtime credentials & brand details are fetched from secrets.enc.
"""

import logging
import os
import json
import sys
import datetime
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    print("ERROR: cryptography package missing. Run: pip install cryptography", file=sys.stderr)
    sys.exit(1)


# ── SecretSanitizer ────────────────────────────────────────────────────────────

class SecretSanitizer(logging.Filter):
    """Scrubs decrypted secret values from all log records to prevent token leakage."""

    _values: set = set()

    @classmethod
    def register(cls, value: str) -> None:
        if value and len(value) > 3:
            cls._values.add(value)

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for secret in self.__class__._values:
            if secret in msg:
                record.msg = record.msg.replace(secret, "***REDACTED***")
                record.args = ()
        return True


def _install_sanitizer() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(SecretSanitizer())
    root.addFilter(SecretSanitizer())


_sanitizer_installed = False


# ── Key loading ───────────────────────────────────────────────────────────────

def _load_dotenv() -> None:
    """Load PRIMARY and FALLBACK keys from .env if present."""
    search_paths = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(".env")
    ]
    for candidate in search_paths:
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ("ENCRYPTION_KEY_PRIMARY", "ENCRYPTION_KEY_FALLBACK"):
                os.environ.setdefault(key, val)


def _get_keys() -> tuple:
    _load_dotenv()
    primary = os.environ.get("ENCRYPTION_KEY_PRIMARY", "").strip()
    fallback = os.environ.get("ENCRYPTION_KEY_FALLBACK", "").strip()
    missing = []
    if not primary:
        missing.append("ENCRYPTION_KEY_PRIMARY")
    if not fallback:
        missing.append("ENCRYPTION_KEY_FALLBACK")
    if missing:
        raise RuntimeError(
            "\n[secrets_manager] Missing environment variables: " + ", ".join(missing) + "\n"
            "  Local dev  : add them to your .env file\n"
            "  GitHub CI  : add them as repo secrets\n"
        )
    return primary.encode(), fallback.encode()


# ── Vault loading ─────────────────────────────────────────────────────────────

def _load_vault() -> dict:
    search_paths = [
        Path(__file__).resolve().parent.parent / "secrets.enc",
        Path(__file__).resolve().parent / "secrets.enc",
        Path("secrets.enc")
    ]
    for candidate in search_paths:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        "\n[secrets_manager] secrets.enc file not found.\n"
        "  Run: python scripts/encrypt_secrets.py to generate secrets.enc\n"
    )


# ── Decryption ────────────────────────────────────────────────────────────────

def _double_decrypt(ciphertext: str, primary: bytes, fallback: bytes) -> str:
    """Decrypt using Double-Fernet: Fernet(FALLBACK).decrypt(Fernet(PRIMARY).decrypt(ciphertext))"""
    try:
        inner = Fernet(primary).decrypt(ciphertext.encode())
        return Fernet(fallback).decrypt(inner).decode("utf-8")
    except InvalidToken:
        raise RuntimeError(
            "\n[secrets_manager] Decryption failed — incorrect encryption keys or corrupted secrets.enc.\n"
            "  Verify ENCRYPTION_KEY_PRIMARY and ENCRYPTION_KEY_FALLBACK.\n"
        )


def _audit(name: str) -> None:
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    caller = "unknown"
    try:
        import inspect
        frame = inspect.stack()[2]
        caller = f"{Path(frame.filename).name}:{frame.lineno}"
    except Exception:
        pass
    logging.getLogger(__name__).debug("[secrets] get_secret(%r) requested by %s at %s", name, caller, ts)


# ── Public API ────────────────────────────────────────────────────────────────

def get_secret(name: str, default: str = None) -> str:
    """Decrypt and return a single secret value by key name."""
    global _sanitizer_installed
    if not _sanitizer_installed:
        _install_sanitizer()
        _sanitizer_installed = True

    _load_dotenv()
    
    # Priority 1: Direct OS environment variable
    if os.environ.get(name):
        val = os.environ[name]
        SecretSanitizer.register(val)
        return val

    # Priority 2: Decrypt from secrets.enc vault
    try:
        primary, fallback = _get_keys()
        vault = _load_vault()
        if name in vault:
            _audit(name)
            value = _double_decrypt(vault[name], primary, fallback)
            SecretSanitizer.register(value)
            return value
    except Exception:
        pass

    if default is not None:
        return default

    raise KeyError(f"\n[secrets_manager] Secret '{name}' not found in environment or secrets.enc.\n")


def get_all_secrets() -> dict:
    """Decrypt all secrets and return as a dictionary."""
    global _sanitizer_installed
    if not _sanitizer_installed:
        _install_sanitizer()
        _sanitizer_installed = True

    primary, fallback = _get_keys()
    vault = _load_vault()
    result = {}
    for name, ciphertext in vault.items():
        value = _double_decrypt(ciphertext, primary, fallback)
        SecretSanitizer.register(value)
        result[name] = value
    return result


def inject_to_env() -> None:
    """Decrypt all secrets and inject them into os.environ for the current process."""
    _load_dotenv()
    try:
        for name, value in get_all_secrets().items():
            os.environ.setdefault(name, value)
    except Exception as e:
        logging.getLogger(__name__).warning("Could not inject encrypted secrets to env: %s", str(e))
