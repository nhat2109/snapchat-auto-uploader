"""
modules/utils/logger.py
Logging system - loguru + file + database
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from loguru import logger

from modules.database import Database, LogLevel

# ─── Đường dẫn mặc định ────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE  = LOG_DIR / "app.log"
ERROR_LOG = LOG_DIR / "errors.log"


def setup_logging(log_level: str = "INFO",
                   log_file: Optional[str] = None,
                   log_rotation: str = "100 MB",
                   log_retention: int = 7) -> None:
    """
    Khởi tạo loguru logger với file + console output.
    """
    # Remove default handler
    logger.remove()

    # Console: luôn có, màu sắc theo level
    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File chính: rotation + retention
    _log_file = log_file or str(LOG_FILE)
    logger.add(
        _log_file,
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        rotation=log_rotation,
        retention=f"{log_retention} days",
        compression="zip",
        encoding="utf-8",
    )

    # File lỗi riêng: chỉ ghi ERROR
    logger.add(
        str(ERROR_LOG),
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        rotation="50 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )


def get_logger(name: Optional[str] = None):
    """Lấy logger instance, tùy chọn gắn thêm context name."""
    if name:
        return logger.bind(name=name)
    return logger


class PipelineLogger:
    """
    Logger wrapper đồng thời ghi:
      - Console + file (loguru)
      - Database (LogEntry)
    """

    def __init__(self, job_id: Optional[int] = None,
                 account_id: Optional[int] = None,
                 db: Optional[Database] = None,
                 screenshot_dir: str = "screenshots"):
        self.job_id     = job_id
        self.account_id = account_id
        self.db         = db
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(exist_ok=True)
        self._loguru    = logger.bind(job_id=job_id, account_id=account_id)

    # ─────────────────────────────────────────────────────────────────────
    #  Level helpers
    # ─────────────────────────────────────────────────────────────────────
    def _log(self, level: str, message: str,
             exc_info: bool = False,
             save_screenshot: bool = False,
             browser_page=None) -> None:
        # Loguru
        extra = {"job_id": self.job_id, "account_id": self.account_id}
        log_func = getattr(self._loguru, level.lower(), self._loguru.info)
        log_func(message, extra=extra)

        # Database
        if self.db:
            ss_path = None
            if save_screenshot and browser_page:
                ss_path = self._take_screenshot()
            try:
                self.db.add_log(
                    message=message,
                    level=level,
                    job_id=self.job_id,
                    account_id=self.account_id,
                    screenshot_path=ss_path,
                )
            except Exception as e:
                self._loguru.warning(f"Không ghi được log vào DB: {e}")

    def _take_screenshot(self) -> Optional[str]:
        try:
            import asyncio
            from pathlib import Path
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_{self.job_id or 'nojob'}_{ts}.png"
            path = self.screenshot_dir / filename
            # Sẽ được gọi từ browser manager bên ngoài
            return str(path)
        except Exception:
            return None

    def info(self, msg: str):      self._log("INFO", msg)
    def warn(self, msg: str):      self._log("WARN", msg)
    def error(self, msg: str, exc_info=False):
        self._log("ERROR", msg, exc_info=exc_info)
    def step(self, msg: str):      self._log("STEP", msg)

    def section(self, title: str):
        sep = "=" * 60
        self.step(sep)
        self.step(f"  {title}")
        self.step(sep)


# ─── Convenience export ────────────────────────────────────────────────
setup_logging()
