#!/usr/bin/env python3
"""
fb_publisher.py — Facebook Page Feed & Reels Meta Graph API publisher module.

Zero hardcoded Page IDs or Access Tokens in code; credentials are retrieved dynamically
from double-encrypted secrets vault via secrets_manager.py.
Includes SecretSanitizer protection to ensure tokens are never logged.
"""

import os
import logging
import requests
from secrets_manager import get_secret

logger = logging.getLogger(__name__)


def get_valid_access_token() -> str:
    """
    Retrieve FB_ACCESS_TOKEN and attempt auto-refresh using FB_APP_ID & FB_APP_SECRET
    via Meta Graph API fb_exchange_token endpoint if configured.
    """
    token = get_secret("FB_ACCESS_TOKEN")
    app_id = get_secret("FB_APP_ID", default="")
    app_secret = get_secret("FB_APP_SECRET", default="")

    if app_id and app_secret:
        try:
            exchange_url = "https://graph.facebook.com/v19.0/oauth/access_token"
            resp = requests.get(exchange_url, params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": token,
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                new_token = data.get("access_token")
                if new_token:
                    logger.info("Successfully refreshed long-lived Facebook access token via Meta Graph API.")
                    return new_token
        except Exception as e:
            logger.warning("Token auto-exchange attempt skipped/failed: %s", str(e))
            
    return token


def _handle_fb_error(error_payload: str, context: str):
    """Detect expired OAuth sessions or invalid access tokens and output step-by-step renewal guidance."""
    if "Session has expired" in error_payload or "code\": 190" in error_payload or "OAuthException" in error_payload or "190" in str(error_payload):
        err_msg = (
            f"Facebook Access Token has expired during '{context}' (OAuthException code 190).\n"
            "─────────────────────────────────────────────────────────────────────────────\n"
            "Action Required to renew Facebook Access Token:\n"
            " 1. Go to Graph API Explorer (https://developers.facebook.com/tools/explorer/)\n"
            " 2. Select your App & Facebook Page.\n"
            " 3. Ensure permissions: pages_manage_posts, pages_read_engagement, publish_video.\n"
            " 4. Generate User Token -> Access Token Tool -> Exchange for 60-day Long-Lived User Token.\n"
            " 5. Query: GET /v19.0/me/accounts?access_token=<LONG_LIVED_USER_TOKEN> to get your Never-Expiring Page Token.\n"
            " 6. Update secrets.enc: python scripts/encrypt_secrets.py --input secrets.json --output secrets.enc\n"
            "─────────────────────────────────────────────────────────────────────────────"
        )
        logger.error(err_msg)
        raise RuntimeError(err_msg)


def publish_feed_photo(image_path: str, caption: str) -> dict:
    """Publish a photo post to Facebook Page Feed via Meta Graph API."""
    page_id = get_secret("FB_PAGE_ID")
    access_token = get_valid_access_token()
    
    url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
    logger.info("Publishing image post to Facebook Page ID %s...", page_id)
    
    with open(image_path, "rb") as image_file:
        payload = {
            "caption": caption,
            "access_token": access_token
        }
        files = {"source": image_file}
        response = requests.post(url, data=payload, files=files, timeout=60)
        
    if response.status_code != 200:
        logger.error("Failed to publish photo post: %s", response.text)
        _handle_fb_error(response.text, "Publish Feed Photo")
        response.raise_for_status()
        
    res_data = response.json()
    logger.info("Successfully published Facebook Feed Photo Post! Post ID: %s", res_data.get("id", "N/A"))
    return res_data


def publish_facebook_reel(video_path: str, caption: str) -> dict:
    """Publish a vertical video Reel to Facebook Page via 3-step Reels Graph API."""
    page_id = get_secret("FB_PAGE_ID")
    access_token = get_valid_access_token()
    
    logger.info("Publishing Reel video to Facebook Page ID %s...", page_id)
    
    # Phase 1: Start Upload Session
    init_url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels"
    init_res = requests.post(init_url, data={
        "upload_phase": "start",
        "access_token": access_token
    }, timeout=30).json()
    
    video_id = init_res.get("video_id")
    upload_url = init_res.get("upload_url")
    
    if not upload_url or not video_id:
        logger.error("Failed to initialize Facebook Reel upload session: %s", init_res)
        _handle_fb_error(str(init_res), "Init Reel Upload Session")
        raise RuntimeError(f"Reel upload initialization failed: {init_res}")
        
    logger.info("Reel upload session initialized. Video ID: %s", video_id)

    # Phase 2: Upload Video File Bytes
    with open(video_path, "rb") as f:
        video_data = f.read()

    upload_res = requests.post(upload_url, headers={
        "Authorization": f"OAuth {access_token}",
        "offset": "0",
        "file_size": str(len(video_data))
    }, data=video_data, timeout=120)

    if upload_res.status_code not in (200, 201):
        logger.error("Failed to upload Reel video binary payload: %s", upload_res.text)
        _handle_fb_error(upload_res.text, "Upload Reel Video Binary")
        upload_res.raise_for_status()

    # Phase 3: Finish & Publish Reel
    finish_url = f"https://graph.facebook.com/v19.0/{page_id}/video_reels"
    finish_res = requests.post(finish_url, data={
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "description": caption,
        "access_token": access_token
    }, timeout=30).json()

    if "success" in finish_res and not finish_res.get("success"):
        logger.error("Failed to finalize Reel publication: %s", finish_res)
        _handle_fb_error(str(finish_res), "Finalize Reel Publication")
        raise RuntimeError(f"Reel publication failed: {finish_res}")

    logger.info("Successfully published Facebook Reel! Details: %s", finish_res)
    return finish_res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("FB publisher module loaded.")
