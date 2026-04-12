"""
modules/automation/ditto.py
Ditto Music Automation - Upload nhạc lên dịch vụ phân phối
"""

import os
import asyncio
from typing import Optional, Dict, Any

from loguru import logger

from modules.core.browser import BrowserManager
from modules.utils.logger import PipelineLogger
from modules.utils.retry import retry_on_failure, random_delay
from modules.utils.retry import async_random_delay


class DittoAutomation:
    """
    Tự động hóa quy trình upload nhạc lên Ditto Music.
    Steps:
      1. Login
      2. Navigate to upload
      3. Fill metadata (title, artist, language)
      4. Upload audio file
      5. Confirm
    """

    BASE_URL = "https://distrokid.com"

    def __init__(self,
                 browser: BrowserManager,
                 logger: Optional[PipelineLogger] = None):
        self.browser   = browser
        self._log      = logger or PipelineLogger()
        self._page     = None
        self._account_id: Optional[int] = None

    # ─────────────────────────────────────────────────────────────────────
    #  Main flow
    # ─────────────────────────────────────────────────────────────────────
    async def run(self,
                  username: str,
                  password: str,
                  music_file: str,
                  music_title: str,
                  artist: str,
                  language: str = "Vietnamese",
                  account_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Chạy toàn bộ quy trình upload nhạc lên Ditto.
        Trả về dict kết quả.
        """
        self._account_id = account_id
        result = {"success": False, "message": "", "url": None}

        try:
            self._log.section("DITTO MUSIC UPLOAD")
            self._log.info(f"User: {username} | Track: {music_title} - {artist}")

            # Tạo context mới
            ctx = await self.browser.new_context(account_id=self._account_id or 0)
            self._page = await ctx.new_page()

            # Step 1: Login
            login_ok = await self._login(username, password)
            if not login_ok:
                result["message"] = "Đăng nhập Ditto thất bại"
                await self._save_error_screenshot("ditto_login_failed")
                return result

            # Step 2: Navigate to upload
            nav_ok = await self._navigate_to_upload()
            if not nav_ok:
                result["message"] = "Không navigate được đến trang upload"
                return result

            # Step 3: Fill metadata
            meta_ok = await self._fill_metadata(music_title, artist, language)
            if not meta_ok:
                result["message"] = "Điền metadata thất bại"
                return result

            # Step 4: Upload file
            upload_ok = await self._upload_file(music_file)
            if not upload_ok:
                result["message"] = "Upload file nhạc thất bại"
                return result

            # Step 5: Submit
            submit_ok = await self._submit()
            if not submit_ok:
                result["message"] = "Submit thất bại"
                return result

            result["success"] = True
            result["message"] = "Nhạc đã được tải lên Ditto thành công!"
            self._log.info("✅ Ditto upload hoàn tất!")

        except Exception as e:
            result["message"] = str(e)
            self._log.error(f"Ditto error: {e}", exc_info=True)
            await self._save_error_screenshot("ditto_error")

        finally:
            if self._page:
                await self._page.close()

        return result

    # ─────────────────────────────────────────────────────────────────────
    #  Step 1: Login
    # ─────────────────────────────────────────────────────────────────────
    async def _login(self, username: str, password: str) -> bool:
        self._log.info("🔐 Đang đăng nhập Ditto Music...")

        try:
            await self.browser.safe_goto(self._page, f"{self.BASE_URL}/signin")
            await asyncio.sleep(2)

            # Điền email
            email_sel = 'input[name="email"], input[type="email"], #email'
            await self._safe_fill_selectors(email_sel, username)

            # Điền password
            pass_sel = 'input[name="password"], input[type="password"], #password'
            await self._safe_fill_selectors(pass_sel, password)

            # Click login
            login_sel = 'button[type="submit"], input[type="submit"], .btn-signin, button:has-text("Sign In")'
            await self.browser.safe_click(self._page, login_sel)

            # Đợi redirect
            await asyncio.sleep(4)
            await self._random_scroll()
            self._log.info("✅ Đăng nhập Ditto thành công")
            return True

        except Exception as e:
            self._log.error(f"Login Ditto failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  Step 2: Navigate to upload
    # ─────────────────────────────────────────────────────────────────────
    async def _navigate_to_upload(self) -> bool:
        self._log.info("🎵 Đang navigate đến trang upload...")

        upload_urls = [
            f"{self.BASE_URL}/new/distribution",
            f"{self.BASE_URL}/distributions/new",
            f"{self.BASE_URL}/members/distribute",
        ]

        for url in upload_urls:
            ok = await self.browser.safe_goto(self._page, url)
            if ok:
                await asyncio.sleep(2)
                self._log.info(f"✅ Navigated: {url}")
                return True

        self._log.error("Không navigate được đến trang upload Ditto")
        return False

    # ─────────────────────────────────────────────────────────────────────
    #  Step 3: Fill metadata
    # ─────────────────────────────────────────────────────────────────────
    async def _fill_metadata(self,
                             title: str,
                             artist: str,
                             language: str) -> bool:
        self._log.info(f"📝 Điền metadata: {title} - {artist}")

        try:
            # Track title
            await self._safe_fill_selectors(
                'input[name="title"], #track-title, input[placeholder*="title" i], input[placeholder*="tên" i]',
                title
            )

            # Artist name
            await self._safe_fill_selectors(
                'input[name="artist"], #artist-name, input[placeholder*="artist" i], input[placeholder*="nghệ sĩ" i]',
                artist
            )

            # Language selector
            lang_map = {
                "vietnamese": "vi", "tiếng việt": "vi",
                "english": "en", "tiếng anh": "en",
            }
            lang_code = lang_map.get(language.lower(), "vi")

            lang_sel = (f'select[name="language"], select[name="lang"], '
                        f'#language, [data-testid="language-select"]')
            try:
                await self._page.select_option(lang_sel, lang_code, timeout=3000)
            except Exception:
                self._log.warn("Language selector không tìm thấy, bỏ qua")

            await self._random_scroll()
            await async_random_delay(1.0, 2.0)
            self._log.info("✅ Metadata đã điền")
            return True

        except Exception as e:
            self._log.error(f"Fill metadata failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  Step 4: Upload file
    # ─────────────────────────────────────────────────────────────────────
    async def _upload_file(self, filepath: str) -> bool:
        if not os.path.exists(filepath):
            self._log.error(f"File không tồn tại: {filepath}")
            return False

        self._log.info(f"📤 Đang upload file: {os.path.basename(filepath)}")

        try:
            # Tìm input[type="file"]
            file_sel = 'input[type="file"], input[name="audio_file"], input[name="file"]'
            try:
                file_input = await self._page.wait_for_selector(file_sel, state="visible", timeout=5000)
                if file_input:
                    await file_input.set_input_files(filepath)
                    self._log.info("✅ File input đã set")
                    await async_random_delay(2.0, 4.0)
                    return True
            except Exception:
                pass

            # Fallback: dùng set_input_files trên page
            await self._page.set_input_files(file_sel, filepath)
            await async_random_delay(2.0, 4.0)
            self._log.info("✅ File uploaded!")
            return True

        except Exception as e:
            self._log.error(f"Upload file failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  Step 5: Submit
    # ─────────────────────────────────────────────────────────────────────
    async def _submit(self) -> bool:
        self._log.info("🚀 Đang submit...")

        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Upload")',
            'button:has-text("Submit for Review")',
            '.btn-submit',
        ]

        for sel in submit_selectors:
            ok = await self.browser.safe_click(self._page, sel, delay=1.0)
            if ok:
                self._log.info("✅ Submit thành công!")
                await async_random_delay(3.0, 5.0)
                return True

        self._log.warn("Submit selector không tìm thấy")
        return False

    # ─────────────────────────────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────────────────────────────
    async def _safe_fill_selectors(self, selectors: str, value: str) -> bool:
        """Thử fill với nhiều selector alternative."""
        for sel in selectors.split(", "):
            sel = sel.strip()
            try:
                await self._page.wait_for_selector(sel, state="visible", timeout=3000)
                await self._page.fill(sel, value)
                return True
            except Exception:
                continue
        return False

    async def _random_scroll(self):
        from playwright.async_api import MouseButton
        await self._page.evaluate("""
            window.scrollTo({
                top: Math.random() * 500 + 200,
                behavior: 'smooth'
            })
        """)
        await asyncio.sleep(0.5)

    async def _save_error_screenshot(self, name: str):
        if self._page:
            try:
                from datetime import datetime
                from pathlib import Path
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = Path("screenshots") / f"{name}_{ts}.png"
                await self._page.screenshot(path=str(path), full_page=True)
                self._log.info(f"📸 Screenshot saved: {path}")
            except Exception as e:
                self._log.warn(f"Screenshot failed: {e}")

    async def logout(self):
        """Đăng xuất khỏi Ditto."""
        try:
            await self.browser.safe_goto(self._page, f"{self.BASE_URL}/logout")
            self._log.info("✅ Đã logout Ditto")
        except Exception:
            pass
