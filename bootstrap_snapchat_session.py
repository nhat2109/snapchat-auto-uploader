import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from modules.core.browser import BrowserManager


LOGIN_URL = "https://www.snapchat.com/login"
WEB_URL = "https://www.snapchat.com/web?ref=sign_in_sidebar"


async def main() -> int:
    load_dotenv()

    session_state = os.getenv("SNAPCHAT_SESSION_STATE", "sessions/snapchat_state.json").strip()
    session_file = Path(session_state)

    browser = BrowserManager(headless=False, screenshots_dir="screenshots")

    print(f"SESSION_STATE={session_file}", flush=True)
    await browser.start()
    try:
        existing_state = str(session_file) if session_file.exists() else None
        ctx = await browser.new_context(account_id=9901, storage_state=existing_state)
        page = await ctx.new_page()

        print(f"OPEN_URL={LOGIN_URL}", flush=True)
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

        print("MANUAL_LOGIN_REQUIRED=True", flush=True)
        print("HAY_DANG_NHAP_TREN_TRINH_DUYET_SAU_DO_NHAN_ENTER_TAI_TERMINAL", flush=True)
        await asyncio.to_thread(input)

        await page.goto(WEB_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)
        current_url = page.url.lower()

        if "accounts.snapchat.com" in current_url or "/login" in current_url:
            screenshot = Path("screenshots") / "snapchat_session_bootstrap_failed.png"
            await page.screenshot(path=str(screenshot), full_page=True)
            print("SESSION_BOOTSTRAP=FAILED", flush=True)
            print(f"FINAL_URL={page.url}", flush=True)
            print(f"SCREENSHOT={screenshot}", flush=True)
            return 1

        session_file.parent.mkdir(parents=True, exist_ok=True)
        await ctx.storage_state(path=str(session_file))

        screenshot = Path("screenshots") / "snapchat_session_bootstrap_ok.png"
        await page.screenshot(path=str(screenshot), full_page=True)

        print("SESSION_BOOTSTRAP=OK", flush=True)
        print(f"FINAL_URL={page.url}", flush=True)
        print(f"SCREENSHOT={screenshot}", flush=True)
        return 0
    finally:
        await browser.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
