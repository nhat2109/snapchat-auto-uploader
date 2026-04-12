"""
modules/automation/scraper.py
Viral Video Scraper - Tìm và thu thập video viral từ YouTube, TikTok, Douyin
Theo hethong.txt - Section 2.1
"""

import re
import asyncio
import random
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from loguru import logger

from modules.utils.logger import PipelineLogger
from modules.utils.retry import retry_on_failure, async_random_delay
from modules.utils.retry import random_delay


class ViralVideoScraper:
    """
    Scraper tìm video viral từ nhiều nguồn.
    Sources: YouTube Shorts, TikTok, Douyin, Instagram Reels (optional)
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
            sources         : Nguồn scrape ['youtube', 'tiktok', 'douyin']
            pipeline_logger : Logger để cập nhật GUI
        """
        self._log = pipeline_logger or PipelineLogger()
        self._log.section("VIRAL VIDEO SCRAPER")

        if sources is None:
            sources = ["youtube", "tiktok", "douyin"]

        all_videos = []
        for kw in keywords:
            self._log.info(f"🔍 Tìm kiếm: '{kw}'")
            for source in sources:
                videos = await self._scrape_keyword(kw, source, max_results)
                all_videos.extend(videos)

        # Filter theo criteria
        filtered = [
            v for v in all_videos
            if v.get("views", 0) >= min_views
            and v.get("duration", 60) <= max_duration_sec
        ]

        self._log.info(f"✅ Tìm thấy {len(filtered)} video viral đạt chuẩn")
        return filtered

    async def _scrape_keyword(self, keyword: str,
                               source: str,
                               max_results: int) -> List[Dict[str, Any]]:
        """Scrape theo keyword + source."""
        if source == "youtube":
            return await self._scrape_youtube(keyword, max_results)
        elif source == "tiktok":
            return await self._scrape_tiktok(keyword, max_results)
        elif source == "douyin":
            return await self._scrape_douyin(keyword, max_results)
        return []

    # ─────────────────────────────────────────────────────────────────────
    #  YouTube Shorts Scraper
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_youtube(self, keyword: str,
                               max_results: int) -> List[Dict[str, Any]]:
        """Scrape YouTube Shorts search results bằng requests + BeautifulSoup."""
        self._log.info(f"📺 YouTube: Tìm '{keyword}'...")

        try:
            import requests
            from bs4 import BeautifulSoup

            search_url = self.YOUTUBE_SEARCH.format(keyword.replace(" ", "+"))
            headers = {
                "User-Agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
                ]),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            response = requests.get(search_url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            videos = []

            # Parse video items từ YouTube search results
            for item in soup.select("ytd-video-renderer, ytd-rich-item-renderer"):
                try:
                    link_el  = item.select_one("a#video-title, a#thumbnail")
                    title_el = item.select_one("h3 a, #title .yt-simple-endpoint")
                    meta_el  = item.select_one(".yt-formatted-string")

                    if not link_el or not title_el:
                        continue

                    href = link_el.get("href", "")
                    if "/shorts/" in href:
                        video_id = href.split("/shorts/")[-1].split("?")[0]
                    elif "/watch?v=" in href:
                        video_id = href.split("v=")[-1].split("&")[0]
                    else:
                        continue

                    url     = f"https://www.youtube.com/watch?v={video_id}"
                    title   = title_el.get_text(strip=True)
                    views   = self._parse_views(meta_el.get_text(strip=True) if meta_el else "0")
                    duration = 60  # Shorts thường <60s

                    videos.append({
                        "source_url": url,
                        "title":      title,
                        "source":     "youtube",
                        "video_id":   video_id,
                        "views":      views,
                        "duration":   duration,
                        "keyword":    keyword,
                    })

                    if len(videos) >= max_results:
                        break

                except Exception as e:
                    continue

            self._log.info(f"  → YouTube: {len(videos)} video(s) tìm thấy")
            await async_random_delay(1.0, 3.0)
            return videos

        except Exception as e:
            self._log.error(f"YouTube scrape failed: {e}")
            return []

    def _parse_views(self, text: str) -> int:
        """Parse view count từ text: '1.2M views' → 1200000"""
        text = text.lower().replace(",", "").replace(" ", "")
        if "k" in text:
            try:
                return int(float(text.replace("k", "").replace("views", "")) * 1000)
            except Exception:
                return 0
        if "m" in text:
            try:
                return int(float(text.replace("m", "").replace("views", "")) * 1_000_000)
            except Exception:
                return 0
        try:
            return int(re.sub(r"[^\d]", "", text))
        except Exception:
            return 0

    # ─────────────────────────────────────────────────────────────────────
    #  TikTok Scraper (headless browser)
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_tiktok(self, keyword: str,
                               max_results: int) -> List[Dict[str, Any]]:
        """
        Scrape TikTok search results.
        Sử dụng requests (fallback) — headless browser cần có Playwright.
        """
        self._log.info(f"📱 TikTok: Tìm '{keyword}'...")

        try:
            import requests
            from bs4 import BeautifulSoup

            search_url = f"https://www.tiktok.com/search/video?q={keyword.replace(' ', '+')}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }

            response = requests.get(search_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "lxml")

            videos = []
            # TikTok renders content bằng JS — có thể cần Playwright
            # Tạm thời parse link pattern
            for link in soup.find_all("a", href=re.compile(r"/video/\d+")):
                href = link.get("href", "")
                if href and "/video/" in href:
                    videos.append({
                        "source_url": f"https://www.tiktok.com{href}",
                        "title":      keyword,
                        "source":     "tiktok",
                        "video_id":   href.split("/video/")[-1],
                        "views":      0,   # views ẩn sau JS render
                        "duration":   30,
                        "keyword":    keyword,
                    })
                if len(videos) >= max_results:
                    break

            self._log.info(f"  → TikTok: {len(videos)} video(s) tìm thấy")
            await async_random_delay(2.0, 4.0)
            return videos

        except Exception as e:
            self._log.error(f"TikTok scrape failed: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────
    #  Douyin Scraper
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_douyin(self, keyword: str,
                               max_results: int) -> List[Dict[str, Any]]:
        """Scrape Douyin (Chinese TikTok)."""
        self._log.info(f"🇨🇳 Douyin: Tìm '{keyword}'...")

        try:
            import requests
            from bs4 import BeautifulSoup

            search_url = f"https://www.douyin.com/search/{keyword.replace(' ', '%20')}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            response = requests.get(search_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "lxml")

            videos = []
            for link in soup.find_all("a", href=re.compile(r"/video/\d+")):
                href = link.get("href", "")
                if href:
                    if not href.startswith("http"):
                        href = f"https://www.douyin.com{href}"
                    videos.append({
                        "source_url": href,
                        "title":      keyword,
                        "source":     "douyin",
                        "video_id":   "",
                        "views":      0,
                        "duration":   30,
                        "keyword":    keyword,
                    })
                if len(videos) >= max_results:
                    break

            self._log.info(f"  → Douyin: {len(videos)} video(s) tìm thấy")
            await async_random_delay(2.0, 4.0)
            return videos

        except Exception as e:
            self._log.error(f"Douyin scrape failed: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────
    #  Save to database
    # ─────────────────────────────────────────────────────────────────────
    def save_to_db(self, videos: List[Dict[str, Any]], db) -> int:
        """Lưu danh sách video vào database."""
        count = 0
        for v in videos:
            try:
                # Kiểm tra trùng URL
                existing = db.session.query(db.query(db.models.Video).filter_by(
                    source_url=v["source_url"]
                ).first()) if db else None

                if existing:
                    continue

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

            except Exception as e:
                logger.error(f"Save video failed: {e}")

        if db:
            db.session.commit()
        return count
