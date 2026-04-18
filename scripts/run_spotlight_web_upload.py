import os
import sys
import time
import argparse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[ERROR] Vui lòng cài đặt playwright: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Tự động đăng Spotlight Snapchat qua Trình duyệt.")
    parser.add_argument("--dir", default="uploads/video", help="Thư mục chứa video (.mp4)")
    parser.add_argument("--tags", default="#trending #spotlight #viral", help="Hashtags cho video")
    parser.add_argument("--save-session", action="store_true", default=True, help="Lưu phiên đăng nhập")
    args = parser.parse_args()

    # Đường dẫn thư mục video
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    video_dir = PROJECT_ROOT / args.dir
    
    if not video_dir.exists():
        print(f"[ERROR] Không tìm thấy thư mục: {video_dir}")
        return 1

    videos = list(video_dir.glob("*.mp4"))
    if not videos:
        print(f"[ERROR] Không tìm thấy file .mp4 nào trong {video_dir}")
        return 1

    print(f"\n======================================================")
    print(f"   SNAPCHAT SPOTLIGHT WEB AUTOMATION")
    print(f"======================================================")
    print(f"[INFO] Tìm thấy {len(videos)} video sẵn sàng tải lên.")
    print(f"[INFO] Tags sẽ dùng: {args.tags}")

    with sync_playwright() as p:
        browser_type = p.chromium
        
        # Đường dẫn lưu session
        session_dir = PROJECT_ROOT / "sessions" / "browser_session"
        session_dir.mkdir(parents=True, exist_ok=True)

        print(f"[INFO] Đang khởi động trình duyệt...")
        # Sử dụng launch_persistent_context để lưu cookie/đăng nhập
        context = browser_type.launch_persistent_context(
            str(session_dir),
            headless=False, # Phải để False để người dùng đăng nhập
            args=["--start-maximized"],
            no_viewport=True
        )

        page = context.new_page()
        page.goto("https://profile.snapchat.com/")

        print("\n" + "!" * 60)
        print(" CHÚ Ý: VUI LÒNG ĐĂNG NHẬP TRÊN CỬA SỔ TRÌNH DUYỆT VỪA MỞ.")
        print(" Script sẽ tự động tiếp tục khi thấy bạn vào được trang tải lên.")
        print("!" * 60 + "\n")

        # Hỗ trợ nhận diện đăng nhập linh hoạt hơn
        print("[INFO] Đang đợi bạn đăng nhập... (Thời hạn 5 phút)")
        print("[TIP] Nếu bạn đã vào đến trang 'Web Uploader' mà script vẫn chưa chạy,")
        print("      hãy quay lại đây và nhấn phím ENTER để bắt đầu ngay!")
        
        # Chạy một luồng đợi song song: hoặc thấy selector, hoặc thấy URL thay đổi, hoặc người dùng nhấn Enter
        login_detected = False
        start_time = time.time()
        
        while time.time() - start_time < 300: # 5 phút
            # 1. Kiểm tra URL (Snapchat Web Uploader thường có '/web-uploader' trong URL)
            if "/web-uploader" in page.url:
                print("[SUCCESS] Đã nhận diện được trang Web Uploader!")
                login_detected = True
                break
            
            # 2. Kiểm tra sự hiện diện của input file
            if page.query_selector("input[type='file']"):
                print("[SUCCESS] Đã tìm thấy khu vực tải lên!")
                login_detected = True
                break
                
            # Đợi một chút rồi kiểm tra tiếp (để không làm treo máy)
            time.sleep(2)
            
            # Lưu ý: Trong môi trường CLI, việc đợi phím bấm mà không làm treo UI trình duyệt khá phức tạp
            # nên tôi ưu tiên nhận diện tự động qua URL và Selector.

        if not login_detected:
            print("[ERROR] Không nhận diện được trạng thái đăng nhập.")
            context.close()
            return 1

        for i, video_path in enumerate(videos):
            print(f"\n[{i+1}/{len(videos)}] Đang xử lý: {video_path.name}")
            
            try:
                # 1. Tải file lên - Đợi input file tồn tại (có thể bị ẩn)
                page.wait_for_selector("input[type='file']", state="attached", timeout=60000)
                file_input = page.query_selector("input[type='file']")
                
                if not file_input:
                    print("[ERROR] Không tìm thấy nút chọn file. Re-loading...")
                    page.reload()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_selector("input[type='file']", state="attached")
                    file_input = page.query_selector("input[type='file']")

                file_input.set_input_files(str(video_path.absolute()))
                print("[INFO] Đang tải file lên máy chủ Snap...")
                
                # 2. Đợi video xử lý
                time.sleep(10) 

                # 3. Điền Caption/Hashtags
                caption_selectors = [
                    "textarea", 
                    "div[contenteditable='true']",
                    "input[placeholder*='Add a description']",
                    "input[placeholder*='caption']"
                ]
                
                caption_found = False
                for selector in caption_selectors:
                    try:
                        # Đợi selector này xuất hiện trong 5s
                        page.wait_for_selector(selector, timeout=5000)
                        field = page.query_selector(selector)
                        if field:
                            field.fill(args.tags)
                            caption_found = True
                            break
                    except:
                        continue
                
                if not caption_found:
                    print("[WARNING] Không tự điền được tags, bạn có thể tự điền nhanh bằng tay.")

                # 4. Đợi một chút để hệ thống nhận diện xong video
                time.sleep(5)

                # 5. Bấm nút Post
                post_button = page.query_selector("button:has-text('Post'), button:has-text('Gửi'), button:has-text('Submit')")
                
                if post_button:
                    # Đợi cho đến khi nút hết bị disabled (video xử lý xong)
                    start_wait = time.time()
                    while not post_button.is_enabled() and time.time() - start_wait < 30:
                        time.sleep(2)
                    
                    if post_button.is_enabled():
                        post_button.click()
                        print(f"[OK] Đã bấm nút đăng video.")
                        
                        # Đợi trang web xử lý xong và quay lại trạng thái sẵn sàng
                        time.sleep(12)
                        
                        # Chuyển về trang upload để chuẩn bị cho video tiếp theo
                        if page.url != "https://profile.snapchat.com/":
                             page.goto("https://profile.snapchat.com/")
                        
                        page.wait_for_load_state("networkidle")
                    else:
                        print("[ERROR] Nút Post vẫn bị xám. Có thể video quá nặng hoặc mạng chậm.")
                        page.reload()
                else:
                    print("[ERROR] Không tìm thấy nút 'Post'.")
                    page.reload()
                    
            except Exception as e:
                print(f"[ERROR] Lỗi trong quá trình automation: {e}")
                print("[INFO] Thử chuyển sang video tiếp theo...")
                page.goto("https://profile.snapchat.com/")
                time.sleep(5)
                continue

        print("\n" + "="*50)
        print("  HOÀN TẤT QUÁ TRÌNH TẢI LÊN SPOTLIGHT!")
        print("======================================================")
        time.sleep(5)
        context.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Đã dừng script theo yêu cầu người dùng.")
        sys.exit(0)
