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

    if not username or not password:
        print("ERROR: Missing SNAPCHAT_USERNAME or SNAPCHAT_PASSWORD in .env")
        return 2

    browser = BrowserManager(headless=False, screenshots_dir="screenshots")
    plog = PipelineLogger()
    snap = SnapchatAutomation(browser, plog)

    await browser.start()
    try:
        ctx = await browser.new_context(account_id=9001)
        page = await ctx.new_page()
        snap._page = page

        print("CHECK=LOGIN_START", flush=True)
        login_ok = await asyncio.wait_for(snap._login(username, password), timeout=120)
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
