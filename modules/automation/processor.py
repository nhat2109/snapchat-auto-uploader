"""
modules/automation/processor.py
Video Processor - Xử lý video bằng ffmpeg để tránh duplicate detection
Theo hethong.txt - Section 2.3

Chức năng:
  • Cắt clip (5–15s)
  • Resize về 9:16 (dọc)
  • Thêm subtitle / text overlay
  • Thêm zoom hoặc blur effect
  • Ghép nhạc nền
"""

import os
import asyncio
import random
from pathlib import Path
from typing import Optional, List, Dict

from loguru import logger

from modules.utils.logger import PipelineLogger
from modules.utils.retry import async_random_delay


class VideoProcessor:
    """
    Xử lý video bằng ffmpeg (hoặc moviepy wrapper):
      1. Trim (cắt đoạn 5–15s)
      2. Resize 9:16
      3. Text overlay / watermark
      4. Zoom/blur effect
      5. Add background music
    """

    def __init__(self,
                 ffmpeg_path: str = "ffmpeg",
                 output_dir: str = "uploads/processed"):
        self.ffmpeg   = ffmpeg_path
        self.out_dir = Path(output_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._log    = None

    # ─────────────────────────────────────────────────────────────────────
    #  Main process
    # ─────────────────────────────────────────────────────────────────────
    async def process(self,
                       video_path: str,
                       music_path: Optional[str] = None,
                       output_name: Optional[str] = None,
                       start_sec: float = 0.0,
                       duration_sec: float = 15.0,
                       add_text: Optional[str] = None,
                       text_position: str = "center",
                       font_size: int = 36,
                       font_color: str = "white",
                       add_blur: bool = True,
                       add_zoom: bool = False,
                       zoom_factor: float = 1.05,
                       pipeline_logger: Optional[PipelineLogger] = None) -> dict:
        """
        Xử lý 1 video: trim → resize → effect → add music.

        Args:
            video_path    : Đường dẫn video nguồn
            music_path    : File nhạc nền
            output_name   : Tên file output (auto nếu None)
            start_sec     : Thời điểm bắt đầu cắt
            duration_sec  : Thời lượng clip (5–15s)
            add_text      : Thêm text overlay
            text_position  : Vị trí text (center, bottom, top)
            font_size     : Cỡ chữ
            font_color    : Màu chữ
            add_blur      : Thêm blur effect
            add_zoom      : Thêm zoom effect
            zoom_factor   : Hệ số zoom
        """
        self._log = pipeline_logger or PipelineLogger()
        self._log.section("VIDEO PROCESSING")

        if not os.path.exists(video_path):
            self._log.error(f"Video không tồn tại: {video_path}")
            return {"success": False, "error": "Video file not found"}

        if output_name is None:
            ts      = random.randint(1000, 9999)
            name    = Path(video_path).stem
            output_name = f"{name}_processed_{ts}.mp4"

        output_path = str(self.out_dir / output_name)

        self._log.info(f"📹 Source: {video_path}")
        self._log.info(f"⏱  Trim: {start_sec}s → {start_sec + duration_sec}s")
        self._log.info(f"📐 Target: 9:16 vertical")

        result = {"success": False, "output_path": None, "error": None}

        try:
            # Build ffmpeg command
            cmd = await self._build_ffmpeg_cmd(
                video_path, output_path,
                start_sec, duration_sec,
                add_text, text_position, font_size, font_color,
                add_blur, add_zoom, zoom_factor,
                music_path,
            )

            if cmd is None:
                # Fallback: chạy thông qua Python subprocess
                result = await self._process_with_python(video_path, output_path,
                                                          start_sec, duration_sec)
                return result

            # Chạy ffmpeg trong thread pool
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0 and os.path.exists(output_path):
                result["success"]     = True
                result["output_path"] = output_path
                self._log.info(f"✅ Video processed: {output_path}")
            else:
                err = stderr.decode() if stderr else "Unknown error"
                self._log.error(f"FFmpeg failed: {err}")
                result["error"] = err

        except FileNotFoundError:
            self._log.warn("⚠️ FFmpeg không tìm thấy — dùng moviepy fallback")
            result = await self._process_with_python(video_path, output_path,
                                                    start_sec, duration_sec)
        except Exception as e:
            result["error"] = str(e)
            self._log.error(f"Process error: {e}")

        await async_random_delay(1.0, 2.0)
        return result

    # ─────────────────────────────────────────────────────────────────────
    #  Build FFmpeg command
    # ─────────────────────────────────────────────────────────────────────
    async def _build_ffmpeg_cmd(self,
                                  video_path: str,
                                  output_path: str,
                                  start_sec: float,
                                  duration_sec: float,
                                  add_text: Optional[str],
                                  text_position: str,
                                  font_size: int,
                                  font_color: str,
                                  add_blur: bool,
                                  add_zoom: bool,
                                  zoom_factor: float,
                                  music_path: Optional[str]) -> Optional[List[str]]:

        # Check ffmpeg available
        import shutil
        if not shutil.which(self.ffmpeg):
            return None

        cmd = [self.ffmpeg, "-y"]

        # Input video
        cmd += ["-i", video_path]

        # Input music
        if music_path and os.path.exists(music_path):
            cmd += ["-i", music_path]

        # ── Video filter chain ───────────────────────────────────────────
        filters = []

        # 1. Trim theo thời gian
        filters.append(f"trim=start={start_sec}:duration={duration_sec},setpts=PTS-STARTPTS")

        # 2. Scale về 9:16 (vertical) — base width 720 → height 1280
        filters.append("scale=720:1280:force_original_aspect_ratio=decrease")
        filters.append("pad=720:1280:(ow-iw)/2:(oh-ih)/2:black")

        # 3. Zoom effect (tùy chọn)
        if add_zoom:
            zoom_cmd = (
                f"zoompan=z='min(zoom+{zoom_factor/10}, {zoom_factor})'"
                f":d=1:s=720x1280"
            )
            filters.append(zoom_cmd)

        # 4. Blur edges (tùy chọn)
        if add_blur:
            filters.append("unsharp=5:5:0.8:3:3:0.5")

        # 5. Text overlay
        if add_text:
            pos_y = {
                "center": "(h-text_h)/2",
                "bottom": "h-text_h-20",
                "top":    "20",
            }.get(text_position, "(h-text_h)/2")
            pos_x = "(w-text_w)/2"
            fontfile = "C\\:/Windows/Tasks/SegoeUI.ttf"  # Windows path, fallback nếu thiếu

            text_filter = (
                f"drawtext=text='{add_text}':"
                f"fontsize={font_size}:"
                f"fontcolor={font_color}:"
                f"x={pos_x}:y={pos_y}"
            )
            filters.append(text_filter)

        # Áp filter
        cmd += ["-vf", ",".join(filters)]

        # ── Audio ────────────────────────────────────────────────────────
        if music_path and os.path.exists(music_path):
            cmd += ["-map", "0:v", "-map", "1:a"]
            cmd += ["-shortest"]
        else:
            cmd += ["-map", "0:v"]

        # Output
        cmd += [
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path,
        ]

        return cmd

    # ─────────────────────────────────────────────────────────────────────
    #  Python fallback (moviepy)
    # ─────────────────────────────────────────────────────────────────────
    async def _process_with_python(self,
                                     video_path: str,
                                     output_path: str,
                                     start_sec: float,
                                     duration_sec: float) -> dict:
        """Fallback khi không có ffmpeg — dùng moviepy."""
        try:
            from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
            from PIL import Image, ImageDraw, ImageFont
            import numpy as np

            self._log.info("🎬 Processing với moviepy...")

            clip = VideoFileClip(video_path).subclip(start_sec, start_sec + duration_sec)

            # Resize 9:16
            w, h = clip.size
            target_w, target_h = 720, 1280
            scale = min(target_w / w, target_h / h)
            clip  = clip.resize(scale)

            # Pad về 9:16
            def add_padding(frame):
                img = Image.fromarray(frame)
                new = Image.new("RGB", (target_w, target_h), (0, 0, 0))
                x = (target_w - img.width) // 2
                y = (target_h - img.height) // 2
                new.paste(img, (x, y))
                return np.array(new)

            clip = clip.fl_image(add_padding)

            # Add music
            if os.path.exists(str(self.out_dir.parent / "music")):
                # Tìm music mặc định
                pass

            clip.write_videofile(output_path, codec="libx264", fps=30,
                                audio_codec="aac", threads=4, logger=None)

            self._log.info(f"✅ Moviepy done: {output_path}")
            return {"success": True, "output_path": output_path}

        except ImportError:
            self._log.error("⚠️ Cần cài đặt: pip install moviepy Pillow")
            return {"success": False, "error": "moviepy not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────────────────────────────
    #  Batch process
    # ─────────────────────────────────────────────────────────────────────
    async def process_batch(self,
                             videos: List[Dict],
                             pipeline_logger: Optional[PipelineLogger] = None) -> List[dict]:
        """
        Xử lý nhiều video tuần tự.
        videos: List[dict] — mỗi dict có 'local_path', 'title', ...
        """
        self._log = pipeline_logger or PipelineLogger()
        self._log.section("BATCH VIDEO PROCESSING")

        results = []
        for i, v in enumerate(videos):
            video_path = v.get("local_path", "")
            if not video_path or not os.path.exists(video_path):
                continue

            output_name = f"batch_{i+1:03d}_{Path(video_path).stem}.mp4"
            result = await self.process(
                video_path=video_path,
                output_name=output_name,
                duration_sec=random.randint(10, 15),
                pipeline_logger=pipeline_logger,
            )
            results.append(result)

        return results


# ─── Utility helpers ──────────────────────────────────────────────────

def get_video_duration(filepath: str) -> Optional[float]:
    """Lấy thời lượng video (giây)."""
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return None
