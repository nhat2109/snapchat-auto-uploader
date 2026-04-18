import os
import sys
import time
import shutil
import argparse
from pathlib import Path

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
    parser.add_argument("--tags", default="#trending #spotlight #viral", help="Hashtags mặc định")
    parser.add_argument("--headless", action="store_true", help="Chạy ẩn danh trình duyệt")
    parser.add_argument("--save-session", action="store_true", default=True, help="Lưu phiên đăng nhập")
    args = parser.parse_args()

    # Đường dẫn thư mục video
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    video_dir = PROJECT_ROOT / args.dir
    completed_dir = video_dir / "completed"
    completed_dir.mkdir(exist_ok=True)
    
    if not video_dir.exists():
        print(f"[ERROR] Không tìm thấy thư mục: {video_dir}")
        return 1

    videos = [v for v in video_dir.glob("*.mp4") if v.parent == video_dir]
    if not videos:
        print(f"[INFO] Không tìm thấy video mới nào trong {video_dir}")
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

        print(f"[INFO] Đang khởi động trình duyệt...")
        context = browser_type.launch_persistent_context(
            str(session_dir),
            headless=args.headless,
            args=["--start-maximized"] if not args.headless else [],
            no_viewport=True if not args.headless else False
        )

        page = context.new_page()
        page.goto("https://profile.snapchat.com/")

        # Nhận diện đăng nhập
        login_detected = False
        start_time = time.time()
        max_wait = 300 if not args.headless else 45 # Nếu ẩn danh thì đợi ít hơn vì giả định đã có session

        if not args.headless:
            print("\n" + "!" * 60)
            print(" CHÚ Ý: VUI LÒNG ĐĂNG NHẬP TRÊN CỬA SỔ TRÌNH DUYỆT (Nếu cần).")
            print("!" * 60 + "\n")

        while time.time() - start_time < max_wait:
            if "/web-uploader" in page.url or page.query_selector("input[type='file']"):
                login_detected = True
                break
            time.sleep(2)

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
    sys.exit(main())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Đã dừng script theo yêu cầu người dùng.")
        sys.exit(0)
