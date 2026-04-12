"""
modules/automation/analytics.py
Analytics + Scaling System - Theo dõi hiệu suất và nhân rộng viral content
Theo hethong.txt - Section 2.9

Chức năng:
  • Ghi nhận views, likes, shares từ Snapchat (manual hoặc scraping)
  • Đánh dấu "winning content" (>10k views)
  • Tạo job mới từ winning content để scale
  • Thống kê tổng hợp
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from loguru import logger

from modules.utils.logger import get_logger


class AnalyticsTracker:
    """
    Theo dõi hiệu suất video và đề xuất scaling strategy.
    """

    WINNING_THRESHOLD = 10_000   # views threshold để đánh dấu "winning"

    def __init__(self, db=None):
        self.db  = db
        self._log = get_logger("AnalyticsTracker")

    # ─────────────────────────────────────────────────────────────────────
    #  Record metrics
    # ─────────────────────────────────────────────────────────────────────
    def record(self,
              video_id: int,
              account_id: int,
              views: int = 0,
              likes: int = 0,
              shares: int = 0,
              comments: int = 0,
              snap_url: Optional[str] = None) -> dict:
        """Ghi nhận metrics của 1 video từ 1 account."""
        try:
            entry = self.db.models.Analytics(
                video_id=video_id,
                account_id=account_id,
                views=views,
                likes=likes,
                shares=shares,
                comments=comments,
                snap_url=snap_url,
                checked_at=datetime.utcnow(),
            )
            self.db.session.add(entry)
            self.db.session.commit()

            # Cập nhật is_winning nếu đạt threshold
            if views >= self.WINNING_THRESHOLD:
                self._mark_winning(video_id)

            return {"success": True, "entry_id": entry.id}
        except Exception as e:
            self._log.error(f"Record analytics failed: {e}")
            return {"success": False, "error": str(e)}

    def _mark_winning(self, video_id: int) -> None:
        """Đánh dấu video là winning content."""
        if not self.db:
            return
        try:
            video = self.db.session.query(
                self.db.models.Video
            ).filter_by(id=video_id).first()
            if video and not video.is_winning:
                video.is_winning = True
                self.db.session.commit()
                self._log.info(f"🏆 Video #{video_id} được đánh dấu WINNING!")
        except Exception as e:
            self._log.error(f"Mark winning failed: {e}")

    # ─────────────────────────────────────────────────────────────────────
    #  Get winning content
    # ─────────────────────────────────────────────────────────────────────
    def get_winning_videos(self, min_views: int = None) -> List[Dict]:
        """Lấy danh sách video thắng (winning content)."""
        if not self.db:
            return []

        threshold = min_views or self.WINNING_THRESHOLD
        entries = (
            self.db.session.query(self.db.models.Analytics)
            .filter(self.db.models.Analytics.views >= threshold)
            .all()
        )

        results = []
        seen = set()
        for e in entries:
            if e.video_id in seen:
                continue
            seen.add(e.video_id)
            results.append({
                "video_id": e.video_id,
                "views":    e.views,
                "likes":    e.likes,
                "shares":   e.shares,
                "snap_url": e.snap_url,
            })
        return sorted(results, key=lambda x: x["views"], reverse=True)

    # ─────────────────────────────────────────────────────────────────────
    #  Get best performing videos (top content)
    # ─────────────────────────────────────────────────────────────────────
    def get_top_videos(self, limit: int = 20) -> List[Dict]:
        """Lấy top video theo views từ nguồn gốc."""
        if not self.db:
            return []
        videos = (
            self.db.session.query(self.db.models.Video)
            .filter(self.db.models.Video.views > 0)
            .order_by(self.db.models.Video.views.desc())
            .limit(limit)
            .all()
        )
        return [v.to_dict() for v in videos]

    # ─────────────────────────────────────────────────────────────────────
    #  Aggregate stats
    # ─────────────────────────────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        """Tổng hợp thống kê toàn hệ thống."""
        if not self.db:
            return {}

        try:
            total_videos    = self.db.session.query(self.db.models.Video).count()
            winning_videos  = self.db.session.query(self.db.models.Video).filter_by(is_winning=True).count()
            uploaded_videos = self.db.session.query(self.db.models.Video).filter_by(status="uploaded").count()

            analytics = self.db.session.query(self.db.models.Analytics).all()
            total_views   = sum(a.views for a in analytics)
            total_likes   = sum(a.likes for a in analytics)
            total_shares  = sum(a.shares for a in analytics)

            # Scale levels theo hethong.txt
            accounts = self.db.session.query(self.db.models.Account).filter_by(status="active").count()
            level = "Level 1 (5 acc)" if accounts >= 5 else \
                    "Level 2 (20 acc)" if accounts >= 20 else \
                    "Level 3 (50+ acc)" if accounts >= 50 else \
                    "Starting"

            return {
                "total_videos":    total_videos,
                "winning_videos": winning_videos,
                "uploaded_videos": uploaded_videos,
                "total_views":    total_views,
                "total_likes":    total_likes,
                "total_shares":   total_shares,
                "active_accounts": accounts,
                "scale_level":    level,
                "winning_threshold": self.WINNING_THRESHOLD,
            }

        except Exception as e:
            self._log.error(f"Get stats failed: {e}")
            return {}

    # ─────────────────────────────────────────────────────────────────────
    #  Scaling recommendations
    # ─────────────────────────────────────────────────────────────────────
    def get_scaling_recommendations(self) -> Dict[str, Any]:
        """Đưa ra khuyến nghị scale dựa trên hiệu suất."""
        stats   = self.get_stats()
        winning = self.get_winning_videos()

        recommendations = []

        if not winning:
            recommendations.append({
                "type": "INFO",
                "message": "Chưa có winning content. Cần tạo thêm video và thử nghiệm."
            })

        if stats.get("active_accounts", 0) < 5:
            recommendations.append({
                "type": "WARN",
                "message": f"Chỉ có {stats['active_accounts']} tài khoản. Nên có ≥5 tài khoản (Level 1)."
            })

        if winning:
            top = winning[0]
            recommendations.append({
                "type": "WIN",
                "message": f"🏆 Top content: {top['views']:,} views — Nhân rộng concept này!",
                "top_video": top,
            })

        if stats.get("total_views", 0) > 100_000:
            recommendations.append({
                "type": "SCALE",
                "message": "Đạt >100k views! Sẵn sàng scale lên Level 2 (20 accounts, 100 videos/ngày)."
            })

        return {
            "stats": stats,
            "winning_count": len(winning),
            "recommendations": recommendations,
        }

    # ─────────────────────────────────────────────────────────────────────
    #  Generate similar jobs from winning content
    # ─────────────────────────────────────────────────────────────────────
    def create_scale_jobs_from_winning(self,
                                       winning_video_id: int,
                                       num_copies: int = 3) -> List[int]:
        """
        Tạo jobs mới từ winning content để scale.
        Sử dụng cùng keyword/theme nhưng upload với account khác.
        """
        if not self.db:
            return []

        job_ids = []
        try:
            video = self.db.session.query(
                self.db.models.Video
            ).filter_by(id=winning_video_id).first()

            if not video:
                return []

            for i in range(num_copies):
                job = self.db.models.Job(
                    account_id=None,
                    video_id=video.id,
                    video_path=video.processed_path or video.local_path,
                    title=f"{video.title} (Scale {i+1})",
                    job_type="upload_video",
                    status="pending",
                )
                self.db.session.add(job)
                self.db.session.commit()
                job_ids.append(job.id)

            self._log.info(f"✅ Tạo {num_copies} scale jobs từ winning video #{winning_video_id}")

        except Exception as e:
            self._log.error(f"Create scale jobs failed: {e}")

        return job_ids
