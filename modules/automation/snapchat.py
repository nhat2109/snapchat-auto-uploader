"""
modules/automation/snapchat.py
Snapchat Automation - Upload video + thêm nhạc
"""

import os
import asyncio
from typing import Optional, Dict, Any

from loguru import logger

from modules.core.browser import BrowserManager
from modules.utils.logger import PipelineLogger
from modules.utils.retry import async_random_delay
from modules.utils.retry import random_delay


class SnapchatAutomation:
    """
    Tự động hóa quy trình đăng video lên Snapchat.
    Steps:
      1. Login
      2. Navigate to content studio / creator studio
      3. Upload video
      4. Thêm nhạc (search by title + artist)
      5. Publish
    """

    BASE_URL = "https://www.snapchat.com"

    def __init__(self,
                 browser: BrowserManager,
                 logger: Optional[PipelineLogger] = None):
        self.browser      = browser
        self._log         = logger or PipelineLogger()
        self._page        = None
        self._account_id: Optional[int] = None

    # ─────────────────────────────────────────────────────────────────────
    #  Main flow
    # ─────────────────────────────────────────────────────────────────────
    async def run(self,
                  username: str,
                  password: str,
                  video_path: str,
                  music_title: str,
                  artist: str,
                  title: Optional[str] = None,
                  description: Optional[str] = None,
                  tags: Optional[str] = None,
                  account_id: Optional[int] = None,
                  headless: bool = True) -> Dict[str, Any]:
        """
        Chạy toàn bộ quy trình upload video lên Snapchat.
        """
        self._account_id = account_id
        result = {"success": False, "message": "", "post_url": None}

        try:
            self._log.section("SNAPCHAT VIDEO UPLOAD")
            self._log.info(f"User: {username} | Video: {title or os.path.basename(video_path)}")

            # Tạo context
            ctx = await self.browser.new_context(account_id=self._account_id or 0)
            self._page = await ctx.new_page()

            # Step 1: Login
            login_ok = await self._login(username, password)
            if not login_ok:
                result["message"] = "Đăng nhập Snapchat thất bại"
                await self._save_error_screenshot("snapchat_login_failed")
                return result

            # Step 2: Navigate to creator/content studio
            studio_ok = await self._navigate_to_studio()
            if not studio_ok:
                result["message"] = "Không navigate được đến Content Studio"
                return result

            # Step 3: Upload video
            upload_ok = await self._upload_video(video_path)
            if not upload_ok:
                result["message"] = "Upload video thất bại"
                await self._save_error_screenshot("snapchat_upload_failed")
                return result

            # Step 4: Set title + description
            if title or description:
                await self._set_content_info(title, description, tags)

            # Step 5: Thêm nhạc
            music_ok = await self._add_music(music_title, artist)
            if not music_ok:
                self._log.warn("⚠️ Thêm nhạc không thành công (bài có thể chưa được distribute)")

            # Step 6: Publish
            publish_ok = await self._publish()
            if not publish_ok:
                result["message"] = "Publish thất bại"
                return result

            result["success"] = True
            result["message"] = "Video đã đăng lên Snapchat thành công!"
            self._log.info("✅ Snapchat upload hoàn tất!")

        except Exception as e:
            result["message"] = str(e)
            self._log.error(f"Snapchat error: {e}", exc_info=True)
            await self._save_error_screenshot("snapchat_error")

        finally:
            if self._page:
                try:
                    await self._page.close()
                except Exception:
                    pass

        return result

    # ─────────────────────────────────────────────────────────────────────
    #  Step 1: Login
    # ─────────────────────────────────────────────────────────────────────
    async def _login(self, username: str, password: str) -> bool:
        self._log.info("🔐 Đang đăng nhập Snapchat...")

        try:
            # Điều hướng đến trang đăng nhập
            login_url = f"{self.BASE_URL}/login"
            ok = await self.browser.safe_goto(self._page, login_url)
            if not ok:
                return False
            await asyncio.sleep(3)

            # Step 1: Điền username/email
            user_selectors = [
                '[class*="SignInForm"] input[class*="SignInForm_input"]',
                'form input[class*="SignInForm_input"]',
                'input[name="username"]',
                'input[id="username"]',
                'input[placeholder*="username" i]',
                'input[placeholder*="email" i]',
                'input[placeholder*="user" i]',
                'input[autocomplete="username"]',
                'input[type="text"]:not([class*="SearchInput"])',
                '#username_field',
            ]
            user_ok = await self._try_fill_selectors(user_selectors, username)
            if not user_ok:
                self._log.warn("Không tìm thấy ô username/email")
                await self._save_error_screenshot("snapchat_login_username_missing")
                return False

            # Submit bước username để chuyển sang bước password
            username_submit = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Đăng nhập")',
                'button:has-text("Đăng Nhập")',
                'button:has-text("Log in")',
                'button:has-text("Log In")',
                'button:has-text("Next")',
                'button:has-text("Continue")',
                '[data-testid="login-btn"]',
                '.login-btn',
            ]
            await self._try_click_selectors(username_submit)

            await async_random_delay(0.5, 1.5)

            # Step 2: Điền password (trang 2 bước của Snapchat)
            pass_selectors = [
                '[class*="SignInForm"] input[type="password"]',
                'form input[type="password"]',
                'input[name="password"]',
                'input[id="password"]',
                'input[type="password"]',
                'input[autocomplete="current-password"]',
                '[class*="SignInForm"] input[class*="SignInForm_input"]',
            ]

            pass_ok = False
            for _ in range(5):
                pass_ok = await self._try_fill_selectors(pass_selectors, password)
                if pass_ok:
                    break
                checkpoint = await self._detect_login_checkpoint()
                if checkpoint:
                    self._log.warn(f"Checkpoint phát hiện sau bước username: {checkpoint}")
                    await self._save_error_screenshot("snapchat_login_checkpoint")
                    return False
                await asyncio.sleep(1)

            if not pass_ok:
                self._log.warn("Không tìm thấy ô password sau bước username")
                await self._save_error_screenshot("snapchat_login_password_missing")
                return False

            await async_random_delay(0.3, 0.8)

            # Submit bước password
            password_submit = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Đăng nhập")',
                'button:has-text("Đăng Nhập")',
                'button:has-text("Log In")',
                'button:has-text("Sign In")',
                'button:has-text("Continue")',
                '[data-testid="login-btn"]',
                '.login-btn',
            ]
            await self._try_click_selectors(password_submit)

            # Đợi redirect sau login
            await asyncio.sleep(5)
            current_url = self._page.url
            self._log.info(f"URL sau login: {current_url}")

            checkpoint = await self._detect_login_checkpoint()
            if checkpoint:
                self._log.warn(f"Checkpoint đăng nhập: {checkpoint}")
                await self._save_error_screenshot("snapchat_login_checkpoint")
                return False

            still_has_password = await self._is_any_selector_visible(pass_selectors, timeout=1500)
            still_has_username = await self._is_any_selector_visible(user_selectors, timeout=1500)

            if "login" not in current_url.lower() and not still_has_password:
                self._log.info("✅ Đăng nhập Snapchat thành công")
                return True

            if still_has_username or still_has_password:
                self._log.warn("⚠️ Vẫn còn form đăng nhập, login chưa hoàn tất")
                await self._save_error_screenshot("snapchat_login_failed")
                return False

            # Một số case URL vẫn chứa login nhưng thực tế đã auth bằng redirect token.
            self._log.warn("⚠️ Trạng thái login chưa rõ ràng, tạm coi là thất bại")
            await self._save_error_screenshot("snapchat_login_unclear")
            return False

        except Exception as e:
            self._log.error(f"Login Snapchat failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  Step 2: Navigate to Content Studio
    # ─────────────────────────────────────────────────────────────────────
    async def _navigate_to_studio(self) -> bool:
        self._log.info("🎬 Đang mở Content Studio...")

        studio_urls = [
            f"{self.BASE_URL}/content",
            f"{self.BASE_URL}/studio",
            f"{self.BASE_URL}/creators",
            f"{self.BASE_URL}/snapcodes",
        ]

        for url in studio_urls:
            ok = await self.browser.safe_goto(self._page, url)
            if ok:
                await asyncio.sleep(3)
                self._log.info(f"✅ Content Studio: {url}")
                return True

        self._log.warn("Content Studio URLs không hoạt động, thử click menu...")
        return True  # Vẫn tiếp tục

    # ─────────────────────────────────────────────────────────────────────
    #  Step 3: Upload video
    # ─────────────────────────────────────────────────────────────────────
    async def _upload_video(self, filepath: str) -> bool:
        if not os.path.exists(filepath):
            self._log.error(f"Video file không tồn tại: {filepath}")
            return False

        filename = os.path.basename(filepath)
        self._log.info(f"📤 Đang upload video: {filename}")

        try:
            # Tìm upload button hoặc dropzone
            upload_selectors = [
                'input[type="file"]',
                'input[accept*="video"]',
                '[data-testid="upload-button"]',
                '[class*="upload"]',
                '[class*="dropzone"]',
                'button:has-text("Upload")',
            ]

            file_input = None
            for sel in upload_selectors:
                try:
                    el = await self._page.wait_for_selector(sel, state="visible", timeout=3000)
                    if el:
                        file_input = el
                        break
                except Exception:
                    continue

            if file_input:
                await file_input.set_input_files(filepath)
                self._log.info("✅ Video file input đã set")
                await async_random_delay(3.0, 6.0)
            else:
                # Fallback: click button rồi upload
                await self._click_upload_button()
                await asyncio.sleep(1)
                await self._page.set_input_files('input[type="file"]', filepath)

            # Đợi video processing
            self._log.info("⏳ Đợi video processing...")
            await asyncio.sleep(5)
            await self._wait_for_upload_complete()
            self._log.info("✅ Video uploaded!")
            return True

        except Exception as e:
            self._log.error(f"Upload video failed: {e}")
            return False

    async def _click_upload_button(self):
        """Click nút upload nếu không tìm thấy input[type=file]."""
        buttons = [
            'button:has-text("Upload")',
            'button:has-text("Add Video")',
            'button:has-text("Tải lên")',
            '[data-testid="upload-cta"]',
        ]
        for sel in buttons:
            try:
                await self._page.click(sel, timeout=3000)
                await asyncio.sleep(1)
                return
            except Exception:
                continue

    async def _wait_for_upload_complete(self, timeout: int = 60):
        """Đợi video upload xong (progress bar biến mất)."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            try:
                # Kiểm tra progress bar / loading indicator
                loading = await self._page.query_selector(
                    '[class*="progress"], [class*="loading"], [class*="uploading"]'
                )
                if not loading:
                    break
                await asyncio.sleep(2)
            except Exception:
                break

    # ─────────────────────────────────────────────────────────────────────
    #  Step 4: Set content info
    # ─────────────────────────────────────────────────────────────────────
    async def _set_content_info(self, title: Optional[str], description: Optional[str],
                                 tags: Optional[str] = None) -> bool:
        try:
            if title:
                title_sel = [
                    'input[name="title"]', 'input[placeholder*="title" i]',
                    'textarea[name="title"]', '[data-testid="title-input"]',
                ]
                await self._try_fill_selectors(title_sel, title)
                self._log.info("✅ Title đã điền")

            if description:
                desc_sel = [
                    'textarea[name="description"]',
                    'textarea[placeholder*="description" i]',
                    '[data-testid="description"]',
                ]
                await self._try_fill_selectors(desc_sel, description)
                self._log.info("✅ Description đã điền")

            if tags:
                tag_sel = [
                    'input[name="tags"]', 'input[placeholder*="tag" i]',
                    '[data-testid="tags-input"]',
                ]
                await self._try_fill_selectors(tag_sel, tags)
                self._log.info("✅ Tags đã điền")

            await async_random_delay(1.0, 2.0)
            return True
        except Exception as e:
            self._log.warn(f"Set content info failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  Step 5: Add music
    # ─────────────────────────────────────────────────────────────────────
    async def _add_music(self, music_title: str, artist: str) -> bool:
        self._log.info(f"🎵 Tìm kiếm nhạc: {music_title} - {artist}")

        try:
            # Mở music/search panel
            music_buttons = [
                'button:has-text("Music")',
                '[data-testid="add-music"]',
                '[class*="music"] button',
                '[class*="sound"]',
                'button:has-text("Sound")',
            ]

            clicked = False
            for sel in music_buttons:
                try:
                    await self._page.click(sel, timeout=3000)
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                self._log.warn("Music button không tìm thấy")
                return False

            await async_random_delay(1.5, 3.0)

            # Search box
            search_sel = [
                'input[name="search"], input[placeholder*="search" i]',
                'input[placeholder*="music" i], input[placeholder*="sound" i]',
                '[data-testid="music-search"]',
            ]
            await self._try_fill_selectors(search_sel, f"{music_title} {artist}")
            await async_random_delay(1.0, 2.0)
            await self._page.keyboard.press("Enter")

            # Đợi kết quả
            await asyncio.sleep(3)

            # Chọn track đầu tiên
            track_sel = [
                '[data-testid="track-item"]',
                '[class*="track"]',
                '[class*="result"]',
                '.music-item',
            ]
            for sel in track_sel:
                try:
                    items = await self._page.query_selector_all(sel)
                    if items:
                        await items[0].click()
                        self._log.info("✅ Music track đã chọn")
                        await async_random_delay(1.0, 2.0)
                        return True
                except Exception:
                    continue

            self._log.warn("Không tìm thấy music track")
            return False

        except Exception as e:
            self._log.error(f"Add music failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  Step 6: Publish
    # ─────────────────────────────────────────────────────────────────────
    async def _publish(self) -> bool:
        self._log.info("🚀 Đang publish...")

        publish_selectors = [
            'button:has-text("Publish")',
            'button:has-text("Post")',
            'button:has-text("Share")',
            'button:has-text("Đăng")',
            '[data-testid="publish-btn"]',
            '[class*="publish"] button',
        ]

        for sel in publish_selectors:
            ok = await self.browser.safe_click(self._page, sel, delay=1.0)
            if ok:
                self._log.info("✅ Video đã được publish!")
                await async_random_delay(3.0, 5.0)
                return True

        self._log.warn("Publish button không tìm thấy")
        return False

    # ─────────────────────────────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────────────────────────────
    async def _try_fill_selectors(self, selectors, value: str) -> bool:
        """Thử fill với nhiều selector alternative."""
        for sel in selectors:
            sel = sel.strip()
            try:
                loc = self._page.locator(sel).first
                await loc.wait_for(state="visible", timeout=3000)
                await loc.click(timeout=2000)
                await loc.fill(value, timeout=3000)
                return True
            except Exception:
                # Fallback JS set value cho các input khó fill bằng Playwright bình thường.
                try:
                    set_ok = await self._page.evaluate(
                        """
                        ([selector, text]) => {
                          const el = document.querySelector(selector);
                          if (!el) return false;
                          el.focus();
                          el.value = text;
                          el.dispatchEvent(new Event('input', { bubbles: true }));
                          el.dispatchEvent(new Event('change', { bubbles: true }));
                          return true;
                        }
                        """,
                        [sel, value],
                    )
                    if set_ok:
                        return True
                except Exception:
                    pass
            try:
                el = await self._page.wait_for_selector(sel, state="attached", timeout=1500)
                if el:
                    await el.fill(value)
                    return True
            except Exception:
                continue
        return False

    async def _try_click_selectors(self, selectors, timeout: int = 3000) -> bool:
        """Thử click với nhiều selector alternative."""
        for sel in selectors:
            sel = sel.strip()
            try:
                await self._page.wait_for_selector(sel, state="visible", timeout=timeout)
                await self._page.click(sel, no_wait_after=True)
                return True
            except Exception:
                continue
        return False

    async def _is_any_selector_visible(self, selectors, timeout: int = 1000) -> bool:
        for sel in selectors:
            try:
                await self._page.wait_for_selector(sel, state="visible", timeout=timeout)
                return True
            except Exception:
                continue
        return False

    async def _detect_login_checkpoint(self) -> Optional[str]:
        """Phát hiện các checkpoint như captcha, 2FA, verify challenge."""
        try:
            from urllib.parse import urlparse

            raw_url = self._page.url
            parsed = urlparse(raw_url)
            path = parsed.path.lower()

            # Chỉ xét theo path để tránh false positive từ chuỗi mã hóa query (vd: %2F).
            checkpoint_paths = [
                "captcha",
                "challenge",
                "/verify",
                "/two_factor",
                "/2fa",
            ]
            if any(k in path for k in checkpoint_paths):
                return f"checkpoint_url:{raw_url.lower()}"

            text = (await self._page.evaluate("() => document.body ? document.body.innerText : ''")).lower()
            checkpoint_keywords = [
                "captcha",
                "i'm not a robot",
                "verify",
                "verification code",
                "two-factor",
                "2fa",
                "security check",
                "suspicious",
            ]
            for kw in checkpoint_keywords:
                if kw in text:
                    return kw
        except Exception:
            return None
        return None

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
        """Đăng xuất khỏi Snapchat."""
        try:
            await self.browser.safe_goto(self._page, f"{self.BASE_URL}/logout")
            self._log.info("✅ Đã logout Snapchat")
        except Exception:
            pass
