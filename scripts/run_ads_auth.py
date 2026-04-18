"""
CLI for Snapchat Ads API OAuth login flow.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from modules.ads_api import SnapAdsAuthError, SnapAdsOAuthManager


def utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def safe_json(response: requests.Response) -> Dict:
    try:
        return response.json()
    except ValueError:
        return {"message": response.text}


def print_token_status(auth: SnapAdsOAuthManager) -> int:
    token = auth.load_token()
    if not token:
        print("No token found in local store.")
        print(f"Token store path: {auth.token_store_path}")
        return 1

    print("Token store:", auth.token_store_path)
    print("Now (UTC):", utc_now_iso())
    print("Expires at (UTC):", token.expires_at_utc.isoformat())
    print("Expiring soon:", "yes" if token.is_expiring_soon() else "no")
    print("Scope:", token.scope or "<empty>")
    print("Token type:", token.token_type)
    return 0


def cmd_auth_url(args: argparse.Namespace) -> int:
    auth = SnapAdsOAuthManager(scope=args.scope)
    url, state = auth.build_authorization_url(state=args.state)

    print("Open this URL in browser and approve access:")
    print(url)
    print("")
    print("state:", state)
    print("")
    print("After redirect, copy ?code=... and run:")
    print("python scripts/run_ads_auth.py exchange-code --code <AUTHORIZATION_CODE>")
    return 0


def cmd_exchange_code(args: argparse.Namespace) -> int:
    auth = SnapAdsOAuthManager()
    token = auth.exchange_code(args.code)

    print("Exchange code success.")
    print("Token saved to:", auth.token_store_path)
    print("Expires at (UTC):", token.expires_at_utc.isoformat())
    print("Scope:", token.scope or "<empty>")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    auth = SnapAdsOAuthManager()
    token = auth.refresh_access_token(refresh_token=args.refresh_token)

    print("Refresh token success.")
    print("Token saved to:", auth.token_store_path)
    print("Expires at (UTC):", token.expires_at_utc.isoformat())
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    auth = SnapAdsOAuthManager()
    return print_token_status(auth)


def cmd_verify(args: argparse.Namespace) -> int:
    auth = SnapAdsOAuthManager()
    access_token = auth.get_valid_access_token(auto_refresh=True)

    api_base = (os.getenv("SNAP_ADS_API_BASE", "https://adsapi.snapchat.com/v1") or "").rstrip("/")
    if not api_base:
        raise SnapAdsAuthError("SNAP_ADS_API_BASE is empty.")

    url = f"{api_base}/me/organizations"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"with_ad_accounts": "true"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=auth.timeout_seconds)
    except requests.RequestException as exc:
        raise SnapAdsAuthError(f"Cannot call verify endpoint: {exc}") from exc

    body = safe_json(response)
    if response.status_code >= 400:
        print("Verify failed.")
        print("Status:", response.status_code)
        print(json.dumps(body, indent=2, ensure_ascii=False))
        return 1

    print("Verify success.")
    print("Status:", response.status_code)
    print(json.dumps(body, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Snapchat Ads OAuth helper (auth-url, exchange-code, refresh, status, verify)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_auth = subparsers.add_parser("auth-url", help="Generate authorization URL.")
    p_auth.add_argument("--state", default=None, help="Optional OAuth state.")
    p_auth.add_argument("--scope", default=None, help="Optional OAuth scope override.")
    p_auth.set_defaults(handler=cmd_auth_url)

    p_exchange = subparsers.add_parser("exchange-code", help="Exchange authorization code for token.")
    p_exchange.add_argument("--code", required=True, help="Authorization code from redirect URL.")
    p_exchange.set_defaults(handler=cmd_exchange_code)

    p_refresh = subparsers.add_parser("refresh", help="Refresh access token.")
    p_refresh.add_argument("--refresh-token", default=None, help="Optional explicit refresh token.")
    p_refresh.set_defaults(handler=cmd_refresh)

    p_status = subparsers.add_parser("status", help="Show local token status.")
    p_status.set_defaults(handler=cmd_status)

    p_verify = subparsers.add_parser("verify", help="Call /me/organizations to verify OAuth token.")
    p_verify.set_defaults(handler=cmd_verify)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except SnapAdsAuthError as exc:
        print(f"OAuth error: {exc}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

