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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def safe_json(response: requests.Response) -> Dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {"message": response.text}


def request_ok(payload: Dict[str, Any]) -> bool:
    return str(payload.get("request_status", "")).strip().lower() in {"success", "ok"}


class ApiStepError(RuntimeError):
    pass


@dataclass
class LaunchResult:
    creative_id: Optional[str] = None
    campaign_id: Optional[str] = None
    ad_squad_id: Optional[str] = None
    ad_id: Optional[str] = None
    creative_preview_link: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "ad_squad_id": self.ad_squad_id,
            "ad_id": self.ad_id,
            "creative_preview_link": self.creative_preview_link,
        }


class SnapAdsLauncher:
    def __init__(self, api_base: str, token: str, timeout_seconds: int):
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.api_base}{path}"
        response = self._request_with_retry(
            method="POST",
            url=url,
            headers=self._headers(),
            json_payload=payload,
        )
        body = safe_json(response)
        if response.status_code >= 400 or not request_ok(body):
            extra = self._extract_subrequest_errors(body)
            if extra:
                extra = "\n" + extra
            raise ApiStepError(
                f"POST {path} failed ({response.status_code}):\n{json.dumps(body, indent=2, ensure_ascii=False)}{extra}"
            )
        return body

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.api_base}{path}"
        response = self._request_with_retry(
            method="GET",
            url=url,
            headers={"Authorization": f"Bearer {self.token}"},
        )
        body = safe_json(response)
        if response.status_code >= 400:
            raise ApiStepError(
                f"GET {path} failed ({response.status_code}):\n{json.dumps(body, indent=2, ensure_ascii=False)}"
            )
        return body

    def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        json_payload: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
    ) -> requests.Response:
        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt < max_attempts:
            attempt += 1
            try:
                if method.upper() == "POST":
                    return requests.post(
                        url,
                        headers=headers,
                        json=json_payload,
                        timeout=self.timeout_seconds,
                    )
                return requests.get(
                    url,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= max_attempts:
                    break
                time.sleep(1.2 * attempt)

        raise ApiStepError(f"{method} {url} failed after {max_attempts} attempts: {last_exc}")

    @staticmethod
    def _extract_subrequest_errors(payload: Dict[str, Any]) -> str:
        lines = []
        for key in ("creatives", "campaigns", "adsquads", "ads"):
            items = payload.get(key)
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                if str(item.get("sub_request_status", "")).upper() != "ERROR":
                    continue
                reason = item.get("sub_request_error_reason") or item.get("debug_message")
                if reason:
                    lines.append(f"{key}[{idx}] error: {reason}")
        return "\n".join(lines)

    @staticmethod
    def _parse_entity_id(payload: Dict[str, Any], key: str, nested_key: str) -> str:
        items = payload.get(key) or []
        if not items:
            raise ApiStepError(f"Response missing '{key}': {json.dumps(payload, ensure_ascii=False)}")
        first = items[0] or {}
        entity = first.get(nested_key) or {}
        entity_id = entity.get("id")
        if not entity_id:
            raise ApiStepError(
                f"Response missing '{nested_key}.id' in '{key}': {json.dumps(payload, ensure_ascii=False)}"
            )
        return str(entity_id)

    def create_creative(
        self,
        ad_account_id: str,
        media_id: str,
        name: str,
        headline: str,
        call_to_action: str,
        landing_url: str,
        brand_name: Optional[str],
        profile_id: str,
        status: str,
    ) -> str:
        creative: Dict[str, Any] = {
            "ad_account_id": ad_account_id,
            "name": name,
            "type": "WEB_VIEW",
            "shareable": True,
            "top_snap_media_id": media_id,
            "headline": headline,
            "call_to_action": call_to_action,
            "web_view_properties": {"url": landing_url},
            "status": status,
            "profile_properties": {"profile_id": profile_id},
        }
        if brand_name:
            creative["brand_name"] = brand_name

        payload = {"creatives": [creative]}
        body = self._post(f"/adaccounts/{ad_account_id}/creatives", payload)
        return self._parse_entity_id(body, key="creatives", nested_key="creative")

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
