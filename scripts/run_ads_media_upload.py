"""
Create and upload Snapchat Ads media (video-first workflow).

Usage:
  python scripts/run_ads_media_upload.py --file uploads/video/sample-5s.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from modules.ads_api import SnapAdsAuthError, SnapAdsOAuthManager


def safe_json(response: requests.Response) -> Dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {"message": response.text}


def request_status_ok(value: Any) -> bool:
    return str(value or "").strip().lower() in {"success", "ok"}


def parse_create_media_response(payload: Dict[str, Any]) -> Tuple[str, str]:
    media_items = payload.get("media") or []
    if not media_items:
        raise RuntimeError(f"Create media response missing media list: {json.dumps(payload, ensure_ascii=False)}")

    first = media_items[0] or {}
    media_obj = first.get("media") or {}
    media_id = media_obj.get("id")
    if not media_id:
        raise RuntimeError(f"Create media response missing media id: {json.dumps(payload, ensure_ascii=False)}")

    media_status = media_obj.get("media_status") or "<unknown>"
    return str(media_id), str(media_status)


def parse_upload_response(payload: Dict[str, Any]) -> str:
    result = payload.get("result") or {}
    media_status = result.get("media_status")
    if media_status:
        return str(media_status)

    media_items = payload.get("media") or []
    if media_items:
        first = media_items[0] or {}
        media_obj = first.get("media") or {}
        media_status = media_obj.get("media_status")
        if media_status:
            return str(media_status)
    return "<unknown>"


def check_file(video_path: Path) -> None:
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if not video_path.is_file():
        raise FileNotFoundError(f"Not a file: {video_path}")
    if video_path.suffix.lower() not in {".mp4", ".mov"}:
        raise ValueError("Video file must be .mp4 or .mov")


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and upload Snapchat Ads media.")
    parser.add_argument(
        "--file",
        required=False,
        default=os.getenv("TEST_VIDEO_FILE", "uploads/video/sample-5s.mp4"),
        help="Path to video file (.mp4/.mov).",
    )
    parser.add_argument("--name", required=False, default=None, help="Media display name.")
    parser.add_argument(
        "--ad-account-id",
        required=False,
        default=os.getenv("SNAP_ADS_AD_ACCOUNT_ID", "").strip(),
        help="Target Snapchat ad account ID.",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        help="Poll media status after upload until READY or timeout.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=120,
        help="Polling timeout seconds when --poll is enabled.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Polling interval in seconds when --poll is enabled.",
    )
    return parser


def get_media_status(
    api_base: str,
    media_id: str,
    token: str,
    timeout: int,
) -> Tuple[int, Dict[str, Any], str]:
    url = f"{api_base}/media/{media_id}"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    body = safe_json(response)

    status = "<unknown>"
    if isinstance(body, dict):
        media_payload = body.get("media")
        if isinstance(media_payload, list) and media_payload:
            first = media_payload[0] or {}
            media_obj = first.get("media") or {}
            if isinstance(media_obj, dict):
                status = str(media_obj.get("media_status") or status)
        elif isinstance(media_payload, dict):
            status = str(media_payload.get("media_status") or status)
        else:
            result = body.get("result") or {}
            if isinstance(result, dict):
                status = str(result.get("media_status") or status)

    return response.status_code, body, status


def main() -> int:
    parser = get_parser()
    args = parser.parse_args()

    video_path = Path(args.file).expanduser()
    check_file(video_path)

    ad_account_id = str(args.ad_account_id or "").strip()
    if not ad_account_id:
        print("Missing ad account ID. Set SNAP_ADS_AD_ACCOUNT_ID or pass --ad-account-id.")
        return 1

    api_base = (os.getenv("SNAP_ADS_API_BASE", "https://adsapi.snapchat.com/v1") or "").rstrip("/")
    if not api_base:
        print("SNAP_ADS_API_BASE is empty.")
        return 1

    auth = SnapAdsOAuthManager()
    try:
        access_token = auth.get_valid_access_token(auto_refresh=True)
    except SnapAdsAuthError as exc:
        print(f"OAuth error: {exc}")
        return 1

    media_name = args.name or f"video-{video_path.stem}"
    create_url = f"{api_base}/adaccounts/{ad_account_id}/media"
    create_payload = {
        "media": [
            {
                "name": media_name,
                "type": "VIDEO",
                "ad_account_id": ad_account_id,
            }
        ]
    }

    print("Step 1/3: create media object...")
    create_resp = requests.post(
        create_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=create_payload,
        timeout=auth.timeout_seconds,
    )
    create_body = safe_json(create_resp)
    if create_resp.status_code >= 400 or not request_status_ok(create_body.get("request_status")):
        print("Create media failed.")
        print("Status:", create_resp.status_code)
        print(json.dumps(create_body, indent=2, ensure_ascii=False))
        return 1

    media_id, media_status = parse_create_media_response(create_body)
    print("Create media success.")
    print("media_id:", media_id)
    print("media_status:", media_status)

    print("Step 2/3: upload video file...")
    upload_url = f"{api_base}/media/{media_id}/upload"
    with video_path.open("rb") as fh:
        upload_resp = requests.post(
            upload_url,
            headers={"Authorization": f"Bearer {access_token}"},
            files={"file": (video_path.name, fh, "video/mp4")},
            timeout=auth.timeout_seconds,
        )
    upload_body = safe_json(upload_resp)
    if upload_resp.status_code >= 400 or not request_status_ok(upload_body.get("request_status")):
        print("Upload failed.")
        print("Status:", upload_resp.status_code)
        print(json.dumps(upload_body, indent=2, ensure_ascii=False))
        if upload_body.get("error_code") == "E2601":
            print("")
            print("Hint: media does not meet creative requirements.")
            print("Try a vertical 1080x1920 MP4 (H264/AAC), short duration, and <= 32MB.")
        return 1

    upload_media_status = parse_upload_response(upload_body)
    print("Upload success.")
    print("media_status:", upload_media_status)

    print("Step 3/3: verify media status...")
    status_code, status_body, fetched_status = get_media_status(
        api_base=api_base,
        media_id=media_id,
        token=access_token,
        timeout=auth.timeout_seconds,
    )
    if status_code >= 400:
        print("Fetch media status failed.")
        print("Status:", status_code)
        print(json.dumps(status_body, indent=2, ensure_ascii=False))
    else:
        print("Fetch media status success.")
        print("media_status:", fetched_status)
        print("media_id:", media_id)

    if args.poll:
        import time

        deadline = time.time() + max(1, int(args.poll_seconds))
        interval = max(1, int(args.poll_interval))
        latest = fetched_status

        while time.time() < deadline and latest != "READY":
            time.sleep(interval)
            status_code, status_body, latest = get_media_status(
                api_base=api_base,
                media_id=media_id,
                token=access_token,
                timeout=auth.timeout_seconds,
            )
            if status_code >= 400:
                print("Polling failed.")
                print("Status:", status_code)
                print(json.dumps(status_body, indent=2, ensure_ascii=False))
                return 1
            print("poll media_status:", latest)

        if latest == "READY":
            print("Media READY.")
            return 0

        print("Polling timeout before READY.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
