"""
modules/core/job_manager.py
Job Manager - Job queue system với retry logic
"""

import os
import asyncio
from typing import Optional, List, Dict, Any, Callable, Awaitable

from loguru import logger

from modules.database import Database, Job, JobStatus
from modules.utils.logger import get_logger


# ─── Callback type ────────────────────────────────────────────────────
JobCallback = Callable[["JobManager", Job, "BrowserManager"], Awaitable[bool]]


class JobManager:
    """
    Job Queue System:
    - Load pending jobs từ DB
    - Process tuần tự hoặc song song
    - Retry khi fail (max 3 lần)
    - Auto-assign account + proxy
    - Screenshot on error
    """

    def __init__(self,
                 db: Optional[Database] = None,
                 max_retries: int = 3,
                 max_parallel: int = 1):
        self.db          = db
        self.max_retries = max_retries
        self.max_parallel = max_parallel
        self._log         = get_logger("JobManager")
        self._running     = False
        self._current_job: Optional[int] = None

    # ─────────────────────────────────────────────────────────────────────
    #  Load jobs
    # ─────────────────────────────────────────────────────────────────────
    def load_pending(self, limit: int = 10) -> List[Job]:
        if not self.db:
            self._log.error("Database chưa kết nối.")
            return []
        jobs = self.db.get_pending_jobs(limit)
        self._log.info(f"Loaded {len(jobs)} pending jobs.")
        return jobs

    def get_job(self, job_id: int) -> Optional[Job]:
        if self.db:
            return self.db.get_job_by_id(job_id)
        return None

    def get_all_jobs(self, status: Optional[str] = None) -> List[Job]:
        if self.db:
            return self.db.get_all_jobs(status)
        return []

    # ─────────────────────────────────────────────────────────────────────
    #  Job CRUD
    # ─────────────────────────────────────────────────────────────────────
    def create_job(self,
                   video_path: str,
                   music_path: Optional[str] = None,
                   title: Optional[str] = None,
                   music_title: Optional[str] = None,
                   artist: Optional[str] = None,
                   description: Optional[str] = None,
                   tags: Optional[str] = None,
                   account_id: Optional[int] = None) -> Job:
        """Tạo job mới."""
        if not self.db:
            raise RuntimeError("Database chưa kết nối.")
        return self.db.create_job(
            video_path=video_path,
            music_path=music_path,
            title=title,
            music_title=music_title,
            artist=artist,
            description=description,
            tags=tags,
            account_id=account_id,
        )

    def update_status(self, job_id: int, status: str,
                      error_message: Optional[str] = None) -> bool:
        """Cập nhật trạng thái job."""
        self._log.info(f"Job {job_id} status: {status}" +
                       (f" | Error: {error_message}" if error_message else ""))
        if self.db:
            return self.db.update_job_status(job_id, status, error_message)
        return False

    def mark_running(self, job_id: int) -> bool:
        return self.update_status(job_id, JobStatus.RUNNING)

    def mark_done(self, job_id: int) -> bool:
        return self.update_status(job_id, JobStatus.DONE)

    def mark_failed(self, job_id: int, error: str) -> bool:
        return self.update_status(job_id, JobStatus.FAILED, error)

    def increment_retry(self, job_id: int) -> int:
        if self.db:
            return self.db.increment_retry(job_id)
        return 0

    def assign_account(self, job_id: int, account_id: int) -> bool:
        if self.db:
            return self.db.assign_account_to_job(job_id, account_id)
        return False

    def delete_job(self, job_id: int) -> bool:
        if self.db:
            return self.db.delete_job(job_id)
        return False

    # ─────────────────────────────────────────────────────────────────────
    #  Process single job
    # ─────────────────────────────────────────────────────────────────────
    async def process_job(self,
                          job: Job,
                          browser_mgr,
                          account_mgr,
                          callback: JobCallback) -> bool:
        """
        Xử lý 1 job: gọi callback → retry nếu fail → update status.
        """
        self._current_job = job.id
        self._log.section(f"PROCESSING JOB #{job.id}: {job.title or 'Untitled'}")

        # Assign account
        if not job.account_id:
            acc = account_mgr.get_next_available()
            if acc:
                self.assign_account(job.id, acc.id)
                job.account_id = acc.id

        # Run automation
        success = False
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            self._log.info(f"Job #{job.id} attempt {attempt}/{self.max_retries}")

            try:
                self.mark_running(job.id)
                result = await callback(self, job, browser_mgr)
                if result:
                    self.mark_done(job.id)
                    self._log.info(f"✅ Job #{job.id} hoàn tất!")
                    success = True
                    break
            except Exception as e:
                last_error = str(e)
                self._log.error(f"Job #{job.id} failed: {e}")

                if self.db and attempt < self.max_retries:
                    retry_count = self.increment_retry(job.id)
                    # Đợi trước khi retry
                    from modules.utils.retry import random_delay
                    wait = random_delay(3.0, 8.0)
                    self._log.warning(f"Retry #{retry_count} sau {wait:.1f}s...")

            if attempt == self.max_retries:
                self.mark_failed(job.id, last_error or "Max retries exceeded")

        self._current_job = None
        return success

    # ─────────────────────────────────────────────────────────────────────
    #  Process queue (sequential)
    # ─────────────────────────────────────────────────────────────────────
    async def run_queue(self,
                         browser_mgr,
                         account_mgr,
                         callback: JobCallback,
                         job_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Xử lý toàn bộ queue tuần tự.
        """
        self._running = True
        results = {"done": 0, "failed": 0, "total": 0}

        if job_ids:
            jobs = [self.get_job(jid) for jid in job_ids]
            jobs = [j for j in jobs if j]
        else:
            jobs = self.load_pending()

        results["total"] = len(jobs)
        self._log.info(f"Starting queue: {len(jobs)} jobs")

        for job in jobs:
            if not self._running:
                self._log.warning("Queue stopped by user.")
                break

            ok = await self.process_job(job, browser_mgr, account_mgr, callback)
            if ok:
                results["done"] += 1
            else:
                results["failed"] += 1

        self._running = False
        self._log.info(f"Queue done: {results}")
        return results

    def stop_queue(self) -> None:
        """Dừng queue processing."""
        self._log.warning("Stopping queue...")
        self._running = False

    # ─────────────────────────────────────────────────────────────────────
    #  Stats
    # ─────────────────────────────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        if not self.db:
            return {}
        return self.db.get_stats()

    @property
    def is_running(self) -> bool:
        return self._running

    def __repr__(self):
        return f"<JobManager(running={self._running}, current_job={self._current_job})>"