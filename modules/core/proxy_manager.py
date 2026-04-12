"""
modules/core/proxy_manager.py
Proxy Manager - Proxy rotation + free proxy scraper + DB integration

Tích hợp ProxyManager của user vào hệ thống chuẩn hethong.txt.
Hỗ trợ:
  • Proxy tùy chỉnh (http/socks5)
  • Proxy miễn phí (scraped từ free-proxy-list.net, sslproxies.org)
  • Kiểm tra proxy alive (đa luồng)
  • Lưu vào MySQL database
  • Assign proxy cho account (1 proxy / 1 account)
"""

import os
import re
import time
import random
import asyncio
import requests
import threading
from queue import Queue
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime

from loguru import logger

from modules.database import Database, Proxy
from modules.utils.logger import get_logger


# ═══════════════════════════════════════════════════════════════════════════
#  PROXY MANAGER - Tích hợp user's code + system integration
# ═══════════════════════════════════════════════════════════════════════════

class ProxyManager:
    """
    Quản lý proxy toàn diện:
    - Proxy tùy chỉnh (http/socks5/authenticated)
    - Proxy miễn phí (scraped, multithread test)
    - Proxy rotation (1 proxy / 1 account)
    - DB persistence (MySQL)
    """

    # Nguồn scrape proxy miễn phí
    FREE_PROXY_SOURCES = [
        "https://free-proxy-list.net/",
        "https://sslproxies.org/",
        "https://www.socks-proxy.net/",
    ]

    def __init__(self, db: Optional[Database] = None):
        self.db          = db
        self._log        = get_logger("ProxyManager")
        self._proxies: List[str] = []       # list proxy strings
        self._free_proxies: List[str] = []  # scraped free proxies
        self._cache: Dict[int, str] = {}    # account_id → proxy_url

    # ─────────────────────────────────────────────────────────────────────
    #  Setup & Configuration
    # ─────────────────────────────────────────────────────────────────────
    def set_proxy(self, proxy_address: str) -> bool:
        """
        Đặt proxy mặc định cho hệ thống.
        Format: 'http://user:pass@ip:port' hoặc 'ip:port' hoặc 'type://ip:port'
        """
        proxy = self._normalize_proxy(proxy_address)
        if proxy:
            self._proxies = [proxy]
            self._log.info(f"Proxy set: {proxy}")
            return True
        return False

    def _normalize_proxy(self, proxy_str: str) -> Optional[str]:
        """Chuẩn hóa proxy string."""
        proxy_str = proxy_str.strip()
        if not proxy_str:
            return None

        # Đã có protocol prefix
        if proxy_str.startswith("http://") or proxy_str.startswith("socks5://"):
            return proxy_str

        # Thêm http://
        return f"http://{proxy_str}"

    def disable_proxy(self) -> None:
        """Tắt proxy — dùng IP thật."""
        self._proxies = []
        self._log.info("Proxy disabled.")

    def get_current_ip(self, proxy_url: Optional[str] = None) -> Optional[str]:
        """Lấy IP hiện tại (qua httpbin.org)."""
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}
        elif self._proxies:
            proxies = {"http": self._proxies[0], "https": self._proxies[0]}

        try:
            resp = requests.get(
                "http://httpbin.org/ip",
                proxies=proxies,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("origin")
        except requests.exceptions.RequestException as e:
            self._log.error(f"Get IP failed: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    #  Proxy Testing
    # ─────────────────────────────────────────────────────────────────────
    def test_proxy(self, proxy_to_test: Optional[str] = None) -> bool:
        """
        Test một proxy có hoạt động không.
        Nếu không truyền → test proxy mặc định.
        """
        proxy = proxy_to_test or (self._proxies[0] if self._proxies else None)
        if not proxy:
            self._log.warning("No proxy to test.")
            return False

        test_url = proxy_to_test or self._proxies[0]
        proxies = {"http": test_url, "https": test_url}

        try:
            resp = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=5)
            resp.raise_for_status()
            origin = resp.json().get("origin", "")
            self._log.info(f"✅ Proxy works! IP: {origin}")
            return True
        except requests.exceptions.RequestException:
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  Scrape Free Proxies
    # ─────────────────────────────────────────────────────────────────────
    def _scrape_proxies_from_url(self, url: str) -> List[str]:
        """Scrape proxies từ 1 URL."""
        proxies = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()

            # Parse bảng proxy
            table_match = re.search(
                r'<table[^>]*class="table[- ]?striped"[^>]*>(.*?)</table>',
                resp.text, re.DOTALL | re.IGNORECASE
            )
            if not table_match:
                return []

            table_html = table_match.group(1)
            rows = re.findall(r'<tr>(.*?)</tr>', table_html, re.DOTALL)

            for row in rows[1:]:  # Skip header row
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                if len(cells) >= 2:
                    ip   = re.sub(r'<[^>]+>', "", cells[0]).strip()
                    port = re.sub(r'<[^>]+>', "", cells[1]).strip()
                    if ip and port:
                        proto = "https" if "yes" in cells[6].lower() else "http"
                        proxies.append(f"{proto}://{ip}:{port}")

        except Exception as e:
            self._log.error(f"Scrape {url} failed: {e}")

        return proxies

    def get_free_proxies(self, force_refresh: bool = False) -> List[str]:
        """
        Lấy danh sách proxy miễn phí.
        Cache kết quả — refresh nếu force_refresh=True.
        """
        if self._free_proxies and not force_refresh:
            self._log.info(f"Dùng cache: {len(self._free_proxies)} free proxies")
            return self._free_proxies

        self._log.info("🔍 Scraping free proxies...")
        all_proxies: Dict[str, str] = {}

        for source_url in self.FREE_PROXY_SOURCES:
            scraped = self._scrape_proxies_from_url(source_url)
            for p in scraped:
                all_proxies[p] = p
            self._log.info(f"  {source_url}: +{len(scraped)} proxies")

        self._free_proxies = list(all_proxies.values())
        self._log.info(f"✅ Tổng cộng: {len(self._free_proxies)} free proxies")
        return self._free_proxies

    # ─────────────────────────────────────────────────────────────────────
    #  Find Working Free Proxy (multithread)
    # ─────────────────────────────────────────────────────────────────────
    def find_working_proxy(
        self,
        country_code: Optional[str] = None,
        protocol: Optional[str] = None,
        timeout: int = 10,
        max_threads: int = 10,
    ) -> Optional[str]:
        """
        Tìm proxy miễn phí hoạt động (multithreaded test).
        Trả về proxy đầu tiên pass test, hoặc None.
        """
        if not self._free_proxies:
            self.get_free_proxies()

        if not self._free_proxies:
            self._log.error("Không có free proxy để test.")
            return None

        self._log.info(f"🧪 Testing {len(self._free_proxies)} proxies với {max_threads} threads...")

        # Shuffle để phân bổ đều
        proxies_to_test = self._free_proxies.copy()
        random.shuffle(proxies_to_test)

        working    = []
        q          = Queue()
        lock       = threading.Lock()
        found_flag = threading.Event()

        for p in proxies_to_test:
            q.put(p)
        for _ in range(max_threads):
            q.put(None)  # Sentinel

        def worker():
            while True:
                proxy = q.get()
                if proxy is None:
                    break
                if found_flag.is_set():
                    q.task_done()
                    break

                proxies = {"http": proxy, "https": proxy}
                try:
                    resp = requests.get(
                        "http://httpbin.org/ip",
                        proxies=proxies,
                        timeout=timeout,
                    )
                    if resp.status_code == 200:
                        with lock:
                            if proxy not in working:
                                working.append(proxy)
                                found_flag.set()
                                self._log.info(f"✅ Found working proxy: {proxy}")
                except Exception:
                    pass
                finally:
                    q.task_done()

        threads = []
        for _ in range(max_threads):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        q.join()
        found_flag.set()

        if working:
            best = working[0]
            self._log.info(f"✅ Working proxy: {best}")
            return best

        self._log.warning("⚠️ Không tìm được proxy miễn phí hoạt động.")
        return None

    # ─────────────────────────────────────────────────────────────────────
    #  DB Integration
    # ─────────────────────────────────────────────────────────────────────
    def save_to_db(self, proxy_url: Optional[str] = None) -> Optional[int]:
        """Lưu proxy vào MySQL database."""
        if not self.db or not proxy_url:
            return None

        try:
            # Parse proxy URL
            parsed = self._parse_proxy_url(proxy_url)
            if not parsed:
                return None

            p = self.db.create_proxy(
                host=parsed["host"],
                port=parsed["port"],
                username=parsed.get("username"),
                password=parsed.get("password"),
                proxy_type=parsed.get("type", "http"),
                country=parsed.get("country"),
            )
            self._log.info(f"💾 Saved to DB: proxy #{p.id}")
            return p.id

        except Exception as e:
            self._log.error(f"Save proxy to DB failed: {e}")
            return None

    def _parse_proxy_url(self, proxy_url: str) -> Optional[Dict[str, Any]]:
        """Parse proxy URL thành dict {host, port, user, pass, type}."""
        try:
            # Bỏ protocol prefix
            clean = re.sub(r'^(http://|socks5://|socks4://)', '', proxy_url.strip())
            auth, host_port = clean.split('@') if '@' in clean else (None, clean)
            host, port_str = host_port.rsplit(':', 1)
            port = int(port_str)

            result = {"host": host, "port": port, "type": "http"}
            if auth and ':' in auth:
                result["username"], result["password"] = auth.split(':', 1)
                result["type"] = "socks5" if "socks5" in proxy_url else "http"

            return result
        except Exception:
            return None

    def load_proxies_from_db(self) -> List[Proxy]:
        """Load proxies active từ MySQL."""
        if not self.db:
            return []
        proxies = self.db.get_active_proxies()
        self._log.info(f"📥 Loaded {len(proxies)} proxies from DB")
        return proxies

    def get_proxy_for_account(self, account_id: int) -> Optional[str]:
        """
        Lấy proxy cho account cụ thể.
        Ưu tiên: proxy đã gán trước → random active proxy → None.
        """
        # Kiểm tra cache
        if account_id in self._cache:
            cached = self._cache[account_id]
            self._log.debug(f"Using cached proxy for account {account_id}: {cached}")
            return cached

        # Kiểm tra DB
        if self.db:
            acc = self.db.get_account_by_id(account_id)
            if acc and acc.proxy:
                self._cache[account_id] = acc.proxy
                return acc.proxy

        # Random proxy từ DB
        if self.db:
            proxy_record = self.db.get_random_proxy()
            if proxy_record:
                proxy_url = proxy_record.proxy_url
                self._cache[account_id] = proxy_url
                return proxy_url

        # Default proxy (từ list)
        if self._proxies:
            p = self._proxies[account_id % len(self._proxies)]
            self._cache[account_id] = p
            return p

        return None

    def release_proxy(self, account_id: int) -> None:
        """Giải phóng proxy khỏi cache (logout)."""
        self._cache.pop(account_id, None)

    def import_proxies_from_file(self, filepath: str) -> int:
        """Import proxies từ file text."""
        count = 0
        if not os.path.exists(filepath):
            self._log.error(f"File not found: {filepath}")
            return 0

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                proxy = self._normalize_proxy(line)
                if proxy:
                    self._proxies.append(proxy)
                    count += 1

        self._log.info(f"✅ Imported {count} proxies from file: {filepath}")
        return count

    # ─────────────────────────────────────────────────────────────────────
    #  Stats & Info
    # ─────────────────────────────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        """Thống kê proxy."""
        total_in_db = 0
        active_in_db = 0
        if self.db:
            all_proxies = self.db.session.query(Proxy).all()
            total_in_db  = len(all_proxies)
            active_in_db = sum(1 for p in all_proxies if p.status == "active")

        return {
            "configured":    len(self._proxies),
            "free_cached":  len(self._free_proxies),
            "db_total":     total_in_db,
            "db_active":    active_in_db,
            "account_cache": len(self._cache),
        }

    def __repr__(self):
        return (f"<ProxyManager(configured={len(self._proxies)}, "
                f"free={len(self._free_proxies)}, "
                f"cache={len(self._cache)})>")
