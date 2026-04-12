"""
modules/automation/downloader.py
Video Downloader - Tải video từ YouTube, TikTok, Douyin bằng yt-dlp
Theo hethong.txt - Section 2.2
"""

import os
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from loguru import logger

from modules.utils.logger import PipelineLogger
from modules.utils.retry import async_random_delay


class VideoDownloader:
    """
    Download videos sử dụng yt-dlp.
    Hỗ trợ: YouTube, TikTok, Douyin
    """

    def __init__(self,
                 output_dir: str = "uploads/video",
                 thumbnails: bool = True,
                 quality: str = "best[height<=720][ext=mp4]"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails = thumbnails
        self.quality    = quality
        self._log       = None

    # ─────────────────────────────────────────────────────────────────────
    #  Download single video
    # ─────────────────────────────────────────────────────────────────────
    async def download(self,
                       url: str,
                       save_path: Optional[str] = None,
                       pipeline_logger: Optional[PipelineLogger] = None,
                       proxy_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Download 1 video từ URL.

        Returns:
            dict với keys: success, local_path, title, duration, error
        """
        self._log = pipeline_logger or PipelineLogger()

        result = {
            "success": False,
            "local_path": None,
            "title": None,
            "duration": None,
            "error": None,
        }

        try:
            import yt_dlp

            if not save_path:
                save_path = str(self.output_dir / "%(title)s-%(id)s.%(ext)s")

            ydl_opts = {
                "outtmpl": save_path,
                "format": self.quality,
                "noplaylist": True,
                "quiet": False,
                "no_color": True,
                "extract_flat": False,
            }

            if proxy_url:
                ydl_opts["proxy"] = proxy_url

            if self.thumbnails:
                ydl_opts["writethumbnail"] = True

            self._log.info(f"📥 Downloading: {url}")

            # yt-dlp là sync — chạy trong thread pool để không block event loop
            def _sync_download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info

            info = await asyncio.get_event_loop().run_in_executor(
                None, _sync_download
            )

            if info:
                result["success"]   = True
                result["title"]     = info.get("title", "")
                result["duration"]  = info.get("duration", 0)
                # Tìm file đã lưu
                if os.path.exists(save_path):
                    result["local_path"] = save_path
                else:
                    # yt-dlp có thể đổi tên file
                    base = save_path.replace("%(ext)s", "mp4").replace("%(title)s", "").replace("%(id)s", "")
                    for f in Path(self.output_dir).glob("*"):
                        if info.get("title", "") in str(f) or info.get("id", "") in str(f):
                            result["local_path"] = str(f)
                            break

                self._log.info(f"✅ Downloaded: {result['title']} → {result['local_path']}")
            else:
                result["error"] = "yt-dlp returned no info"

        except Exception as e:
            result["error"] = str(e)
            self._log.error(f"Download failed: {e}")

        await async_random_delay(2.0, 4.0)
        return result

    # ─────────────────────────────────────────────────────────────────────
    #  Download batch
    # ─────────────────────────────────────────────────────────────────────
    async def download_batch(self,
                              urls: List[Dict[str, Any]],
                              pipeline_logger: Optional[PipelineLogger] = None,
                              proxy_url: Optional[str] = None,
                              max_concurrent: int = 2) -> List[Dict[str, Any]]:
        """
        Download nhiều videos đồng thời (giới hạn concurrency).

        Args:
            urls           : List[dict] — mỗi dict có 'source_url', 'title', ...
            max_concurrent : Tối đa bao nhiêu task cùng lúc
        """
        self._log = pipeline_logger or PipelineLogger()
        self._log.section("VIDEO DOWNLOAD BATCH")

        semaphore = asyncio.Semaphore(max_concurrent)
        results   = []

        async def _download_one(item: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                url = item.get("source_url", item.get("url", ""))
                return await self.download(url, pipeline_logger=pipeline_logger,
                                          proxy_url=proxy_url)

        tasks = [ _download_one(u) for u in urls ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        self._log.info(f"✅ Batch hoàn tất: {success_count}/{len(urls)} videos")

        return results

    # ─────────────────────────────────────────────────────────────────────
    #  Get video info (không download)
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    async def get_info(url: str, proxy_url: Optional[str] = None) -> Optional[Dict]:
        """Lấy thông tin video mà không download."""
        try:
            import yt_dlp
            opts = {"noplaylist": True, "quiet": True}
            if proxy_url:
                opts["proxy"] = proxy_url
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            logger.error(f"Get info failed: {e}")
            return None
