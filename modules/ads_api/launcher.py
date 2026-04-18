from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import requests

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
    def __init__(self, token: str, api_base: str = "https://adsapi.snapchat.com/v1", timeout_seconds: int = 30):
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
        print(f"DEBUG: POST {path} payload:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
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
        call_to_action: Optional[str] = None,
        landing_url: Optional[str] = None,
        brand_name: Optional[str] = None,
        profile_id: Optional[str] = None,
        status: str = "ACTIVE",
    ) -> str:
        creative: Dict[str, Any] = {
            "name": name,
            "type": "SNAP_AD",
            "shareable": True,
            "top_snap_media_id": media_id,
            "headline": headline,
            "brand_name": brand_name or "Snap Brand",
        }
        
        if profile_id:
            creative["profile_properties"] = {"profile_id": profile_id}
            
        if call_to_action:
            creative["call_to_action"] = call_to_action
            
        if landing_url:
            creative["web_view_properties"] = {"url": landing_url}

        payload = {
            "ad_account_id": ad_account_id,
            "creatives": [creative]
        }
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
        ad_account_id: str,
        campaign_id: str,
        name: str,
        start_time: str,
        status: str,
        country_code: str,
        bid_micro: int,
        daily_budget_micro: int,
        billing_event: str,
        optimization_goal: str,
    ) -> str:
        payload = {
            "adsquads": [
                {
                    "name": name,
                    "campaign_id": campaign_id,
                    "status": status,
                    "type": "SNAP_AD",
                    "billing_event": billing_event,
                    "optimization_goal": optimization_goal,
                    "bid_micro": bid_micro,
                    "daily_budget_micro": daily_budget_micro,
                    "start_time": start_time,
                    "targeting": {
                        "geographies": [
                            {"country_code": country_code}
                        ]
                    },
                }
            ]
        }
        body = self._post(f"/adaccounts/{ad_account_id}/adsquads", payload)
        return self._parse_entity_id(body, key="adsquads", nested_key="adsquad")

    def create_ad(
        self,
        ad_account_id: str,
        adsquad_id: str,
        creative_id: str,
        name: str,
        status: str,
    ) -> str:
        payload = {
            "ads": [
                {
                    "name": name,
                    "adsquad_id": adsquad_id,
                    "creative_id": creative_id,
                    "status": status,
                    "type": "SNAP_AD",
                }
            ]
        }
        body = self._post(f"/adaccounts/{ad_account_id}/ads", payload)
        return self._parse_entity_id(body, key="ads", nested_key="ad")
