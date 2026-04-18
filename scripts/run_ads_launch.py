"""
Create Snapchat Ads entities in sequence:
creative -> campaign -> ad squad -> ad

Usage:
  python scripts/run_ads_launch.py --media-id <MEDIA_ID>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import time

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from modules.ads_api import SnapAdsAuthError, SnapAdsOAuthManager
from modules.ads_api.launcher import SnapAdsLauncher, ApiStepError, LaunchResult


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# The SnapAdsLauncher class has been moved to modules/ads_api/launcher.py

    def create_campaign(
        self,
        ad_account_id: str,
        name: str,
        start_time: str,
        status: str,
        objective_v2_type: str,
    ) -> str:
        payload = {
            "campaigns": [
                {
                    "name": name,
                    "ad_account_id": ad_account_id,
                    "status": status,
                    "start_time": start_time,
                    "buy_model": "AUCTION",
                    "objective_v2_properties": {
                        "objective_v2_type": objective_v2_type,
                    },
                }
            ]
        }
        body = self._post(f"/adaccounts/{ad_account_id}/campaigns", payload)
        return self._parse_entity_id(body, key="campaigns", nested_key="campaign")

    def create_adsquad(
        self,
        campaign_id: str,
        name: str,
        start_time: str,
        status: str,
        country_code: str,
        bid_micro: int,
        daily_budget_micro: int,
    ) -> str:
        payload = {
            "adsquads": [
                {
                    "name": name,
                    "campaign_id": campaign_id,
                    "type": "SNAP_ADS",
                    "status": status,
                    "placement_v2": {"config": "AUTOMATIC"},
                    "billing_event": "IMPRESSION",
                    "optimization_goal": "IMPRESSIONS",
                    "bid_strategy": "LOWEST_COST_WITH_MAX_BID",
                    "bid_micro": int(bid_micro),
                    "daily_budget_micro": int(daily_budget_micro),
                    "delivery_constraint": "DAILY_BUDGET",
                    "targeting": {"geos": [{"country_code": country_code.lower()}]},
                    "start_time": start_time,
                }
            ]
        }
        body = self._post(f"/campaigns/{campaign_id}/adsquads", payload)
        return self._parse_entity_id(body, key="adsquads", nested_key="adsquad")

    def create_ad(
        self,
        ad_squad_id: str,
        creative_id: str,
        name: str,
        status: str,
    ) -> str:
        payload = {
            "ads": [
                {
                    "name": name,
                    "ad_squad_id": ad_squad_id,
                    "creative_id": creative_id,
                    "type": "SNAP_AD",
                    "status": status,
                }
            ]
        }
        body = self._post(f"/adsquads/{ad_squad_id}/ads", payload)
        return self._parse_entity_id(body, key="ads", nested_key="ad")

    def get_creative_preview_link(self, creative_id: str) -> Optional[str]:
        try:
            body = self._get(f"/creatives/{creative_id}/creative_preview")
        except ApiStepError:
            return None

        # API usually returns creative_id/expires_at/signature or direct creative_preview_link.
        direct = body.get("creative_preview_link")
        if direct:
            return str(direct)

        cid = body.get("creative_id")
        expires_at = body.get("expires_at")
        signature = body.get("signature")
        if cid and expires_at and signature:
            return (
                "https://ad-preview.snapchat.com/?"
                f"creative_id={cid}&expires_at={expires_at}&signature={signature}"
            )
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create Snapchat Ads entities: creative -> campaign -> ad squad -> ad."
    )
    parser.add_argument("--media-id", required=True, help="Uploaded media ID with status READY.")
    parser.add_argument(
        "--ad-account-id",
        default=os.getenv("SNAP_ADS_AD_ACCOUNT_ID", "").strip(),
        help="Snap ad account ID (defaults to SNAP_ADS_AD_ACCOUNT_ID).",
    )
    parser.add_argument(
        "--country-code",
        default="us",
        help="Target country code for ad squad targeting. Default: us.",
    )
    parser.add_argument(
        "--headline",
        default="Try this now",
        help="Creative headline.",
    )
    parser.add_argument(
        "--call-to-action",
        default="LEARN_MORE",
        help="Creative CTA. Default: LEARN_MORE",
    )
    parser.add_argument(
        "--landing-url",
        default="https://example.com",
        help="Creative landing URL for WEB_VIEW creative.",
    )
    parser.add_argument(
        "--brand-name",
        default="SNAPP_APP",
        help="Creative brand name.",
    )
    parser.add_argument(
        "--profile-id",
        default=os.getenv("SNAP_ADS_PROFILE_ID", "").strip(),
        help="Public profile id for profile_properties (required).",
    )
    parser.add_argument(
        "--objective",
        default="AWARENESS_AND_ENGAGEMENT",
        help="Campaign objective_v2_type. Default: AWARENESS_AND_ENGAGEMENT",
    )
    parser.add_argument(
        "--bid-micro",
        type=int,
        default=1_000_000,
        help="Ad squad bid in micro currency. Default: 1000000 ($1).",
    )
    parser.add_argument(
        "--daily-budget-micro",
        type=int,
        default=50_000_000,
        help="Ad squad daily budget in micro currency. Default: 50000000 ($50).",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        help="Create entities with status ACTIVE. Default is PAUSED for safety.",
    )
    parser.add_argument(
        "--start-delay-minutes",
        type=int,
        default=5,
        help="Start time offset from now in minutes. Default: 5.",
    )
    parser.add_argument(
        "--name-prefix",
        default="Auto API",
        help="Prefix used for creative/campaign/adsquad/ad names.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    ad_account_id = str(args.ad_account_id or "").strip()
    if not ad_account_id:
        print("Missing ad account ID. Set SNAP_ADS_AD_ACCOUNT_ID or pass --ad-account-id.")
        return 1

    api_base = (os.getenv("SNAP_ADS_API_BASE", "https://adsapi.snapchat.com/v1") or "").strip()
    if not api_base:
        print("SNAP_ADS_API_BASE is empty.")
        return 1

    profile_id = str(args.profile_id or "").strip()
    if not profile_id:
        print("Missing public profile ID.")
        print("Set SNAP_ADS_PROFILE_ID in .env or pass --profile-id.")
        print("Snap now requires profile_properties.profile_id when creating creatives.")
        return 1

    auth = SnapAdsOAuthManager()
    try:
        access_token = auth.get_valid_access_token(auto_refresh=True)
    except SnapAdsAuthError as exc:
        print(f"OAuth error: {exc}")
        return 1

    status = "ACTIVE" if args.active else "PAUSED"
    now = utc_now()
    start_time = to_iso_z(now + timedelta(minutes=max(0, int(args.start_delay_minutes))))
    stamp = now.strftime("%Y%m%d-%H%M%S")
    prefix = args.name_prefix.strip() or "Auto API"

    creative_name = f"{prefix} Creative {stamp}"
    campaign_name = f"{prefix} Campaign {stamp}"
    adsquad_name = f"{prefix} AdSquad {stamp}"
    ad_name = f"{prefix} Ad {stamp}"

    launcher = SnapAdsLauncher(
        api_base=api_base,
        token=access_token,
        timeout_seconds=auth.timeout_seconds,
    )
    result = LaunchResult()

    print("Step 1/4: create creative...")
    try:
        result.creative_id = launcher.create_creative(
            ad_account_id=ad_account_id,
            media_id=args.media_id.strip(),
            name=creative_name,
            headline=args.headline.strip(),
            call_to_action=args.call_to_action.strip(),
            landing_url=args.landing_url.strip(),
            brand_name=args.brand_name.strip() if args.brand_name else None,
            profile_id=profile_id,
            status=status,
        )
        print("Creative created:", result.creative_id)

        print("Step 2/4: create campaign...")
        result.campaign_id = launcher.create_campaign(
            ad_account_id=ad_account_id,
            name=campaign_name,
            start_time=start_time,
            status=status,
            objective_v2_type=args.objective.strip(),
        )
        print("Campaign created:", result.campaign_id)

        print("Step 3/4: create ad squad...")
        result.ad_squad_id = launcher.create_adsquad(
            campaign_id=result.campaign_id,
            name=adsquad_name,
            start_time=start_time,
            status=status,
            country_code=args.country_code.strip(),
            bid_micro=args.bid_micro,
            daily_budget_micro=args.daily_budget_micro,
        )
        print("Ad squad created:", result.ad_squad_id)

        print("Step 4/4: create ad...")
        result.ad_id = launcher.create_ad(
            ad_squad_id=result.ad_squad_id,
            creative_id=result.creative_id,
            name=ad_name,
            status=status,
        )
        print("Ad created:", result.ad_id)

        result.creative_preview_link = launcher.get_creative_preview_link(result.creative_id)
        if result.creative_preview_link:
            print("Creative preview:", result.creative_preview_link)

        print("")
        print("Launch success:")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0

    except ApiStepError as exc:
        print("Launch failed.")
        print(str(exc))
        print("")
        print("Partial result:")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
