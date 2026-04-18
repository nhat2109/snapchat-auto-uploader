import os
import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = PROJECT_ROOT / "uploads" / "video"

class SpotlightHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() == ".mp4":
            # Kiểm tra xem file có nằm trực tiếp trong folder video không (tránh folder completed)
            if file_path.parent != VIDEO_DIR:
                return

            print(f"\n[DETECTED] Phát hiện video mới: {file_path.name}")
            print("[INFO] Đang đợi 5 giây để đảm bảo file đã được copy hoàn tất...")
            time.sleep(5)
            
            print(f"[ACTION] Bắt đầu kích hoạt Robot đăng bài ngầm cho: {file_path.name}")
            try:
                # Gọi script upload ở chế độ headless
                cmd = [
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "run_spotlight_web_upload.py"),
                    "--headless"
                ]
                subprocess.run(cmd, check=True)
                print(f"[SUCCESS] Robot đã xử lý xong file {file_path.name}")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Robot gặp lỗi khi xử lý {file_path.name}: {e}")

def main():
    if not VIDEO_DIR.exists():
        VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    event_handler = SpotlightHandler()
    observer = Observer()
    observer.schedule(event_handler, str(VIDEO_DIR), recursive=False)
    
    print("="*60)
    print("   SNAPCHAT SPOTLIGHT AUTO-PILOT IS RUNNING")
    print("="*60)
    print(f"[STATUS] Đang giám sát thư mục: {VIDEO_DIR}")
    print("[INFO] Ngay khi bạn copy file .mp4 vào đây, Robot sẽ tự động đăng bài.")
    print("[HINT] Nhấn Ctrl+C để dừng Robot.")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[INFO] Đã dừng Robot Auto-Pilot.")
    observer.join()

if __name__ == "__main__":
    main()
