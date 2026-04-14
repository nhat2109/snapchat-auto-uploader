"""
modules/database/db.py
Database connection và CRUD operations sử dụng SQLAlchemy
"""

import os
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .models import Base, Account, Job, LogEntry, Proxy, JobStatus, AccountStatus, ProxyStatus, LogLevel


class Database:
    """
    Singleton database manager cho Snapchat Automation Platform.
    Kết nối MySQL qua SQLAlchemy, hỗ trợ CRUD đầy đủ.
    """

    _instance = None

    def __new__(cls, db_url: Optional[str] = None):
        if cls._instance is not None:
            return cls._instance
        cls._instance = super().__new__(cls)
        cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_url: Optional[str] = None):
        if self._initialized:
            return
        self._initialized = True

        # Load from .env nếu không truyền db_url
        if db_url is None:
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass

            host     = os.getenv("DB_HOST", "localhost")
            port     = os.getenv("DB_PORT", "3306")
            name     = os.getenv("DB_NAME", "snapchat_automation")
            user     = os.getenv("DB_USER", "root")
            password = os.getenv("DB_PASSWORD", "")
            db_url   = f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"

        self.engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,
        )
        # Keep ORM attributes available after commit so returned objects
        # (e.g. from create_account/create_job) can be safely read by callers.
        self.SessionFactory = sessionmaker(bind=self.engine, expire_on_commit=False)

    # ─────────────────────────────────────────────────────────────────────
    #  Session management
    # ─────────────────────────────────────────────────────────────────────
    @contextmanager
    def session_scope(self) -> Session:
        """Context manager tự động commit/rollback."""
        session = self.SessionFactory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        return self.SessionFactory()

    # ─────────────────────────────────────────────────────────────────────
    #  Schema initialization
    # ─────────────────────────────────────────────────────────────────────
    def init_schema(self):
        """Tạo toàn bộ bảng trong database."""
        Base.metadata.create_all(self.engine)
        print("✅ Database schema đã được khởi tạo.")

    def drop_schema(self):
        """Xóa toàn bộ bảng (cẩn thận!)."""
        Base.metadata.drop_all(self.engine)
        print("⚠️ Database schema đã bị xóa.")

    # ─────────────────────────────────────────────────────────────────────
    #  ACCOUNTS CRUD
    # ─────────────────────────────────────────────────────────────────────
    def create_account(self, username: str, password: str,
                       proxy: Optional[str] = None,
                       status: str = AccountStatus.PENDING) -> Account:
        with self.session_scope() as s:
            acc = Account(username=username, password=password,
                          proxy=proxy, status=status)
            s.add(acc)
            return acc

    def get_account_by_id(self, account_id: int) -> Optional[Account]:
        with self.session_scope() as s:
            return s.query(Account).filter(Account.id == account_id).first()

    def get_account_by_username(self, username: str) -> Optional[Account]:
        with self.session_scope() as s:
            return s.query(Account).filter(Account.username == username).first()

    def get_all_accounts(self, status: Optional[str] = None) -> List[Account]:
        with self.session_scope() as s:
            q = s.query(Account)
            if status:
                q = q.filter(Account.status == status)
            return q.all()

    def get_active_accounts(self) -> List[Account]:
        return self.get_all_accounts(status=AccountStatus.ACTIVE)

    def update_account_status(self, account_id: int, status: str) -> bool:
        with self.session_scope() as s:
            acc = s.query(Account).filter(Account.id == account_id).first()
            if acc:
                acc.status = status
                return True
            return False

    def delete_account(self, account_id: int) -> bool:
        with self.session_scope() as s:
            acc = s.query(Account).filter(Account.id == account_id).first()
            if acc:
                s.delete(acc)
                return True
            return False

    def update_account_proxy(self, account_id: int, proxy: str) -> bool:
        with self.session_scope() as s:
            acc = s.query(Account).filter(Account.id == account_id).first()
            if acc:
                acc.proxy = proxy
                return True
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  JOBS CRUD
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
        with self.session_scope() as s:
            job = Job(
                account_id=account_id,
                video_path=video_path,
                music_path=music_path,
                title=title,
                music_title=music_title,
                artist=artist,
                description=description,
                tags=tags,
                status=JobStatus.PENDING,
            )
            s.add(job)
            return job

    def get_job_by_id(self, job_id: int) -> Optional[Job]:
        with self.session_scope() as s:
            return s.query(Job).filter(Job.id == job_id).first()

    def get_pending_jobs(self, limit: int = 10) -> List[Job]:
        with self.session_scope() as s:
            return (s.query(Job)
                    .filter(Job.status == JobStatus.PENDING)
                    .order_by(Job.created_at.asc())
                    .limit(limit)
                    .all())

    def get_all_jobs(self, status: Optional[str] = None) -> List[Job]:
        with self.session_scope() as s:
            q = s.query(Job)
            if status:
                q = q.filter(Job.status == status)
            return q.order_by(Job.created_at.desc()).all()

    def update_job_status(self, job_id: int, status: str,
                          error_message: Optional[str] = None) -> bool:
        with self.session_scope() as s:
            job = s.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = status
                if error_message:
                    job.error_message = error_message
                return True
            return False

    def increment_retry(self, job_id: int) -> int:
        with self.session_scope() as s:
            job = s.query(Job).filter(Job.id == job_id).first()
            if job:
                job.retry_count += 1
                return job.retry_count
            return 0

    def assign_account_to_job(self, job_id: int, account_id: int) -> bool:
        with self.session_scope() as s:
            job = s.query(Job).filter(Job.id == job_id).first()
            if job:
                job.account_id = account_id
                return True
            return False

    def delete_job(self, job_id: int) -> bool:
        with self.session_scope() as s:
            job = s.query(Job).filter(Job.id == job_id).first()
            if job:
                s.delete(job)
                return True
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  LOGS CRUD
    # ─────────────────────────────────────────────────────────────────────
    def add_log(self,
                message: str,
                level: str = LogLevel.INFO,
                job_id: Optional[int] = None,
                account_id: Optional[int] = None,
                screenshot_path: Optional[str] = None) -> LogEntry:
        with self.session_scope() as s:
            log = LogEntry(
                message=message,
                level=level,
                job_id=job_id,
                account_id=account_id,
                screenshot_path=screenshot_path,
            )
            s.add(log)
            return log

    def get_logs_by_job(self, job_id: int) -> List[LogEntry]:
        with self.session_scope() as s:
            return (s.query(LogEntry)
                    .filter(LogEntry.job_id == job_id)
                    .order_by(LogEntry.created_at.asc())
                    .all())

    def get_recent_logs(self, limit: int = 100) -> List[LogEntry]:
        with self.session_scope() as s:
            return (s.query(LogEntry)
                    .order_by(LogEntry.created_at.desc())
                    .limit(limit)
                    .all())

    # ─────────────────────────────────────────────────────────────────────
    #  PROXIES CRUD
    # ─────────────────────────────────────────────────────────────────────
    def create_proxy(self,
                     host: str, port: int,
                     username: Optional[str] = None,
                     password: Optional[str] = None,
                     proxy_type: str = "http",
                     country: Optional[str] = None) -> Proxy:
        with self.session_scope() as s:
            p = Proxy(host=host, port=port, username=username,
                      password=password, type=proxy_type, country=country)
            s.add(p)
            return p

    def get_active_proxies(self) -> List[Proxy]:
        with self.session_scope() as s:
            return s.query(Proxy).filter(Proxy.status == ProxyStatus.ACTIVE).all()

    def get_proxy_by_id(self, proxy_id: int) -> Optional[Proxy]:
        with self.session_scope() as s:
            return s.query(Proxy).filter(Proxy.id == proxy_id).first()

    def get_random_proxy(self) -> Optional[Proxy]:
        with self.session_scope() as s:
            return (s.query(Proxy)
                    .filter(Proxy.status == ProxyStatus.ACTIVE)
                    .order_by(text("RAND()"))
                    .first())

    def update_proxy_status(self, proxy_id: int, status: str) -> bool:
        with self.session_scope() as s:
            p = s.query(Proxy).filter(Proxy.id == proxy_id).first()
            if p:
                p.status = status
                return True
            return False

    def import_proxies_from_file(self, filepath: str) -> int:
        """Import proxies từ file text (mỗi dòng: host:port[:user:pass])"""
        count = 0
        with self.session_scope() as s:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(":")
                    host = parts[0]
                    port = int(parts[1]) if len(parts) > 1 else 8080
                    username = parts[2] if len(parts) > 2 else None
                    password = parts[3] if len(parts) > 3 else None
                    p = Proxy(host=host, port=port, username=username,
                              password=password, type="http")
                    s.add(p)
                    count += 1
        return count

    # ─────────────────────────────────────────────────────────────────────
    #  STATS
    # ─────────────────────────────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        with self.session_scope() as s:
            total_jobs     = s.query(Job).count()
            pending_jobs   = s.query(Job).filter(Job.status == JobStatus.PENDING).count()
            running_jobs   = s.query(Job).filter(Job.status == JobStatus.RUNNING).count()
            done_jobs      = s.query(Job).filter(Job.status == JobStatus.DONE).count()
            failed_jobs    = s.query(Job).filter(Job.status == JobStatus.FAILED).count()
            total_accounts = s.query(Account).count()
            active_accounts = s.query(Account).filter(Account.status == AccountStatus.ACTIVE).count()
            total_proxies  = s.query(Proxy).count()
            return {
                "jobs": {"total": total_jobs, "pending": pending_jobs,
                         "running": running_jobs, "done": done_jobs, "failed": failed_jobs},
                "accounts": {"total": total_accounts, "active": active_accounts},
                "proxies": {"total": total_proxies},
            }