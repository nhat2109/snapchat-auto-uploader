import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from modules.core.browser import BrowserManager
from modules.automation.snapchat import SnapchatAutomation
from modules.utils.logger import PipelineLogger


async def main() -> int:
    load_dotenv()

    username = os.getenv("SNAPCHAT_USERNAME", "").strip()
    password = os.getenv("SNAPCHAT_PASSWORD", "").strip()
    video_path = os.getenv("TEST_VIDEO_FILE", "uploads/video/sample-5s.mp4").strip()
    session_state = os.getenv("SNAPCHAT_SESSION_STATE", "sessions/snapchat_state.json").strip()
    force_login = os.getenv("SNAPCHAT_FORCE_LOGIN", "false").strip().lower() == "true"
    session_only = os.getenv("SNAPCHAT_SESSION_ONLY", "false").strip().lower() == "true"

    if not username or not password:
        print("ERROR: Missing SNAPCHAT_USERNAME or SNAPCHAT_PASSWORD in .env")
        return 2

    if not video_path:
        print("ERROR: Missing TEST_VIDEO_FILE")
        return 2

    video = Path(video_path)
    if not video.exists():
        print(f"ERROR: Video file not found: {video}")
        return 2

    browser = BrowserManager(headless=False, screenshots_dir="screenshots")
    plog = PipelineLogger()
    snap = SnapchatAutomation(browser, plog)

    timeout_sec = int(os.getenv("UPLOAD_TEST_TIMEOUT", "300"))

    print(f"TEST_VIDEO={video}", flush=True)
    print(f"TEST_TIMEOUT={timeout_sec}", flush=True)
    print(f"SESSION_STATE={session_state}", flush=True)
    print(f"FORCE_LOGIN={force_login}", flush=True)
    print(f"SESSION_ONLY={session_only}", flush=True)
    await browser.start()
    try:
        try:
            result = await asyncio.wait_for(
                snap.run(
                    username=username,
                    password=password,
                    video_path=str(video),
                    music_title=os.getenv("DEFAULT_MUSIC_TITLE", "").strip(),
                    artist=os.getenv("DEFAULT_ARTIST_NAME", "").strip(),
                    title="E2E Upload Test",
                    description="Automated upload validation",
                    tags="test,automation",
                    account_id=None,
                    headless=False,
                    session_state_path=session_state,
                    force_login=force_login,
                    session_only=session_only,
                ),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            screenshot = Path("screenshots") / "snapchat_upload_test_timeout.png"
            try:
                if snap._page:
                    await snap._page.screenshot(path=str(screenshot), full_page=True)
            except Exception:
                pass

            print("UPLOAD_SUCCESS=False", flush=True)
            print("UPLOAD_MESSAGE=Timeout while waiting for upload flow", flush=True)
            print("UPLOAD_POST_URL=None", flush=True)
            print(f"SCREENSHOT={screenshot}", flush=True)
            return 3

        print(f"UPLOAD_SUCCESS={result.get('success')}", flush=True)
        print(f"UPLOAD_MESSAGE={result.get('message')}", flush=True)
        print(f"UPLOAD_POST_URL={result.get('post_url')}", flush=True)

        if not result.get("success") and "Đăng nhập Snapchat thất bại" in str(result.get("message")):
            if not Path(session_state).exists():
                print("HINT=RUN bootstrap_snapchat_session.py TO SAVE SESSION FIRST", flush=True)

        if not result.get("success") and "session-only mode" in str(result.get("message")).lower():
            print("HINT=TURN_OFF_SNAPCHAT_SESSION_ONLY_OR_REFRESH_SESSION", flush=True)

        return 0 if result.get("success") else 1
    finally:
        await browser.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
