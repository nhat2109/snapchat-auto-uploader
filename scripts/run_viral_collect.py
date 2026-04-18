import os
import asyncio
import random
from pathlib import Path
from dotenv import load_dotenv

from modules.automation.scraper import ViralVideoScraper
from modules.automation.download import VideoDownloader
from modules.automation.processor import VideoProcessor
from modules.core.browser import BrowserManager
from modules.utils.logger import setup_logging, PipelineLogger

async def main():
    setup_logging()
    load_dotenv()
    
    # 1. Cau hinh
    keywords = os.getenv("KEYWORDS", "funny cats,satisfying videos").split(",")
    music_file = os.getenv("MUSIC_FILE", "uploads/music/default.mp3")
    max_videos = 2
    plog = PipelineLogger()
    plog.section("VIRAL MACHINE - COLLECTOR & PROCESSOR")
    
    # 2. Khoi tao modules
    scraper = ViralVideoScraper()
    # 1. Cau hinh
    keywords = ["funny cats", "satisfying asmr", "life hacks"]
    music_file = os.getenv("MUSIC_FILE", "uploads/music/default.mp3")
    max_videos = 3
    
    # 2. Scrape (Ket hop ca YouTube va TikTok)
    print(f"🔍 Dang tim kiem video cho tu khoa: {keywords}")
    videos = await scraper.scrape(keywords=keywords, max_results=max_videos, sources=["tiktok", "youtube"])
    
    if not videos:
        plog.error("❌ Khong tim thay video nao phu hop.")
        return

    downloader = VideoDownloader(output_dir="uploads/video")
    processor = VideoProcessor(output_dir="uploads/processed")
    
    plog.info(f"✅ Tim thay {len(videos)} video. Bat dau tai ve...")
    
    for idx, v in enumerate(videos):
        plog.step(f"VIDEO #{idx+1}: {v['title']}")
        
        # Step A: Download
        dl_res = await downloader.download(v['source_url'])
        if not dl_res['success'] or not dl_res['local_path']:
            plog.warn(f"   Jump qua video nay vi tai that bai.")
            continue
            
        video_path = dl_res['local_path']
        
        # Step B: AI Edit (Processor)
        plog.info(f"   🎭 Dang 'Hoa than' video (AI Edit)...")
        # Chung ta se zoom 1.1x va blur de tranh ban quyen
        proc_res = await processor.process(
            video_path=video_path,
            add_zoom=True,
            zoom_factor=1.1,
            add_blur=True,
            duration_sec=10.0, # Lay 10 giay viral nhat
            music_path=music_file if os.path.exists(music_file) else None
        )
        
        if proc_res['success']:
            plog.info(f"   ✅ HOAN TAT: {proc_res['output_path']}")
        else:
            plog.error(f"   ❌ Edit that bai: {proc_res['error']}")

    plog.section("DA XU LY XONG TOAN BO")
    print("\n[SUCCESS] Video da duoc edit va luu tai: uploads/processed/")
    print("[HINT] Ban co the vao folder do de kiem tra thanh qua.")

if __name__ == "__main__":
    asyncio.run(main())
