"""
Minimal local callback server for Snapchat Ads OAuth redirects.

Usage:
  python scripts/snap_ads_callback_server.py --port 8787 --exchange
"""

from __future__ import annotations

import argparse
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from modules.ads_api import SnapAdsAuthError, SnapAdsOAuthManager


class CallbackState:
    def __init__(self, expected_path: str, exchange: bool):
        self.expected_path = expected_path
        self.exchange = exchange
        self.done = False
        self.last_code: Optional[str] = None
        self.last_state: Optional[str] = None
        self.last_error: Optional[str] = None


def html_page(title: str, body: str) -> bytes:
    content = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family: Arial, sans-serif; margin: 40px;">
  <h2>{title}</h2>
  <p>{body}</p>
</body>
</html>
"""
    return content.encode("utf-8")


def make_handler(shared: CallbackState):
    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        server_version = "SnapAdsCallback/1.0"

        def log_message(self, format: str, *args):  # noqa: A003
            # Keep server output clean in terminal.
            return

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != shared.expected_path:
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    html_page(
                        "Not Found",
                        f"Expected callback path: {shared.expected_path}",
                    )
                )
                return

            query: Dict[str, list[str]] = parse_qs(parsed.query, keep_blank_values=True)
            code = (query.get("code") or [""])[0].strip() or None
            state = (query.get("state") or [""])[0].strip() or None
            error = (query.get("error") or [""])[0].strip() or None
            error_description = (query.get("error_description") or [""])[0].strip() or None

            shared.last_code = code
            shared.last_state = state
            shared.last_error = error or error_description

            print("")
            print("=== Snapchat OAuth Callback Received ===")
            print(f"path:  {parsed.path}")
            print(f"state: {state or '<empty>'}")
            if error:
                print(f"error: {error}")
            if error_description:
                print(f"error_description: {error_description}")
            if code:
                print(f"code:  {code}")
            else:
                print("code:  <missing>")

            if error:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    html_page(
                        "OAuth Failed",
                        f"{error}: {error_description or 'Unknown error'}",
                    )
                )
                shared.done = True
                return

            if not code:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_page("Missing Code", "No authorization code was provided."))
                shared.done = True
                return

            if not shared.exchange:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    html_page(
                        "OAuth Success",
                        "Authorization code received. You can return to terminal.",
                    )
                )
                shared.done = True
                return

            auth = SnapAdsOAuthManager()
            try:
                token = auth.exchange_code(code)
                print("exchange: success")
                print(f"token_store: {auth.token_store_path}")
                print(f"expires_at_utc: {token.expires_at_utc.isoformat()}")

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    html_page(
                        "OAuth + Exchange Success",
                        "Token exchange completed. You can return to terminal.",
                    )
                )
            except SnapAdsAuthError as exc:
                print(f"exchange: failed -> {exc}")
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    html_page(
                        "Exchange Failed",
                        str(exc),
                    )
                )
            finally:
                shared.done = True

    return OAuthCallbackHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Listen for Snapchat OAuth callback locally.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind local callback server.")
    parser.add_argument("--port", type=int, default=8787, help="Port to bind local callback server.")
    parser.add_argument("--path", default="/callback", help="Callback path, e.g. /callback")
    parser.add_argument(
        "--exchange",
        action="store_true",
        help="Exchange authorization code for token immediately after callback.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    callback_path = args.path.strip() or "/callback"
    if not callback_path.startswith("/"):
        callback_path = "/" + callback_path

    shared = CallbackState(expected_path=callback_path, exchange=args.exchange)
    handler = make_handler(shared)

    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.timeout = 1.0

    print(f"Listening callback at http://{args.host}:{args.port}{callback_path}")
    print("Press Ctrl+C to stop.")

    try:
        while not shared.done:
            server.handle_request()
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    finally:
        server.server_close()

    if shared.last_error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

