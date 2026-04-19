import os
import asyncio
import random
from pathlib import Path
from dotenv import load_dotenv
import sys

# Ho tro tieng Viet co dau tren Windows Terminal
if sys.platform == "win32":
    import io
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from modules.automation.scraper import ViralVideoScraper
from modules.automation.download import VideoDownloader
from modules.automation.processor import VideoProcessor
from modules.core.browser import BrowserManager
from modules.utils.logger import setup_logging, PipelineLogger

async def main():
    setup_logging()
    load_dotenv()
    plog = PipelineLogger()
    plog.section("VIRAL MACHINE 2.0 - SMART COLLECTOR")
    
    # 1. Nhap tu khoa
    query = input("\n[?] Ban muon tim video ve chu de gi?: ").strip()
    if not query:
        query = "satisfying asmr"
        print(f"[INFO] Mac dinh lay chu de: {query}")
    
    keywords = [query]

    # 2. Nhap so luong
    target_count_str = input("\n[?] Ban muon tai ve bao nhieu video?: ").strip()
    try:
        target_count = int(target_count_str) if target_count_str else 3
    except:
        target_count = 3
        print(f"[INFO] So luong khong hop le, mac dinh lay: {target_count}")

    # 3. Nhap nguong view
    min_views_str = input("[?] Nguong view toi thieu (mac dinh 1000): ").strip()
    try:
        min_views = int(min_views_str) if min_views_str else 1000
    except:
        min_views = 1000

    # 4. Chon nguon
    print("\n------------------------------------------------------")
    print(" CHON NGUON VIDEO:")
    print(" [1] TikTok")
    print(" [2] YouTube")
    print(" [3] Facebook Reels")
    print(" [4] TAT CA")
    print("------------------------------------------------------")
    s_choice = input("Chon nguon (vi du: 1,2): ").strip() or "4"
    
    sources = []
    if "1" in s_choice: sources.append("tiktok")
    if "2" in s_choice: sources.append("youtube")
    if "3" in s_choice: sources.append("facebook")
    if "4" in s_choice or not sources: sources = ["tiktok", "youtube", "facebook"]

    # 5. Chon che do
    print("\n------------------------------------------------------")
    print(" CHON CHE DO VAN HANH:")
    print(" [1] TU DONG (Robot tu chon video nhieu Engagement nhat)")
    print(" [2] THU CONG (Ban tu chon tu danh sach)")
    print("------------------------------------------------------")
    mode = input("Chon (1/2): ").strip() or "1"
    
    # Pool size: Scrape gap 5 lan so luong can (tang ty le tim thay video viral)
    max_to_scrape = max(30, target_count * 5)
    music_file = os.getenv("MUSIC_FILE", "uploads/music/default.mp3")
    
    # 6. Khoi tao Scraper
    scraper = ViralVideoScraper()
    
    print(f"\n[INFO] Dang săn lùng video viral cho: '{query}'...")
    videos = await scraper.scrape(keywords=keywords, max_results=max_to_scrape, min_views=min_views, sources=sources)
    
    if not videos:
        plog.error("❌ Khong tim thay video nao dat chuẩn viral.")
        return

    # 6. Sap xep theo Engagement (Views + Likes*5 + Shares*10) - Giam dan
    def get_engagement(v):
        return v.get("views", 0) + (v.get("likes", 0) * 5) + (v.get("shares", 0) * 10)

    videos.sort(key=get_engagement, reverse=True)

    selected_videos = []
    if mode == "2":
        # Hien thi bang danh sach
        print("\n" + "="*110)
        print(f"{'STT':<5} | {'VIEW':<10} | {'LIKE':<8} | {'SHARE':<8} | {'NGUON':<8} | {'TEN VIDEO'}")
        print("-" * 110)
        for i, v in enumerate(videos):
            view_str = f"{v['views']:,}" if v.get('views') else "0"
            like_str = f"{v['likes']:,}" if v.get('likes') else "0"
            share_str = f"{v['shares']:,}" if v.get('shares') else "0"
            print(f"[{i+1:<3}] | {view_str:<10} | {like_str:<8} | {share_str:<8} | {v['source'].upper():<8} | {v['title'][:45]}...")
        print("="*110)
        
        choices = input(f"\n[?] Nhap STT cac video ban muon lay (ví dụ: 1,3,5) \nHoac Go 'ALL' de lay top {target_count}: ").strip().upper()
        
        if choices == "ALL":
            selected_videos = videos[:target_count]
        else:
            try:
                indices = [int(x.strip()) - 1 for x in choices.split(",") if x.strip().isdigit()]
                selected_videos = [videos[i] for i in indices if 0 <= i < len(videos)]
            except:
                print(f"[ERROR] Lua chon khong hop le. Lay top {target_count}.")
                selected_videos = [videos[0]]
    else:
        # Che do tu dong: Lay dung so luong yeu cau
        selected_videos = videos[:target_count]
        print(f"[INFO] Da tu dong chon {len(selected_videos)} video co engagement cao nhat.")

    if not selected_videos:
        print("[INFO] Khong co video nao duoc chon.")
        return

    downloader = VideoDownloader(output_dir="uploads/video")
    processor = VideoProcessor(output_dir="uploads/processed")
    
    plog.info(f"🚀 Bat dau xu ly {len(selected_videos)} video...")
    
    for idx, v in enumerate(selected_videos):
        plog.step(f"XU LY #{idx+1}: {v['title']}")
        
        # Step A: Download
        dl_res = await downloader.download(v['source_url'])
        if not dl_res['success'] or not dl_res['local_path']:
            continue
            
        video_path = Path(dl_res['local_path'])
        
        # Luu caption vao file .txt de Spotlight dung
        caption_file = video_path.with_suffix(".txt")
        with open(caption_file, "w", encoding="utf-8") as f:
            f.write(f"{v['title']} #viral #trending #{query.replace(' ', '')}")

        # Step B: AI Edit
        plog.info(f"   🎭 Dang 'AI Re-Edit' de tranh ban quyen...")
        proc_res = await processor.process(
            video_path=video_path,
            add_zoom=True,
            zoom_factor=1.1,
            add_blur=True,
            duration_sec=min(v.get('duration', 60), 15.0), # Lấy 15s tiêu biểu
            music_path=music_file if os.path.exists(music_file) else None
        )
        
        if proc_res['success']:
            plog.info(f"   ✅ HOAN TAT: {proc_res['output_path']}")
            # Xoa file goc de tiet kiem cho (Yeu cau truoc do)
            try: video_path.unlink()
            except: pass
        else:
            plog.error(f"   ❌ Edit that bai: {proc_res['error']}")

    plog.section("DA XU LY XONG. VIDEO DA SAN SANG DE DANG!")
    print("\n[SUCCESS] Video da duoc edit va luu tai: uploads/processed/")
    print("[HINT] Ban co the vao folder do de kiem tra thanh qua.")

if __name__ == "__main__":
    asyncio.run(main())
