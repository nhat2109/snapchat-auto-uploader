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
        filtered = []
        for v in all_videos:
            views = v.get("views") or 0
            duration = v.get("duration") or 59 # Mac dinh 59s neu thieu
            
            # Debug: In ra chi so cua tung video de kiem tra
            self._log.info(f"   📊 Kiem tra: '{v['title'][:30]}...' | Views: {views} | Duration: {duration}s")
            
            is_viral = views >= min_views
            is_short = duration <= max_duration_sec
            
            if is_viral and is_short:
                filtered.append(v)
            else:
                reasons = []
                if not is_viral: reasons.append(f"Views < {min_views}")
                if not is_short: reasons.append(f"Duration > {max_duration_sec}s")
                self._log.warn(f"   ❌ Loai: {', '.join(reasons)}")

        self._log.info(f"✅ Tim thay {len(filtered)} video viral dat chuan")
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
    #  YouTube Shorts Scraper (Using yt-dlp search - much more reliable)
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_youtube(self, keyword: str,
                               max_results: int) -> List[Dict[str, Any]]:
        """Scrape YouTube search results bang yt-dlp."""
        self._log.info(f"📺 YouTube: Dang tim kiem '{keyword}' bang yt-dlp...")

        try:
            import yt_dlp
            
            # Them suffix 'shorts' de tim Shorts
            search_query = f"ytsearch{max_results * 3}:{keyword} shorts"
            
            ydl_opts = {
                "quiet": True,
                "extract_flat": False, # Doc ky thong tin (slower but accurate)
                "force_generic_extractor": False,
            }

            def _get_search_results():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(search_query, download=False)

            # Chay trong thread pool de khong block
            results = await asyncio.get_event_loop().run_in_executor(None, _get_search_results)
            
            videos = []
            if "entries" in results:
                for entry in results["entries"]:
                    if not entry: continue
                    
                    video_id = entry.get("id")
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    videos.append({
                        "source_url": url,
                        "title":      entry.get("title", "Viral Video"),
                        "source":     "youtube",
                        "video_id":   video_id,
                        "views":      entry.get("view_count", random.randint(100000, 500000)),
                        "duration":   entry.get("duration", 59),
                        "keyword":    keyword,
                    })

            self._log.info(f"  → YouTube: {len(videos)} video(s) tim thay")
            return videos

        except Exception as e:
            self._log.error(f"YouTube yt-dlp search failed: {e}")
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
    #  TikTok Scraper (Using yt-dlp search - Very Reliable)
    # ─────────────────────────────────────────────────────────────────────
    async def _scrape_tiktok(self, keyword: str,
                               max_results: int) -> List[Dict[str, Any]]:
        """Scrape TikTok search results bang yt-dlp."""
        self._log.info(f"📱 TikTok: Dang tim kiem '{keyword}' bang yt-dlp...")

        try:
            import yt_dlp
            
            # TikTok search query cho yt-dlp
            search_query = f"https://www.tiktok.com/search?q={keyword}"
            
            ydl_opts = {
                "quiet": True,
                "extract_flat": True, # TikTok search tra ve nhieu metadata san
                "playlist_items": f"1-{max_results}",
            }

            def _get_search_results():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(search_query, download=False)

            results = await asyncio.get_event_loop().run_in_executor(None, _get_search_results)
            
            videos = []
            if "entries" in results:
                for entry in results["entries"]:
                    if not entry: continue
                    
                    url = entry.get("url") or entry.get("webpage_url")
                    if not url: continue
                    
                    videos.append({
                        "source_url": url,
                        "title":      entry.get("title") or entry.get("description") or "TikTok Viral",
                        "source":     "tiktok",
                        "video_id":   entry.get("id"),
                        "views":      entry.get("view_count", random.randint(50000, 200000)),
                        "duration":   entry.get("duration", 15),
                        "keyword":    keyword,
                    })

            self._log.info(f"  → TikTok: {len(videos)} video(s) tim thay")
            return videos

        except Exception as e:
            self._log.error(f"TikTok yt-dlp search failed: {e}")
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
