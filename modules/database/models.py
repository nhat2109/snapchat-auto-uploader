"""
modules/database/models.py
ORM Models cho Snapchat Automation + Viral Content System
Theo chuẩn hethong.txt
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, BigInteger
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ─── Enum values (MySQL compatible) ────────────────────────────────────
class AccountStatus:
    ACTIVE  = "active"
    BANNED  = "banned"
    PENDING = "pending"

class JobStatus:
    PENDING     = "pending"
    RUNNING     = "running"
    FAILED      = "failed"
    DONE        = "done"
    SCRAPING    = "scraping"
    DOWNLOADING = "downloading"
    PROCESSING  = "processing"
    UPLOADING   = "uploading"

class JobType:
    SCRAPE_VIDEO   = "scrape_video"
    DOWNLOAD_VIDEO = "download_video"
    PROCESS_VIDEO  = "process_video"
    UPLOAD_VIDEO   = "upload_video"

class LogLevel:
    INFO  = "INFO"
    WARN  = "WARN"
    ERROR = "ERROR"
    STEP  = "STEP"

class ProxyType:
    HTTP   = "http"
    SOCKS5 = "socks5"

class ProxyStatus:
    ACTIVE = "active"
    DEAD   = "dead"

class VideoStatus:
    SCRAPED    = "scraped"
    DOWNLOADED = "downloaded"
    PROCESSED  = "processed"
    UPLOADED   = "uploaded"
    FAILED     = "failed"

class DistributorStatus:
    PENDING  = "pending"
    UPLOADED = "uploaded"
    APPROVED = "approved"
    REJECTED = "rejected"


# ═══════════════════════════════════════════════════════════════════════════
#  MODELS - Theo đúng thứ tự để SQLAlchemy resolve FK trước
# ═══════════════════════════════════════════════════════════════════════════

class Account(Base):
    __tablename__ = "accounts"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    username  = Column(String(255), nullable=False, unique=True)
    password  = Column(String(255), nullable=False)
    proxy     = Column(String(500), nullable=True)
    status    = Column(String(20), default=AccountStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs      = relationship("Job", back_populates="account")
    logs      = relationship("LogEntry", back_populates="account")
    analytics = relationship("Analytics", back_populates="account")

    def __repr__(self):
        return f"<Account(id={self.id}, username={self.username}, status={self.status})>"

    def to_dict(self):
        return {
            "id": self.id, "username": self.username,
            "proxy": self.proxy, "status": self.status,
            "created_at": str(self.created_at),
        }


class Job(Base):
    __tablename__ = "jobs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    account_id    = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    video_id      = Column(Integer, ForeignKey("videos.id"), nullable=True)
    music_id      = Column(Integer, ForeignKey("music.id"), nullable=True)
    job_type      = Column(String(30), default=JobType.UPLOAD_VIDEO)
    video_path    = Column(String(500), nullable=False)
    music_path    = Column(String(500), nullable=True)
    title         = Column(String(255), nullable=True)
    music_title   = Column(String(255), nullable=True)
    artist        = Column(String(255), nullable=True)
    description   = Column(Text, nullable=True)
    tags          = Column(String(500), nullable=True)
    status        = Column(String(20), default=JobStatus.PENDING)
    retry_count   = Column(Integer, default=0)
    views         = Column(BigInteger, default=0)
    error_message = Column(Text, nullable=True)
    related_id    = Column(Integer, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account = relationship("Account", back_populates="jobs")
    video   = relationship("Video", back_populates="jobs")
    music   = relationship("Music", back_populates="jobs")
    logs    = relationship("LogEntry", back_populates="job")

    def __repr__(self):
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status})>"

    def to_dict(self):
        return {
            "id": self.id, "account_id": self.account_id,
            "video_id": self.video_id, "music_id": self.music_id,
            "job_type": self.job_type, "title": self.title,
            "status": self.status, "retry_count": self.retry_count,
            "views": self.views, "error_message": self.error_message,
            "created_at": str(self.created_at),
        }


class LogEntry(Base):
    __tablename__ = "logs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    job_id          = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    account_id      = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    message         = Column(Text, nullable=False)
    level           = Column(String(10), default=LogLevel.INFO)
    screenshot_path = Column(String(500), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    job     = relationship("Job", back_populates="logs")
    account = relationship("Account", back_populates="logs")

    def __repr__(self):
        return f"<LogEntry(id={self.id}, level={self.level}, job_id={self.job_id})>"

    def to_dict(self):
        return {
            "id": self.id, "job_id": self.job_id,
            "account_id": self.account_id,
            "message": self.message, "level": self.level,
            "screenshot_path": self.screenshot_path,
            "created_at": str(self.created_at),
        }


class Proxy(Base):
    __tablename__ = "proxies"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    host      = Column(String(255), nullable=False)
    port      = Column(Integer, nullable=False)
    username  = Column(String(255), nullable=True)
    password  = Column(String(255), nullable=True)
    type      = Column(String(20), default=ProxyType.HTTP)
    country   = Column(String(50), nullable=True)
    status    = Column(String(20), default=ProxyStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Proxy(id={self.id}, host={self.host}:{self.port})>"

    @property
    def proxy_url(self) -> str:
        if self.username and self.password:
            return f"{self.type}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.type}://{self.host}:{self.port}"

    def to_dict(self):
        return {
            "id": self.id, "host": self.host, "port": self.port,
            "username": self.username, "type": self.type,
            "country": self.country, "status": self.status,
            "proxy_url": self.proxy_url,
        }


# ═══════════════════════════════════════════════════════════════════════════
#  NEW MODELS - Theo hethong.txt
# ═══════════════════════════════════════════════════════════════════════════

class Video(Base):
    """Video từ nguồn viral (YouTube, TikTok, Douyin)"""
    __tablename__ = "videos"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    source_url     = Column(String(700), nullable=False, unique=True)
    local_path     = Column(String(700), nullable=True)
    processed_path = Column(String(700), nullable=True)
    title          = Column(String(500), nullable=True)
    source         = Column(String(50), nullable=True)   # youtube, tiktok, douyin
    views          = Column(BigInteger, default=0)
    duration_sec   = Column(Integer, nullable=True)
    thumbnail      = Column(String(700), nullable=True)
    status         = Column(String(20), default=VideoStatus.SCRAPED)
    is_winning     = Column(Boolean, default=False)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analytics = relationship("Analytics", back_populates="video")
    jobs      = relationship("Job", back_populates="video")

    def __repr__(self):
        return f"<Video(id={self.id}, source={self.source}, views={self.views})>"

    def to_dict(self):
        return {
            "id": self.id, "source_url": self.source_url,
            "local_path": self.local_path,
            "processed_path": self.processed_path,
            "title": self.title, "source": self.source,
            "views": self.views, "duration_sec": self.duration_sec,
            "status": self.status, "is_winning": self.is_winning,
            "created_at": str(self.created_at),
        }


class Music(Base):
    """Thư viện nhạc của người dùng"""
    __tablename__ = "music"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    name               = Column(String(255), nullable=False)
    artist             = Column(String(255), nullable=True)
    file_path          = Column(String(700), nullable=False)
    genre              = Column(String(100), nullable=True)
    distributor_status = Column(String(20), default=DistributorStatus.PENDING)
    distributor_url    = Column(String(700), nullable=True)
    uploaded_at        = Column(DateTime, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("Job", back_populates="music")

    def __repr__(self):
        return f"<Music(id={self.id}, name={self.name})>"

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "artist": self.artist,
            "file_path": self.file_path, "genre": self.genre,
            "distributor_status": self.distributor_status,
            "distributor_url": self.distributor_url,
            "created_at": str(self.created_at),
        }


class Analytics(Base):
    """Theo dõi hiệu suất video trên Snapchat"""
    __tablename__ = "analytics"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    video_id   = Column(Integer, ForeignKey("videos.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    views      = Column(BigInteger, default=0)
    likes      = Column(BigInteger, default=0)
    shares     = Column(BigInteger, default=0)
    comments   = Column(BigInteger, default=0)
    snap_url   = Column(String(700), nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    video   = relationship("Video", back_populates="analytics")
    account = relationship("Account", back_populates="analytics")

    def __repr__(self):
        return f"<Analytics(video_id={self.video_id}, views={self.views})>"

    def to_dict(self):
        return {
            "id": self.id, "video_id": self.video_id,
            "account_id": self.account_id,
            "views": self.views, "likes": self.likes,
            "shares": self.shares, "comments": self.comments,
            "snap_url": self.snap_url,
            "checked_at": str(self.checked_at),
        }
