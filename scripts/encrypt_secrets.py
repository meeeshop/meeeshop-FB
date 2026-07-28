#!/usr/bin/env python3
"""
encrypt_secrets.py — Encryption tool to encrypt project secrets into secrets.enc using Double-Fernet.

Double encryption scheme:
  Fernet(PRIMARY).encrypt(Fernet(FALLBACK).encrypt(plaintext.encode())).decode('utf-8')

Usage:
  python scripts/encrypt_secrets.py --generate-keys
  python scripts/encrypt_secrets.py --input secrets.json --primary <KEY> --fallback <KEY>
"""

import os
import sys
import json
import argparse
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("ERROR: cryptography package missing. Run: pip install cryptography", file=sys.stderr)
    sys.exit(1)


def double_encrypt(plaintext: str, primary_key: str, fallback_key: str) -> str:
    """Encrypt using Double-Fernet: Fernet(PRIMARY).encrypt(Fernet(FALLBACK).encrypt(plaintext))"""
    f_fallback = Fernet(fallback_key.encode("utf-8"))
    f_primary = Fernet(primary_key.encode("utf-8"))
    
    inner = f_fallback.encrypt(plaintext.encode("utf-8"))
    outer = f_primary.encrypt(inner)
    return outer.decode("utf-8")


def generate_keys():
    primary = Fernet.generate_key().decode("utf-8")
    fallback = Fernet.generate_key().decode("utf-8")
    print("🔑 Generated New Double Encryption Keys:")
    print("=" * 60)
    print(f"ENCRYPTION_KEY_PRIMARY  = {primary}")
    print(f"ENCRYPTION_KEY_FALLBACK = {fallback}")
    print("=" * 60)
    print("\n⚠️ Add these keys to your .env file or GitHub Repository Secrets!")
    return primary, fallback


def encrypt_dict(secrets_dict: dict, primary_key: str, fallback_key: str) -> dict:
    encrypted_vault = {}
    for key, val in secrets_dict.items():
        encrypted_vault[key] = double_encrypt(str(val), primary_key, fallback_key)
    return encrypted_vault


def main():
    parser = argparse.ArgumentParser(description="Encrypt secrets into secrets.enc via Double-Fernet.")
    parser.add_argument("--generate-keys", action="store_true", help="Generate new primary & fallback Fernet keys.")
    parser.add_argument("--input", type=str, help="Path to plaintext JSON secrets file to encrypt.")
    parser.add_argument("--output", type=str, default="secrets.enc", help="Output path for encrypted secrets.enc file.")
    parser.add_argument("--primary", type=str, help="PRIMARY encryption key.")
    parser.add_argument("--fallback", type=str, help="FALLBACK encryption key.")
    
    args = parser.parse_args()

    if args.generate_keys:
        generate_keys()
        if not args.input:
            return

    primary_key = args.primary or os.environ.get("ENCRYPTION_KEY_PRIMARY")
    fallback_key = args.fallback or os.environ.get("ENCRYPTION_KEY_FALLBACK")

    if not primary_key or not fallback_key:
        print("\n❌ Error: Both ENCRYPTION_KEY_PRIMARY and ENCRYPTION_KEY_FALLBACK must be specified or set in environment.")
        sys.exit(1)

    if not args.input:
        print("\n⚠️ No input JSON specified. Provide --input secrets.json to encrypt a secrets dictionary.")
        sys.exit(0)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Input file {input_path} not found.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        plaintext_secrets = json.load(f)

    encrypted_vault = encrypt_dict(plaintext_secrets, primary_key, fallback_key)

    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(encrypted_vault, f, indent=2)

    print(f"✅ Successfully encrypted {len(encrypted_vault)} secrets into '{output_path}'.")


if __name__ == "__main__":
    main()
