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
    session_state = os.getenv("SNAPCHAT_SESSION_STATE", "sessions/snapchat_state.json").strip()
    allow_manual_checkpoint = os.getenv("SNAPCHAT_ALLOW_MANUAL_CHECKPOINT", "false").strip().lower() == "true"
    manual_wait_timeout = int(os.getenv("SNAPCHAT_MANUAL_WAIT_TIMEOUT", "300"))
    base_login_timeout = int(os.getenv("SNAPCHAT_VISIBLE_LOGIN_TIMEOUT", "120"))

    # Nếu bật manual checkpoint, tăng timeout để không bị cắt ngang khi user đang xác minh.
    login_timeout = max(base_login_timeout, manual_wait_timeout + 90) if allow_manual_checkpoint else base_login_timeout

    if not username or not password:
        print("ERROR: Missing SNAPCHAT_USERNAME or SNAPCHAT_PASSWORD in .env")
        return 2

    browser = BrowserManager(headless=False, screenshots_dir="screenshots")
    plog = PipelineLogger()
    snap = SnapchatAutomation(browser, plog)

    await browser.start()
    try:
        session_file = Path(session_state)
        storage_state = str(session_file) if session_file.exists() else None

        ctx = await browser.new_context(account_id=9001, storage_state=storage_state)
        page = await ctx.new_page()
        snap._page = page
        snap._session_state_path = str(session_file)

        print("CHECK=LOGIN_START", flush=True)
        print(f"SESSION_STATE={session_file}", flush=True)

        session_ok = await snap._is_session_logged_in()
        if session_ok:
            login_ok = True
            print("SESSION_VALID=True", flush=True)
            print("LOGIN_OK=True", flush=True)
        else:
            print("SESSION_VALID=False", flush=True)
            print(f"LOGIN_TIMEOUT={login_timeout}", flush=True)
            login_ok = await asyncio.wait_for(snap._login(username, password), timeout=login_timeout)
            print(f"LOGIN_OK={login_ok}", flush=True)

        checkpoint = await snap._detect_login_checkpoint()
        print(f"CHECKPOINT={checkpoint or 'NONE'}", flush=True)
        print(f"FINAL_URL={page.url}", flush=True)

        screenshot = Path("screenshots") / "snapchat_visible_login_result.png"
        await page.screenshot(path=str(screenshot), full_page=True)
        print(f"SCREENSHOT={screenshot}", flush=True)

        if login_ok:
            print("SNAPCHAT_VISIBLE_CHECK=CONNECTED")
            return 0

        print("SNAPCHAT_VISIBLE_CHECK=NOT_CONNECTED")
        return 1

    except asyncio.TimeoutError:
        screenshot = Path("screenshots") / "snapchat_visible_login_timeout.png"
        try:
            if snap._page:
                await snap._page.screenshot(path=str(screenshot), full_page=True)
        except Exception:
            pass
        print("SNAPCHAT_VISIBLE_CHECK=TIMEOUT")
        print(f"SCREENSHOT={screenshot}")
        return 3
    finally:
        await browser.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
