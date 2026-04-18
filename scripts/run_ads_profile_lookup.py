"""
Lookup Snapchat Public Profile IDs shared to an ad account.

Requires OAuth token with profile scope.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

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
        return {"raw": response.text}


def collect_profile_like_ids(node: Any, out: Set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() in {"profile_id", "public_profile_id"} and isinstance(value, str):
                out.add(value)
            if key.lower() == "id" and isinstance(value, str):
                # Keep candidates from objects that look profile-related.
                maybe_profile = any(k.lower().find("profile") >= 0 for k in node.keys())
                if maybe_profile:
                    out.add(value)
            collect_profile_like_ids(value, out)
    elif isinstance(node, list):
        for item in node:
            collect_profile_like_ids(item, out)


def call_endpoint(url: str, token: str, timeout: int) -> tuple[int, Dict[str, Any]]:
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    return resp.status_code, safe_json(resp)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lookup shared public profile IDs for ads.")
    parser.add_argument(
        "--ad-account-id",
        default=os.getenv("SNAP_ADS_AD_ACCOUNT_ID", "").strip(),
        help="Snap ad account ID (defaults to SNAP_ADS_AD_ACCOUNT_ID).",
    )
    parser.add_argument(
        "--organization-id",
        default=os.getenv("SNAP_ADS_ORGANIZATION_ID", "").strip(),
        help="Snap organization ID (defaults to SNAP_ADS_ORGANIZATION_ID).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ad_account_id = str(args.ad_account_id or "").strip()
    organization_id = str(args.organization_id or "").strip()

    if not ad_account_id and not organization_id:
        print("Missing IDs. Set SNAP_ADS_AD_ACCOUNT_ID or SNAP_ADS_ORGANIZATION_ID in .env.")
        return 1

    auth = SnapAdsOAuthManager()
    try:
        token = auth.get_valid_access_token(auto_refresh=True)
    except SnapAdsAuthError as exc:
        print(f"OAuth error: {exc}")
        return 1

    timeout = auth.timeout_seconds
    endpoints: List[str] = []
    if ad_account_id:
        endpoints.append(
            f"https://businessapi.snapchat.com/v1/adaccounts/{ad_account_id}/sharing_policies?shared_resource_types=public_profiles"
        )
    if organization_id:
        endpoints.append(
            f"https://businessapi.snapchat.com/v1/organizations/{organization_id}/sharing_policies?shared_resource_types=public_profiles"
        )
        # Added direct public profiles list endpoint
        endpoints.append(
            f"https://businessapi.snapchat.com/v1/organizations/{organization_id}/public_profiles"
        )

    found_ids: Set[str] = set()
    had_success = False
    had_unauthorized = False

    for url in endpoints:
        print(f"Calling: {url}")
        status, body = call_endpoint(url=url, token=token, timeout=timeout)
        print("Status:", status)
        if status == 403:
            had_unauthorized = True
            print("Body:", body)
            print("")
            continue
        if status >= 400:
            print(json.dumps(body, indent=2, ensure_ascii=False))
            print("")
            continue
        had_success = True
        print(json.dumps(body, indent=2, ensure_ascii=False))
        print("")
        collect_profile_like_ids(body, found_ids)

    if found_ids:
        print("Candidate profile IDs:")
        for pid in sorted(found_ids):
            print("-", pid)
        print("")
        print("Set one in .env:")
        print("SNAP_ADS_PROFILE_ID=<PROFILE_ID>")
        return 0

    if had_unauthorized:
        print("Unauthorized for Business API profile lookup.")
        print("Re-auth with profile scope, then run this command again:")
        print(
            'python scripts/run_ads_auth.py auth-url --scope "snapchat-marketing-api snapchat-profile-api"'
        )
        print("Then exchange the new code to update token.")
        return 1

    if had_success:
        print("No profile IDs found from sharing policies response.")
        print("Make sure your Public Profile is created and shared to the ad account.")
        return 1

    print("No successful endpoint response.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

