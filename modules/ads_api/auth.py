"""
OAuth 2.0 helpers for Snapchat Marketing API login flow.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SnapAdsAuthError(RuntimeError):
    """Raised when OAuth actions fail."""


@dataclass
class SnapAdsToken:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    expires_at_utc: datetime
    scope: str = ""
    created_at_utc: datetime = field(default_factory=utc_now)
    raw: Dict[str, Any] = field(default_factory=dict)

    def is_expiring_soon(self, safety_seconds: int = 120) -> bool:
        return utc_now() + timedelta(seconds=safety_seconds) >= self.expires_at_utc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
            "created_at_utc": self.created_at_utc.isoformat(),
            "expires_at_utc": self.expires_at_utc.isoformat(),
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SnapAdsToken":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=int(data.get("expires_in", 0)),
            scope=data.get("scope", ""),
            created_at_utc=parse_utc(data["created_at_utc"]) if data.get("created_at_utc") else utc_now(),
            expires_at_utc=parse_utc(data["expires_at_utc"]),
            raw=data.get("raw", {}),
        )


class SnapAdsOAuthManager:
    """
    Handles Snapchat Ads OAuth authorization-code flow with local token storage.
    """

    DEFAULT_AUTH_BASE = "https://accounts.snapchat.com"
    DEFAULT_AUTHORIZE_PATH = "/login/oauth2/authorize"
    DEFAULT_TOKEN_PATH = "/login/oauth2/access_token"
    DEFAULT_SCOPE = "snapchat-marketing-api"
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_TOKEN_STORE_PATH = "sessions/snap_ads_oauth.json"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scope: Optional[str] = None,
        token_store_path: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.client_id = (client_id or os.getenv("SNAP_ADS_CLIENT_ID", "")).strip()
        self.client_secret = (client_secret or os.getenv("SNAP_ADS_CLIENT_SECRET", "")).strip()
        self.redirect_uri = (redirect_uri or os.getenv("SNAP_ADS_REDIRECT_URI", "")).strip()

        auth_base = (os.getenv("SNAP_ADS_AUTH_BASE", self.DEFAULT_AUTH_BASE) or self.DEFAULT_AUTH_BASE).strip()
        self.auth_base = auth_base.rstrip("/")
        authorize_path = (os.getenv("SNAP_ADS_AUTHORIZE_PATH", self.DEFAULT_AUTHORIZE_PATH) or self.DEFAULT_AUTHORIZE_PATH).strip()
        token_path = (os.getenv("SNAP_ADS_TOKEN_PATH", self.DEFAULT_TOKEN_PATH) or self.DEFAULT_TOKEN_PATH).strip()
        if not authorize_path.startswith("/"):
            authorize_path = "/" + authorize_path
        if not token_path.startswith("/"):
            token_path = "/" + token_path

        self.authorize_url = f"{self.auth_base}{authorize_path}"
        self.token_url = f"{self.auth_base}{token_path}"
        self.scope = (scope or os.getenv("SNAP_ADS_SCOPE", self.DEFAULT_SCOPE)).strip() or self.DEFAULT_SCOPE

        store_path = (token_store_path or os.getenv("SNAP_ADS_TOKEN_STORE_PATH", self.DEFAULT_TOKEN_STORE_PATH)).strip()
        self.token_store_path = Path(store_path)

        timeout_raw = timeout_seconds if timeout_seconds is not None else os.getenv("SNAP_ADS_TIMEOUT_SECONDS", str(self.DEFAULT_TIMEOUT_SECONDS))
        try:
            self.timeout_seconds = int(timeout_raw)
        except (TypeError, ValueError):
            self.timeout_seconds = self.DEFAULT_TIMEOUT_SECONDS

    def _require_client_config(self) -> None:
        missing = []
        if not self.client_id:
            missing.append("SNAP_ADS_CLIENT_ID")
        if not self.client_secret:
            missing.append("SNAP_ADS_CLIENT_SECRET")
        if not self.redirect_uri:
            missing.append("SNAP_ADS_REDIRECT_URI")
        if missing:
            raise SnapAdsAuthError(f"Missing required env keys: {', '.join(missing)}")

    def generate_state(self, length: int = 32) -> str:
        # token_urlsafe may produce longer strings than input bytes. That is fine for OAuth state.
        if length < 16:
            length = 16
        return secrets.token_urlsafe(length)

    def build_authorization_url(
        self,
        state: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> Tuple[str, str]:
        self._require_client_config()

        resolved_state = state or self.generate_state()
        resolved_scope = (scope or self.scope).strip()
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": resolved_scope,
            "state": resolved_state,
        }
        return f"{self.authorize_url}?{urlencode(params)}", resolved_state

    def exchange_code(self, code: str) -> SnapAdsToken:
        self._require_client_config()
        normalized_code = code.strip()
        if not normalized_code:
            raise SnapAdsAuthError("Authorization code is empty.")

        payload = {
            "grant_type": "authorization_code",
            "code": normalized_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }
        response_data = self._request_token(payload=payload)
        token = self._token_from_response(response_data)
        self.save_token(token)
        return token

    def refresh_access_token(self, refresh_token: Optional[str] = None) -> SnapAdsToken:
        self._require_client_config()
        resolved_refresh_token = (refresh_token or "").strip()
        if not resolved_refresh_token:
            existing = self.load_token()
            if not existing:
                raise SnapAdsAuthError("No existing token found. Run exchange-code first.")
            resolved_refresh_token = existing.refresh_token

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": resolved_refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response_data = self._request_token(payload=payload)

        # Some providers may not send refresh_token on refresh. Keep old one in that case.
        if "refresh_token" not in response_data:
            response_data["refresh_token"] = resolved_refresh_token

        token = self._token_from_response(response_data)
        self.save_token(token)
        return token

    def get_valid_token(self, auto_refresh: bool = True) -> SnapAdsToken:
        token = self.load_token()
        if not token:
            raise SnapAdsAuthError("Token store is empty. Run auth-url then exchange-code.")
        if token.is_expiring_soon() and auto_refresh:
            return self.refresh_access_token(token.refresh_token)
        return token

    def get_valid_access_token(self, auto_refresh: bool = True) -> str:
        return self.get_valid_token(auto_refresh=auto_refresh).access_token

    def save_token(self, token: SnapAdsToken) -> None:
        self.token_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_store_path.write_text(
            json.dumps(token.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_token(self) -> Optional[SnapAdsToken]:
        if not self.token_store_path.exists():
            return None
        raw_text = self.token_store_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return None
        data = json.loads(raw_text)
        return SnapAdsToken.from_dict(data)

    def _request_token(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = requests.post(
                self.token_url,
                data=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise SnapAdsAuthError(f"Cannot call token endpoint: {exc}") from exc

        parsed: Dict[str, Any]
        try:
            parsed = response.json()
        except ValueError:
            parsed = {"message": response.text}

        if response.status_code >= 400:
            raise SnapAdsAuthError(
                f"Token endpoint failed ({response.status_code}): {self._extract_error_text(parsed)}"
            )

        if "access_token" not in parsed:
            raise SnapAdsAuthError("Token response missing access_token.")
        return parsed

    @staticmethod
    def _extract_error_text(data: Dict[str, Any]) -> str:
        for key in ("error_description", "error", "message", "detail"):
            value = data.get(key)
            if value:
                return str(value)
        return "Unknown OAuth error."

    def _token_from_response(self, payload: Dict[str, Any]) -> SnapAdsToken:
        expires_in = int(payload.get("expires_in", 3600))
        created_at = utc_now()
        expires_at = created_at + timedelta(seconds=max(expires_in, 0))

        return SnapAdsToken(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload.get("refresh_token", "")),
            token_type=str(payload.get("token_type", "Bearer")),
            expires_in=expires_in,
            scope=str(payload.get("scope", self.scope)),
            created_at_utc=created_at,
            expires_at_utc=expires_at,
            raw=payload,
        )

