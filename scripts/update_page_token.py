#!/usr/bin/env python3
"""
update_page_token.py — Automated utility script to update FB_ACCESS_TOKEN in secrets.enc.

Usage:
  python scripts/update_page_token.py --token <YOUR_FACEBOOK_TOKEN>
"""

import sys
import json
import argparse
import requests
import datetime
from pathlib import Path

# Add script folder to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from secrets_manager import get_all_secrets, _get_keys
from encrypt_secrets import double_encrypt


def update_token(token_input: str):
    primary, fallback = _get_keys()
    
    # 1. Query Meta Graph API for Page Access Token if user provided a User Token
    print("🔍 Fetching Page Access Token from Meta Graph API...")
    resp = requests.get(f"https://graph.facebook.com/v19.0/me/accounts?access_token={token_input}", timeout=15)
    
    page_token = None
    page_name = None
    page_id = None
    
    if resp.status_code == 200:
        data = resp.json().get("data", [])
        if data:
            page_info = data[0]
            page_token = page_info.get("access_token")
            page_name = page_info.get("name")
            page_id = page_info.get("id")
            print(f"✅ Found Page: '{page_name}' (Page ID: {page_id})")
        else:
            print("⚠️ No pages returned from /me/accounts. Assuming input is already a direct Page Access Token.")
            page_token = token_input
    else:
        print(f"⚠️ Could not query /me/accounts ({resp.status_code}). Assuming input token is a direct Page Token.")
        page_token = token_input

    # 2. Debug Token Expiration
    debug_resp = requests.get(f"https://graph.facebook.com/v19.0/debug_token?input_token={page_token}&access_token={page_token}", timeout=15)
    if debug_resp.status_code == 200:
        debug_data = debug_resp.json().get("data", {})
        expires_at = debug_data.get("expires_at", 0)
        is_valid = debug_data.get("is_valid", False)
        print(f"📊 Token Validation Status: Valid={is_valid}")
        if expires_at == 0:
            print("🎉 Token Expiration: NEVER EXPIRES (Permanent Page Access Token)!")
        else:
            exp_date = datetime.datetime.fromtimestamp(expires_at, datetime.timezone.utc)
            print(f"⏰ Token Expiration Date: {exp_date} UTC")

    # 3. Decrypt existing vault to preserve all other credentials
    print("🔐 Decrypting existing secrets vault...")
    try:
        secrets_dict = get_all_secrets()
    except Exception as e:
        print(f"❌ Failed to decrypt existing secrets.enc: {e}")
        sys.exit(1)

    secrets_dict["FB_ACCESS_TOKEN"] = page_token
    if page_id:
        secrets_dict["FB_PAGE_ID"] = page_id

    # 4. Re-encrypt vault using Double-Fernet and write back to secrets.enc
    encrypted_vault = {}
    for k, v in secrets_dict.items():
        encrypted_vault[k] = double_encrypt(v, primary.decode("utf-8"), fallback.decode("utf-8"))

    vault_path = Path(__file__).resolve().parent.parent / "secrets.enc"
    with open(vault_path, "w", encoding="utf-8") as f:
        json.dump(encrypted_vault, f, indent=2)

    print(f"🚀 Successfully updated FB_ACCESS_TOKEN inside '{vault_path}'!")


def main():
    parser = argparse.ArgumentParser(description="Update Facebook Page Access Token in secrets.enc")
    parser.add_argument("--token", required=True, help="Facebook User Access Token or Page Access Token")
    args = parser.parse_args()
    update_token(args.token)


if __name__ == "__main__":
    main()
