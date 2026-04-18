import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from modules.core.browser import BrowserManager


async def run_check() -> int:
    load_dotenv()

    username = os.getenv("SNAPCHAT_USERNAME", "").strip()
    password = os.getenv("SNAPCHAT_PASSWORD", "").strip()

    if not username or not password:
        print("ERROR: Missing SNAPCHAT_USERNAME or SNAPCHAT_PASSWORD in .env")
        return 2

    browser = BrowserManager(headless=True, screenshots_dir="screenshots")
    print("STEP=browser_start", flush=True)
    await browser.start()
    try:
        print("STEP=new_context", flush=True)
        ctx = await browser.new_context(account_id=9999)
        print("STEP=new_page", flush=True)
        page = await ctx.new_page()

        print("STEP=goto_login", flush=True)
        await page.goto("https://www.snapchat.com/login", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2)

        user_selectors = [
            'input[name="username"]',
            'input[id="username"]',
            'input[autocomplete="username"]',
            'input[placeholder*="Username" i]',
            'input[placeholder*="user" i]',
        ]
        pass_selectors = [
            'input[name="password"]',
            'input[id="password"]',
            'input[type="password"]',
            'input[autocomplete="current-password"]',
        ]
        login_btn_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button.ColoredButton_blueButton__IeoF4',
            'button:has-text("Log In")',
            'button:has-text("Sign In")',
            'button:has-text("Đăng nhập")',
        ]

        async def try_fill(selectors, value):
            for sel in selectors:
                try:
                    await page.wait_for_selector(sel, state="visible", timeout=3000)
                    await page.fill(sel, value)
                    return True
                except Exception:
                    continue
            return False

        print("STEP=fill_username", flush=True)
        user_ok = await try_fill(user_selectors, username)

        clicked = False
        print("STEP=click_first_submit", flush=True)
        for sel in login_btn_selectors:
            try:
                await page.wait_for_selector(sel, state="visible", timeout=3000)
                await page.click(sel, no_wait_after=True)
                clicked = True
                break
            except Exception:
                continue

        await asyncio.sleep(3)

        # Snapchat web login often asks username first, then password on next step.
        print("STEP=fill_password", flush=True)
        pass_ok = await try_fill(pass_selectors, password)
        if pass_ok:
            print("STEP=click_second_submit", flush=True)
            second_click = False
            for sel in login_btn_selectors:
                try:
                    await page.wait_for_selector(sel, state="visible", timeout=3000)
                    await page.click(sel, no_wait_after=True)
                    second_click = True
                    break
                except Exception:
                    continue
            clicked = clicked and second_click

        print("STEP=wait_after_submit", flush=True)
        await asyncio.sleep(8)
        final_url = page.url

        screenshot = Path("screenshots") / "snapchat_login_check.png"
        await page.screenshot(path=str(screenshot), full_page=True)

        ok = bool(user_ok and clicked and "login" not in final_url.lower())
        print(f"USERNAME_STEP_OK={user_ok}")
        print(f"PASSWORD_STEP_OK={pass_ok}")
        print(f"LOGIN_BUTTON_CLICKED={clicked}")
        print(f"FINAL_URL={final_url}")
        print(f"SCREENSHOT={screenshot}")

        if ok and "login" not in final_url.lower():
            print("SNAPCHAT_CONNECTION_STATUS=LIKELY_CONNECTED")
            return 0

        print("SNAPCHAT_CONNECTION_STATUS=NOT_CONFIRMED")
        return 1
    finally:
        print("STEP=browser_stop", flush=True)
        await browser.stop()


if __name__ == "__main__":
    async def _main() -> int:
        try:
            return await asyncio.wait_for(run_check(), timeout=120)
        except asyncio.TimeoutError:
            print("SNAPCHAT_CONNECTION_STATUS=TIMEOUT")
            return 3

    raise SystemExit(asyncio.run(_main()))
