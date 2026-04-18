import os
import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = PROJECT_ROOT / "uploads" / "video"
PROCESSED_DIR = PROJECT_ROOT / "uploads" / "processed"

class SpotlightHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() == ".mp4":
            # Kiểm tra xem file có nằm trong folder video hoặc processed không
            if file_path.parent != VIDEO_DIR and file_path.parent != PROCESSED_DIR:
                return

            print(f"\n[DETECTED] Phat hien video moi: {file_path.name}")
            print(f"[FROM] Thu muc: {file_path.parent.name}")
            print("[INFO] Dang doi 5 giay de dam bao file da duoc ghi hoan tat...")
            time.sleep(5)
            
            print(f"[ACTION] Bat dau dang bai cho: {file_path.name}")
            try:
                # Gọi script upload kèm theo đích danh file video
                cmd = [
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "run_spotlight_web_upload.py"),
                    "--headless",
                    "--file", str(file_path.absolute())
                ]
                subprocess.run(cmd, check=True)
                print(f"[SUCCESS] Robot da xu ly xong file {file_path.name}")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Robot gap loi khi xu ly {file_path.name}")

def main():
    for d in [VIDEO_DIR, PROCESSED_DIR]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)

    event_handler = SpotlightHandler()
    observer = Observer()
    
    # Giam sat ca 2 thu muc
    observer.schedule(event_handler, str(VIDEO_DIR), recursive=False)
    observer.schedule(event_handler, str(PROCESSED_DIR), recursive=False)
    
    print("="*60)
    print("   SNAPCHAT SPOTLIGHT AUTO-PILOT IS RUNNING (PRO)")
    print("="*60)
    print(f"[STATUS] Dang giam sat: \n  1. {VIDEO_DIR}\n  2. {PROCESSED_DIR}")
    print("[INFO] Robot se tu dong dang bat ky video mp4 nao xuat hien.")
    print("[HINT] Nhan Ctrl+C de dung Robot.")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[INFO] Da dung Robot Auto-Pilot.")
    observer.join()

if __name__ == "__main__":
    main()
