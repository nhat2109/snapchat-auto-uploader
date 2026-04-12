"""
modules/core/account_manager.py
Account Manager - Multi-account management với proxy assignment
"""

from typing import Optional, List, Dict, Any

from loguru import logger

from modules.database import Database, Account, AccountStatus
from modules.utils.logger import get_logger


class AccountManager:
    """
    Quản lý tài khoản đa luồng:
    - Load accounts từ DB
    - Filter theo status
    - Assign proxy cho account
    - Track account state
    """

    def __init__(self, db: Optional[Database] = None):
        self.db       = db
        self._log      = get_logger("AccountManager")
        self._cache: Dict[int, Account] = {}  # id -> Account

    # ─────────────────────────────────────────────────────────────────────
    #  Load & Cache
    # ─────────────────────────────────────────────────────────────────────
    def load_all(self) -> List[Account]:
        """Load tất cả accounts vào cache."""
        if not self.db:
            self._log.error("Database chưa kết nối.")
            return []
        accounts = self.db.get_all_accounts()
        self._cache = {a.id: a for a in accounts}
        self._log.info(f"Loaded {len(accounts)} accounts vào cache.")
        return accounts

    def load_active(self) -> List[Account]:
        """Load accounts đang active."""
        if not self.db:
            return []
        accounts = self.db.get_active_accounts()
        self._cache.update({a.id: a for a in accounts})
        return accounts

    # ─────────────────────────────────────────────────────────────────────
    #  Account CRUD
    # ─────────────────────────────────────────────────────────────────────
    def add_account(self, username: str, password: str,
                    proxy: Optional[str] = None,
                    status: str = AccountStatus.PENDING) -> Account:
        """Thêm tài khoản mới."""
        if not self.db:
            raise RuntimeError("Database chưa kết nối.")
        acc = self.db.create_account(username, password, proxy, status)
        self._cache[acc.id] = acc
        self._log.info(f"Added account: {username}")
        return acc

    def get_account(self, account_id: int) -> Optional[Account]:
        """Lấy account từ cache hoặc DB."""
        if account_id in self._cache:
            return self._cache[account_id]
        if self.db:
            acc = self.db.get_account_by_id(account_id)
            if acc:
                self._cache[acc.id] = acc
            return acc
        return None

    def get_account_by_username(self, username: str) -> Optional[Account]:
        """Lấy account theo username."""
        if self.db:
            return self.db.get_account_by_username(username)
        return None

    def get_next_available(self) -> Optional[Account]:
        """Lấy tài khoản active tiếp theo (round-robin)."""
        active = self.load_active()
        for acc in active:
            if acc.status == AccountStatus.ACTIVE:
                return acc
        return None

    def update_status(self, account_id: int, status: str) -> bool:
        """Cập nhật trạng thái account."""
        if account_id in self._cache:
            self._cache[account_id].status = status
        if self.db:
            return self.db.update_account_status(account_id, status)
        return False

    def mark_banned(self, account_id: int) -> bool:
        """Đánh dấu account bị banned."""
        self._log.warning(f"Account {account_id} bị banned!")
        return self.update_status(account_id, AccountStatus.BANNED)

    def mark_active(self, account_id: int) -> bool:
        """Đánh dấu account active."""
        return self.update_status(account_id, AccountStatus.ACTIVE)

    def remove(self, account_id: int) -> bool:
        """Xóa account."""
        self._cache.pop(account_id, None)
        if self.db:
            return self.db.delete_account(account_id)
        return False

    # ─────────────────────────────────────────────────────────────────────
    #  Proxy assignment
    # ─────────────────────────────────────────────────────────────────────
    def get_proxy_for_account(self, account_id: int) -> Optional[str]:
        """Lấy proxy URL được gán cho account."""
        acc = self.get_account(account_id)
        if acc and acc.proxy:
            return acc.proxy
        return None

    def assign_proxy_to_account(self, account_id: int, proxy_url: str) -> bool:
        """Gán proxy cho account."""
        acc = self.get_account(account_id)
        if acc and self.db:
            acc.proxy = proxy_url
            # Update DB
            return self.db.update_account_proxy(account_id, proxy_url)
        return False

    # ─────────────────────────────────────────────────────────────────────
    #  Stats
    # ─────────────────────────────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        total    = len(self._cache)
        active   = sum(1 for a in self._cache.values() if a.status == AccountStatus.ACTIVE)
        banned   = sum(1 for a in self._cache.values() if a.status == AccountStatus.BANNED)
        pending  = sum(1 for a in self._cache.values() if a.status == AccountStatus.PENDING)
        return {
            "total":  total,
            "active": active,
            "banned": banned,
            "pending": pending,
        }

    def __repr__(self):
        return f"<AccountManager(total={len(self._cache)})>"

    # ─────────────────────────────────────────────────────────────────────
    #  Bulk import từ file
    # ─────────────────────────────────────────────────────────────────────
    def import_from_file(self, filepath: str) -> int:
        """
        Import accounts từ file text.
        Format: username:password[:proxy]
        """
        count = 0
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                username = parts[0]
                password = parts[1] if len(parts) > 1 else ""
                proxy    = parts[2] if len(parts) > 2 else None
                try:
                    self.add_account(username, password, proxy, AccountStatus.PENDING)
                    count += 1
                except Exception as e:
                    self._log.error(f"Failed to add {username}: {e}")
        return count