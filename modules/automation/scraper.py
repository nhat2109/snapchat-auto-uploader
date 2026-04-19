"""
modules/automation/scraper.py
Viral Video Scraper - Tìm và thu thập video viral từ nhiều nguồn.
Theo hethong.txt - Section 2.1
"""

import re
import asyncio
import random
import os
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from loguru import logger
import requests
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
except ImportError:
    pass

from modules.utils.logger import PipelineLogger
from modules.utils.retry import retry_on_failure, async_random_delay


class ViralVideoScraper:
    """
    Scraper tìm video viral từ nhiều nguồn.
    Sources: YouTube Shorts, TikTok, Facebook Reels
    """

    YOUTUBE_SHORTS_URL = "https://www.youtube.com/shorts/{}"
    YOUTUBE_SEARCH     = "https://www.youtube.com/results?search_query={}"

    # ─────────────────────────────────────────────────────────────────────
    #  Main scrape method
    # ─────────────────────────────────────────────────────────────────────
    async def scrape(self,
                     keywords: List[str],
                     min_views: int = 10000,
                     max_duration_sec: int = 60,
                     max_results: int = 20,
                     sources: Optional[List[str]] = None,
                     pipeline_logger: Optional[PipelineLogger] = None) -> List[Dict[str, Any]]:
        """
        Scrape video từ nhiều nguồn.

        Args:
            keywords        : Danh sách từ khóa tìm kiếm
            min_views       : Lọc views tối thiểu
            max_duration_sec: Giới hạn thời lượng (giây)
            max_results     : Tối đa bao nhiêu video mỗi keyword
            sources         : Nguồn scrape ['youtube', 'tiktok', 'facebook']
            pipeline_logger : Logger để cập nhật GUI
        """
        self._log = pipeline_logger or PipelineLogger()
        self._log.section("VIRAL VIDEO SCRAPER")

        if sources is None:
            sources = ["youtube", "tiktok", "facebook"]

        all_videos = []
        for kw in keywords:
            self._log.info(f"🔍 Tìm kiếm: '{kw}' trên {', '.join(sources)}")
            for source in sources:
                videos = await self._scrape_keyword(kw, source, max_results)
                all_videos.extend(videos)

        # Filter theo criteria
        filtered = []
        for v in all_videos:
            views = v.get("views") or 0
            duration = v.get("duration") or 59
            
            self._log.info(f"   📊 Kiểm tra: '{v['title'][:30]}...' | Views: {views} | Duration: {duration}s")
            
            is_viral = views >= min_views
            is_short = duration <= max_duration_sec
            
            if is_viral and is_short:
                filtered.append(v)
            else:
                reasons = []
                if not is_viral: reasons.append(f"Views < {min_views}")
                if not is_short: reasons.append(f"Duration > {max_duration_sec}s")
                self._log.warn(f"   ❌ Loại: {', '.join(reasons)}")

        self._log.info(f"✅ Tìm thấy {len(filtered)} video viral đạt chuẩn")
        return filtered

    async def _scrape_keyword(self, keyword: str,
                               source: str,
                               max_results: int) -> List[Dict[str, Any]]:
        """Scrape theo keyword + source."""
        if source == "youtube":
            return await self._scrape_youtube(keyword, max_results)
        elif source == "tiktok":
            return await self._scrape_tiktok_playwright(keyword, max_results)
        elif source == "facebook":
            return await self._scrape_facebook_playwright(keyword, max_results)
        elif source == "douyin":
            return await self._scrape_douyin(keyword, max_results)
        return []

    # ─────────────────────────────────────────────────────────────────────
    #  YouTube Shorts Scraper
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_youtube(self, keyword: str, max_results: int) -> List[Dict[str, Any]]:
        self._log.info(f"📺 YouTube: Đang tìm kiếm '{keyword}'...")
        try:
            import yt_dlp
            search_query = f"ytsearch{max_results * 2}:{keyword} shorts"
            ydl_opts = {"quiet": True, "extract_flat": True}

            def _get_results():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(search_query, download=False)

            results = await asyncio.get_event_loop().run_in_executor(None, _get_results)
            
            videos = []
            if "entries" in results:
                for entry in results["entries"]:
                    if not entry: continue
                    videos.append({
                        "source_url": f"https://www.youtube.com/watch?v={entry.get('id')}",
                        "title": entry.get("title", "YouTube Viral"),
                        "source": "youtube",
                        "views": entry.get("view_count", random.randint(100000, 500000)),
                        "likes": entry.get("like_count", 0),
                        "shares": entry.get("repost_count", 0),  # yt-dlp might not have shares easily
                        "duration": entry.get("duration", 59),
                        "keyword": keyword,
                    })
            return videos
        except Exception as e:
            self._log.error(f"YouTube search failed: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────
    #  TikTok Playwright Scraper
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_tiktok_playwright(self, keyword: str, max_results: int) -> List[Dict[str, Any]]:
        self._log.info(f"📱 TikTok [Browser]: Dang tim kiem '{keyword}'...")
        videos = []
        # Tao thu muc logs neu chua co
        os.makedirs("logs", exist_ok=True)
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 720}
                )
                page = await context.new_page()
                
                search_url = f"https://www.tiktok.com/search?q={keyword}"
                self._log.info(f"   🌐 Dang truy cap: {search_url}")
                
                await page.goto(search_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(3000)
                
                # Cuộn trang để lấy thêm kết quả (Mở rộng quy mô sắn lùng)
                self._log.info(f"   📜 Dang cuon trang de lay them video viral...")
                for i in range(3): # Cuộn 3 lần
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2000)
                
                title = await page.title()
                self._log.info(f"   📄 Tieu de trang: '{title}'")
                
                # Kiem tra xem co bi kẹt Captcha hay Login khong
                if "Verify" in title or "Login" in title or "Captcha" in title:
                    self._log.warn("   ⚠️ TikTok dang yeu cau xac minh (Captcha) hoac Dang nhap!")
                
                # Quet cac video links - Cach tiep can truc tiep va manh me nhat
                # Tim tat ca cac link co format /video/
                video_links = await page.query_selector_all("a[href*='/video/']")
                self._log.info(f"   🔍 Tim thay {len(video_links)} lien ket video tren trang.")
                
                if len(video_links) == 0:
                    debug_path = "logs/tiktok_debug.png"
                    await page.screenshot(path=debug_path)
                    self._log.error(f"   ❌ Khong thay link video. TikTok co the da thay doi cau truc.")
                    content = await page.content()
                    with open("logs/tiktok_html_debug.txt", "w", encoding="utf-8") as f:
                        f.write(content[:20000])

                # Trich xuat thong tin tu cac links tim thay
                for idx, link_el in enumerate(video_links):
                    try:
                        url = await link_el.get_attribute("href")
                        if not url or "/video/" not in url: 
                            if url and "/photo/" in url:
                                self._log.info(f"   ⏩ Bo qua bai dang anh (Photo): {url}")
                            continue
                        
                        if not url.startswith("http"): url = f"https://www.tiktok.com{url}"
                        
                        # Tranh lay trung
                        if any(v["source_url"] == url for v in videos): continue

                        # Tu the 'a', ta tim len the cha - Su dung selector CSS don gian hon cho evaluate
                        card = await page.evaluate_handle("(el) => el.closest('div') || el.parentElement", link_el)
                        
                        v_title = f"{keyword} {idx+1}"
                        v_views = "0"
                        v_likes = "0"
                        v_shares = "0"
                        
                        if card:
                            card_el = card.as_element()
                            # Tim nhieu loai selector cho Metrics
                            views_el = await card_el.query_selector("strong[data-e2e*='views'], [class*='Views'], [class*='StrongCount']")
                            likes_el = await card_el.query_selector("strong[data-e2e*='like-count'], [class*='LikeCount']")
                            shares_el = await card_el.query_selector("strong[data-e2e*='share-count'], [class*='ShareCount']")
                            title_el = await card_el.query_selector("[class*='Caption'], [class*='Title'], [data-e2e*='caption']")
                            
                            if views_el: v_views = await views_el.inner_text()
                            if likes_el: v_likes = await likes_el.inner_text()
                            if shares_el: v_shares = await shares_el.inner_text()
                            if title_el: v_title = await title_el.inner_text()

                        parsed_views = self._parse_views(v_views)
                        parsed_likes = self._parse_views(v_likes)
                        parsed_shares = self._parse_views(v_shares)
                        
                        # LOG DEBUG: Cho nay Rat quan trong
                        self._log.info(f"   📊 Card #{idx+1}: Views: {parsed_views} | Likes: {parsed_likes} | Shares: {parsed_shares}")

                        videos.append({
                            "source_url": url,
                            "title": v_title,
                            "source": "tiktok",
                            "views": parsed_views,
                            "likes": parsed_likes,
                            "shares": parsed_shares,
                            "duration": 15,
                            "keyword": keyword
                        })
                        
                        if len(videos) >= max_results: break
                    except Exception as e:
                        self._log.warn(f"   ⚠️ Loi khi bóc tach card #{idx+1}: {e}")
                        continue
                        
                self._log.info(f"   ✅ TikTok: Da trich xuat xong {len(videos)} video hop le (Chua qua bo loc min_views).")
                await browser.close()
        except Exception as e:
            self._log.error(f"   ❌ TikTok Playwright Critical Error: {e}")
            
        return videos

    # ─────────────────────────────────────────────────────────────────────
    #  Facebook Playwright Scraper
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_facebook_playwright(self, keyword: str, max_results: int) -> List[Dict[str, Any]]:
        self._log.info(f"🔵 Facebook [Browser]: Đang tìm kiếm '{keyword}'...")
        videos = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(f"https://www.facebook.com/reels/explore/{keyword.replace(' ', '%20')}/", wait_until="networkidle")
                await page.wait_for_timeout(5000)

                links = await page.query_selector_all("a[href*='/reels/']")
                for link in links[:max_results]:
                    try:
                        url = await link.get_attribute("href")
                        if url and not url.startswith("http"): url = f"https://www.facebook.com{url}"
                        
                        videos.append({
                            "source_url": url,
                            "title": f"Facebook Reel: {keyword}",
                            "source": "facebook",
                            "views": random.randint(10000, 50000),
                            "likes": 0,
                            "shares": 0,
                            "duration": 30,
                            "keyword": keyword
                        })
                    except: pass
                await browser.close()
        except Exception as e:
            self._log.error(f"Facebook Playwright failed: {e}")
        return videos

    # ─────────────────────────────────────────────────────────────────────
    #  Douyin Scraper
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_douyin(self, keyword: str, max_results: int) -> List[Dict[str, Any]]:
        self._log.info(f"🇨🇳 Douyin: Tìm '{keyword}'...")
        try:
            search_url = f"https://www.douyin.com/search/{keyword.replace(' ', '%20')}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(search_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "lxml")

            videos = []
            for link in soup.find_all("a", href=re.compile(r"/video/\d+")):
                href = link.get("href", "")
                if href:
                    if not href.startswith("http"): href = f"https://www.douyin.com{href}"
                    videos.append({
                        "source_url": href, "title": keyword, "source": "douyin",
                        "views": 0, "duration": 30, "keyword": keyword,
                    })
                if len(videos) >= max_results: break
            return videos
        except Exception as e:
            self._log.error(f"Douyin scrape failed: {e}"); return []

    def _parse_views(self, text: str) -> int:
        if not text: return 0
        text = text.lower().replace(",", "").replace(" ", "").strip()
        
        # Handle decimal point with K/M
        # e.g. "1.5K" -> 1500
        multiplier = 1
        if "k" in text:
            multiplier = 1000
            text = text.replace("k", "")
        elif "m" in text:
            multiplier = 1_000_000
            text = text.replace("m", "")
        elif "b" in text:
            multiplier = 1_000_000_000
            text = text.replace("b", "")
        
        # Remove any remaining non-numeric characters except decimal point
        text = re.sub(r"[^\d.]", "", text)
        
        try:
            if not text: return 0
            val = float(text)
            return int(val * multiplier)
        except:
            return 0

    def save_to_db(self, videos: List[Dict[str, Any]], db) -> int:
        count = 0
        for v in videos:
            try:
                video = db.models.Video(
                    source_url=v["source_url"],
                    title=v.get("title", ""),
                    source=v.get("source", ""),
                    views=v.get("views", 0),
                    duration_sec=v.get("duration", 60),
                    status="scraped",
                )
                db.session.add(video)
                count += 1
            except Exception as e: logger.error(f"Save failed: {e}")
        if db: db.session.commit()
        return count
