"""
main.py - Snapchat Automation Platform
Entry point cho CLI và pipeline orchestration
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from typing import Optional, List

# ─── Add project root to path ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─── Load .env ─────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from loguru import logger

from modules.database import Database
from modules.core import BrowserManager, ProxyManager, AccountManager, JobManager
from modules.automation import DittoAutomation, SnapchatAutomation
from modules.utils.logger import setup_logging, PipelineLogger
from modules.utils.retry import async_random_delay


# ═══════════════════════════════════════════════════════════════════════════
#  DISCLAIMER
# ═══════════════════════════════════════════════════════════════════════════

DISCLAIMER = """
⚠️  DISCLAIMER - CẢNH BÁO QUAN TRỌNG ⚠️
────────────────────────────────────────────────────────────
Công cụ này tự động hóa các thao tác trên Ditto Music và Snapchat.

Việc sử dụng công cụ này có thể vi phạm Điều khoản Dịch vụ (Terms of Service)
của các nền tảng liên quan.

Rủi ro bao gồm nhưng không giới hạn:
  • Tài khoản bị khóa hoặc banned vĩnh viễn
  • Hành động vi phạm bản quyền
  • IP bị chặn bởi nền tảng

Người dùng TỰ CHỊU TRÁCH NHIỆM hoàn toàn khi sử dụng công cụ này.
────────────────────────────────────────────────────────────
"""


# ═══════════════════════════════════════════════════════════════════════════
#  CORE PIPELINE RUNNER
# ═══════════════════════════════════════════════════════════════════════════

class AutomationPipeline:
    """
    Điều phối toàn bộ pipeline:
    Step 1: Upload nhạc lên Ditto
    Step 2: Upload video lên Snapchat + thêm nhạc
    """

    def __init__(self,
                 db: Optional[Database] = None,
                 headless: bool = True,
                 screenshots_dir: str = "screenshots"):
        self.db             = db
        self.headless       = headless
        self.screenshots_dir = screenshots_dir

        self.browser     : Optional[BrowserManager] = None
        self.proxy_mgr   : Optional[ProxyManager]  = None
        self.account_mgr : Optional[AccountManager] = None
        self.job_mgr     : Optional[JobManager]    = None

    async def initialize(self):
        """Khởi tạo toàn bộ hệ thống."""
        logger.info("🚀 Khởi tạo Automation Pipeline...")

        self.browser     = BrowserManager(headless=self.headless,
                                          screenshots_dir=self.screenshots_dir)
        self.proxy_mgr   = ProxyManager(self.db)
        self.account_mgr = AccountManager(self.db)
        self.job_mgr     = JobManager(self.db)

        await self.browser.start()
        logger.info("✅ Browser started")

        # Load proxies
        if self.db:
            self.proxy_mgr.load_proxies_from_db()
        logger.info("✅ Proxy Manager initialized")

    async def shutdown(self):
        """Dọn dẹp resources."""
        if self.browser:
            await self.browser.stop()
        logger.info("✅ Pipeline shutdown complete")

    async def run_single(self,
                          snap_username: str,
                          snap_password: str,
                          video_path: str,
                          music_path: str,
                          music_title: str,
                          artist: str,
                          ditto_username: Optional[str] = None,
                          ditto_password: Optional[str] = None,
                          title: Optional[str] = None,
                          description: Optional[str] = None,
                          tags: Optional[str] = None,
                          proxy_url: Optional[str] = None,
                          account_id: Optional[int] = None) -> dict:
        """
        Chạy pipeline cho 1 job cụ thể (từ GUI hoặc CLI).
        Trả về dict kết quả với status và message.
        """

        # Tạo pipeline logger
        plog = PipelineLogger(job_id=account_id, account_id=account_id, db=self.db)

        try:
            plog.section("SNAPCHAT AUTOMATION PIPELINE")
            plog.info(f"Video: {video_path}")
            plog.info(f"Nhạc: {music_path}")

            result = {"success": False, "steps": {}, "error": None}

            # ── Step 1: Upload nhạc lên Ditto ──────────────────────────────
            if ditto_username and ditto_password and music_path:
                plog.step("STEP 1: Upload nhạc lên Ditto Music")
                ditto = DittoAutomation(self.browser, plog)
                ditto_result = await ditto.run(
                    username=ditto_username,
                    password=ditto_password,
                    music_file=music_path,
                    music_title=music_title,
                    artist=artist,
                    account_id=account_id,
                )
                result["steps"]["ditto"] = ditto_result
                if not ditto_result.get("success"):
                    plog.warn(f"Ditto upload failed: {ditto_result.get('message')}")
                    # Vẫn tiếp tục (có thể nhạc đã upload rồi)
                else:
                    plog.info("✅ Step 1 hoàn tất: Nhạc đã upload lên Ditto")
            else:
                plog.info("ℹ️ Bỏ qua Ditto (không có credentials)")
                result["steps"]["ditto"] = {"success": True, "skipped": True}

            # ── Step 2: Upload video lên Snapchat ────────────────────────────
            plog.step("STEP 2: Upload video lên Snapchat")
            snap = SnapchatAutomation(self.browser, plog)
            snap_result = await snap.run(
                username=snap_username,
                password=snap_password,
                video_path=video_path,
                music_title=music_title,
                artist=artist,
                title=title,
                description=description,
                tags=tags,
                account_id=account_id,
                headless=self.headless,
            )
            result["steps"]["snapchat"] = snap_result

            if snap_result.get("success"):
                result["success"] = True
                plog.info("🎉 PIPELINE HOÀN TẤT!")
                plog.info(f"   Video: {title or os.path.basename(video_path)}")
                plog.info(f"   Nhạc:  {music_title} - {artist}")
            else:
                result["error"] = snap_result.get("message", "Unknown error")
                plog.error(f"Pipeline failed: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return {"success": False, "error": str(e), "steps": {}}


# ═══════════════════════════════════════════════════════════════════════════
#  GUI RUNNER (gọi từ gui.py)
# ═══════════════════════════════════════════════════════════════════════════

async def run_pipeline_from_gui(gui_ref) -> dict:
    """
    Chạy pipeline lấy dữ liệu từ GUI.
    gui_ref: instance của App (gui.py)
    """
    pipeline = AutomationPipeline(headless=False, screenshots_dir="screenshots")
    await pipeline.initialize()

    try:
        # Lấy dữ liệu từ GUI
        snap_user     = gui_ref._get_var("snap_user")
        snap_pass     = gui_ref._get_var("snap_pass")
        video_path    = gui_ref._get_var("video_file")
        music_path    = gui_ref._get_var("music_file")
        music_title   = gui_ref._get_var("music_title") or gui_ref._get_var("music_title_field")
        artist        = gui_ref._get_var("artist") or gui_ref._get_var("music_artist")
        ditto_user    = gui_ref._get_var("ditto_user")
        ditto_pass    = gui_ref._get_var("ditto_pass")
        title         = gui_ref._get_var("video_title")
        description   = gui_ref._get_var("video_desc")
        tags          = gui_ref._get_var("video_tags")

        result = await pipeline.run_single(
            snap_username=snap_user,
            snap_password=snap_pass,
            video_path=video_path,
            music_path=music_path,
            music_title=music_title or Path(video_path).stem,
            artist=artist or "Unknown Artist",
            ditto_username=ditto_user,
            ditto_password=ditto_pass,
            title=title,
            description=description,
            tags=tags,
        )
        return result

    finally:
        await pipeline.shutdown()


# ═══════════════════════════════════════════════════════════════════════════
#  CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

def cmd_init_db(args):
    """Khởi tạo database schema."""
    print("🔧 Đang khởi tạo database...")
    db = Database()
    db.init_schema()
    print("✅ Database schema đã tạo xong.")
    print("   Các bảng: accounts, jobs, logs, proxies")

    # Tạo thư mục cần thiết
    for d in ["logs", "screenshots", "uploads/music", "uploads/video"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("✅ Thư mục đã tạo: logs/, screenshots/, uploads/")

    return db


def cmd_add_account(args):
    """Thêm tài khoản vào DB."""
    db = Database()
    db.init_schema()
    try:
        acc = db.create_account(
            username=args.username,
            password=args.password,
            proxy=args.proxy,
            status="pending",
        )
        print(f"✅ Đã thêm account: {args.username} (ID: {acc.id})")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def cmd_add_job(args):
    """Thêm job vào queue."""
    db = Database()
    db.init_schema()
    try:
        job = db.create_job(
            video_path=args.video,
            music_path=args.music,
            title=args.title,
            music_title=args.music_title,
            artist=args.artist,
        )
        print(f"✅ Đã thêm job: #{job.id} | {args.title or args.video}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")


def cmd_list(args):
    """Liệt kê jobs hoặc accounts."""
    db = Database()
    db.init_schema()

    if args.type == "jobs":
        jobs = db.get_all_jobs(status=args.status)
        if not jobs:
            print("Không có job nào.")
        else:
            print(f"{'ID':<5} {'Title':<30} {'Status':<12} {'Retry':<6} {'Created'}")
            print("-" * 80)
            for j in jobs:
                print(f"{j.id:<5} {str(j.title or 'Untitled'):<30} {j.status:<12} {j.retry_count:<6} {str(j.created_at)[:19]}")

    elif args.type == "accounts":
        accs = db.get_all_accounts(status=args.status)
        if not accs:
            print("Không có account nào.")
        else:
            print(f"{'ID':<5} {'Username':<30} {'Status':<12} {'Proxy'}")
            print("-" * 75)
            for a in accs:
                print(f"{a.id:<5} {a.username:<30} {a.status:<12} {a.proxy or 'N/A'}")

    elif args.type == "stats":
        stats = db.get_stats()
        print("\n📊 THỐNG KÊ HỆ THỐNG")
        print("─" * 40)
        print(f"  Jobs:   {stats['jobs']['total']} total | "
              f"{stats['jobs']['pending']} pending | "
              f"{stats['jobs']['done']} done | "
              f"{stats['jobs']['failed']} failed")
        print(f"  Accounts: {stats['accounts']['total']} total | "
              f"{stats['accounts']['active']} active")
        print(f"  Proxies:  {stats['proxies']['total']} total")

    elif args.type == "logs":
        logs = db.get_recent_logs(limit=args.limit)
        if not logs:
            print("Không có log nào.")
        else:
            for l in logs:
                ts = str(l.created_at)[:19]
                print(f"[{ts}] [{l.level:<5}] {l.message}")


def cmd_run_queue(args):
    """Chạy job queue."""
    print(DISCLAIMER)
    print("⏳ Đang khởi động worker...")

    db = Database()
    db.init_schema()

    pipeline = AutomationPipeline(db=db, headless=args.headless)
    asyncio.run(_run_queue_async(pipeline, args))


async def _run_queue_async(pipeline: AutomationPipeline, args):
    await pipeline.initialize()
    browser = pipeline.browser
    account_mgr = pipeline.account_mgr
    job_mgr = pipeline.job_mgr

    try:
        # Load jobs
        if args.job_id:
            jobs = [job_mgr.get_job(args.job_id)]
        else:
            jobs = job_mgr.load_pending(limit=args.limit)

        print(f"📋 Loaded {len(jobs)} job(s)")

        async def job_callback(jm, job, bm):
            # Lấy account
            account = account_mgr.get_next_available()
            if not account:
                print("⚠️ Không có account khả dụng!")
                return False

            # Lấy proxy
            proxies = pipeline.proxy_mgr.load_proxies_from_db()
            proxy_info = pipeline.proxy_mgr.get_proxy_for_account(
                account.id, proxies=proxies
            )
            proxy_url = proxy_info["server"] if proxy_info else None

            # Build metadata từ job
            plog = PipelineLogger(job_id=job.id, account_id=account.id, db=db)

            ditto_ok  = True
            if job.music_path:
                ditto = DittoAutomation(bm, plog)
                ditto_res = await ditto.run(
                    username="", password="",  # Cần credentials từ job hoặc account
                    music_file=job.music_path,
                    music_title=job.music_title or "",
                    artist=job.artist or "",
                    account_id=account.id,
                )
                ditto_ok = ditto_res.get("success", True)

            snap = SnapchatAutomation(bm, plog)
            snap_res = await snap.run(
                username=account.username,
                password=account.password,
                video_path=job.video_path,
                music_title=job.music_title or "",
                artist=job.artist or "",
                title=job.title,
                description=job.description,
                tags=job.tags,
                account_id=account.id,
                headless=args.headless,
            )
            return snap_res.get("success", False)

        results = await job_mgr.run_queue(browser, account_mgr, job_callback)
        print(f"\n✅ Queue hoàn tất: {results['done']} done, {results['failed']} failed")

    finally:
        await pipeline.shutdown()


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Snapchat Automation Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python main.py init-db
  python main.py add-account --username user --password pass --proxy "ip:port"
  python main.py add-job --video "video.mp4" --music "song.mp3" --title "My Video"
  python main.py list --type stats
  python main.py run
  python main.py gui
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db
    subparsers.add_parser("init-db", help="Khởi tạo database schema")

    # add-account
    acc_parser = subparsers.add_parser("add-account", help="Thêm tài khoản")
    acc_parser.add_argument("--username", "-u", required=True, help="Tài khoản Snapchat")
    acc_parser.add_argument("--password", "-p", required=True, help="Mật khẩu")
    acc_parser.add_argument("--proxy", help="Proxy URL (ip:port:user:pass)")

    # add-job
    job_parser = subparsers.add_parser("add-job", help="Thêm job vào queue")
    job_parser.add_argument("--video", "-v", required=True, help="Đường dẫn file video")
    job_parser.add_argument("--music", "-m", help="Đường dẫn file nhạc")
    job_parser.add_argument("--title", "-t", help="Tiêu đề video")
    job_parser.add_argument("--music-title", help="Tên bài hát")
    job_parser.add_argument("--artist", "-a", help="Tên nghệ sĩ")

    # list
    list_parser = subparsers.add_parser("list", help="Liệt kê dữ liệu")
    list_parser.add_argument("--type", "-t", choices=["jobs", "accounts", "stats", "logs"],
                            default="stats", help="Loại dữ liệu")
    list_parser.add_argument("--status", "-s", help="Filter theo status")
    list_parser.add_argument("--limit", "-l", type=int, default=50, help="Giới hạn kết quả")

    # run
    run_parser = subparsers.add_parser("run", help="Chạy job queue worker")
    run_parser.add_argument("--job-id", type=int, help="Chạy 1 job cụ thể")
    run_parser.add_argument("--limit", type=int, default=10, help="Giới hạn số job")
    run_parser.add_argument("--headless", action="store_true", default=True, help="Chạy headless")
    run_parser.add_argument("--visible", action="store_false", dest="headless",
                           help="Hiển thị trình duyệt")

    # gui
    subparsers.add_parser("gui", help="Chạy giao diện GUI")

    args = parser.parse_args()

    # ── Dispatch commands ─────────────────────────────────────────────────
    if args.command == "init-db":
        cmd_init_db(args)

    elif args.command == "add-account":
        cmd_add_account(args)

    elif args.command == "add-job":
        cmd_add_job(args)

    elif args.command == "list":
        cmd_list(args)

    elif args.command == "run":
        cmd_run_queue(args)

    elif args.command == "gui":
        print("🚀 Đang khởi động GUI...")
        from gui import App
        app = App()
        app.mainloop()


if __name__ == "__main__":
    print(DISCLAIMER)
    main()