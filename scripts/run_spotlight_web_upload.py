import os
import sys
import time
import shutil
import argparse
from pathlib import Path

# Ho tro tieng Viet co dau tren Windows Terminal
if sys.platform == "win32":
    import io
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[ERROR] Vui lòng cài đặt playwright: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

def get_caption(video_path: Path, default_tags: str) -> str:
    """Tìm caption từ file .txt trùng tên video."""
    caption_file = video_path.with_suffix(".txt")
    if caption_file.exists():
        try:
            with open(caption_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    print(f"[INFO] Đã tìm thấy caption riêng cho {video_path.name}")
                    return content
        except Exception as e:
            print(f"[WARNING] Lỗi khi đọc file caption: {e}")
    return default_tags

def main():
    parser = argparse.ArgumentParser(description="Tự động đăng Spotlight Snapchat.")
    parser.add_argument("--dir", default="uploads/video", help="Thư mục chứa video (.mp4)")
    parser.add_argument("--file", default=None, help="Đường dẫn trực tiếp đến 1 file video cụ thể")
    parser.add_argument("--tags", default="#trending #spotlight #viral", help="Hashtags mặc định")
    parser.add_argument("--headless", action="store_true", help="Chạy ẩn danh trình duyệt")
    parser.add_argument("--save-session", action="store_true", default=True, help="Lưu phiên đăng nhập")
    parser.add_argument("--cleanup", action="store_true", help="Xóa file video sau khi đăng thành công (thay vì di chuyển)")
    args = parser.parse_args()

    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    if args.file:
        video_path = Path(args.file)
        if not video_path.exists():
            print(f"[ERROR] Không tìm thấy file: {args.file}")
            return 1
        videos = [video_path]
        # Đặt lại video_dir để completed_dir đúng chỗ
        video_dir = video_path.parent
        completed_dir = video_dir / "completed"
        completed_dir.mkdir(exist_ok=True)
    else:
        # Đường dẫn thư mục video
        video_dir = PROJECT_ROOT / args.dir
        completed_dir = video_dir / "completed"
        completed_dir.mkdir(exist_ok=True)
        
        if not video_dir.exists():
            print(f"[ERROR] Không tìm thấy thư mục: {video_dir}")
            return 1
        videos = [v for v in video_dir.glob("*.mp4") if v.parent == video_dir]
    
    if not videos:
        print(f"[INFO] Không tìm thấy video mới nào.")
        return 0

    print(f"\n======================================================")
    print(f"   SNAPCHAT SPOTLIGHT SUPER AUTOMATION")
    print(f"======================================================")
    print(f"[INFO] Tìm thấy {len(videos)} video mới.")
    print(f"[INFO] Chế độ chạy ngầm (Headless): {args.headless}")

    with sync_playwright() as p:
        browser_type = p.chromium
        session_dir = PROJECT_ROOT / "sessions" / "browser_session"
        session_dir.mkdir(parents=True, exist_ok=True)

        print(f"[INFO] Dang khoi dong trinh duyet...")
        context = browser_type.launch_persistent_context(
            str(session_dir),
            headless=args.headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=["--start-maximized"] if not args.headless else [],
            no_viewport=True if not args.headless else False
        )

        page = context.new_page()
        page.goto("https://profile.snapchat.com/")

        # Nhận diện đăng nhập
        login_detected = False
        start_time = time.time()
        # Tang thoi gian doi cho headless len 90s cho chac chan
        max_wait = 300 if not args.headless else 90 

        if not args.headless:
            print("\n" + "!" * 60)
            print(" CHU AY: VUI LONG DANG NHAP TREN CUA SO TRINH DUYET (Neu can).")
            print("!" * 60 + "\n")

        while time.time() - start_time < max_wait:
            curr_url = page.url
            # Kiem tra URL uploader hoac su hien dien cua nut Upload/Avatar
            if "/web-uploader" in curr_url or page.query_selector("input[type='file']") or page.query_selector("button:has-text('Upload')") or page.query_selector(".profile-info"):
                login_detected = True
                break
            
            # Neu thay nut Login hoac URL chua /login thi chac chan chua login
            if "/login" in curr_url or page.query_selector("button[type='submit']") and "Log In" in page.content():
                if args.headless:
                    print("[WARNING] Robot phat hien trang Dang nhap. Session da het han hoac chua co.")
                    break
            
            time.sleep(3)

        if not login_detected:
            print("[ERROR] Không nhận diện được trạng thái đăng nhập. Vui lòng chạy ở chế độ UI trước.")
            context.close()
            return 1

        for i, video_path in enumerate(videos):
            print(f"\n[{i+1}/{len(videos)}] Đang xử lý: {video_path.name}")
            video_caption = get_caption(video_path, args.tags)
            
            try:
                page.wait_for_selector("input[type='file']", state="attached", timeout=60000)
                file_input = page.query_selector("input[type='file']")
                file_input.set_input_files(str(video_path.absolute()))
                
                print("[INFO] Đang tải lên và chờ xử lý...")
                time.sleep(12) # Đợi render video

                # Điền Caption
                caption_selectors = ["textarea", "div[contenteditable='true']", "input[placeholder*='description']"]
                for selector in caption_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        field = page.query_selector(selector)
                        if field:
                            field.fill(video_caption)
                            break
                    except: continue

                # Bấm nút Post
                post_button = page.query_selector("button:has-text('Post'), button:has-text('Gửi'), button:has-text('Submit')")
                if post_button:
                    # Chờ nút enable
                    for _ in range(15):
                        if post_button.is_enabled(): break
                        time.sleep(2)
                    
                    if post_button.is_enabled():
                        post_button.click()
                        print(f"[SUCCESS] Đã đăng video!")
                        time.sleep(15) # Chờ hoàn tất
                        
                        if args.cleanup:
                            try:
                                video_path.unlink()
                                # Xoa file caption neu co
                                caption_f = video_path.with_suffix(".txt")
                                if caption_f.exists(): caption_f.unlink()
                                print(f"[INFO] Da xoa file sau khi dang de tiet kiem dung luong.")
                            except Exception as e:
                                print(f"[WARNING] Khong the xoa file: {e}")
                        else:
                            # Di chuyển vào folder completed
                            shutil.move(str(video_path), str(completed_dir / video_path.name))
                            print(f"[INFO] Đã chuyển {video_path.name} vào thư mục 'completed'.")
                        
                        # Chuyển về trang upload
                        page.goto("https://profile.snapchat.com/")
                        page.wait_for_load_state("networkidle")
                    else:
                        print("[ERROR] Nút Post bị vô hiệu hóa.")
                        page.reload()
                else:
                    print("[ERROR] Không thấy nút Post.")
                    page.reload()
                    
            except Exception as e:
                print(f"[ERROR] Sự cố: {e}")
                page.goto("https://profile.snapchat.com/")
                continue

        context.close()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[INFO] Da dung script theo yeu cau.")
        sys.exit(0)
