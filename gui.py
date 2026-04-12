# Snapchat Automation Platform v2.0 - Viral Content System
# Requires: pip install customtkinter Pillow loguru

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os
import sys
import threading
from datetime import datetime

# ─── Cấu hình giao diện ───────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "Snapchat Automation Platform v2.0"
APP_WIDTH = 1000
APP_HEIGHT = 750
LOG_DIR   = os.path.join(os.path.dirname(__file__), "logs")


# ═══════════════════════════════════════════════════════════════════════════
#  CỬA SỔ CHÍNH
# ═══════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # ── Biến trạng thái ──────────────────────────────────────────────
        self.log_lines   = []
        self.log_limit   = 500
        self.is_running  = False
        self.process_thread = None

        # ── Biến Widget ──────────────────────────────────────────────────
        self._vars = {}
        self._widgets = {}

        self._build_ui()
        self._load_assets()
        self._log("✅ Ứng dụng khởi động thành công.")
        self._log("ℹ️  Vui lòng điền đầy đủ thông tin trước khi bắt đầu.")

    # ─────────────────────────────────────────────────────────────────────
    #  XÂY DỰNG GIAO DIỆN
    # ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Thanh tiêu đề + Logo ─────────────────────────────────────────
        title_frame = ctk.CTkFrame(master=self, fg_color=("white", "#1A1A2E"), height=60)
        title_frame.pack(fill="x", padx=0, pady=(0, 0))
        title_frame.pack_propagate(False)

        lbl = ctk.CTkLabel(
            master=title_frame,
            text=f"  {APP_TITLE}",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=("#1A1A2E", "#00D1FF"),
        )
        lbl.pack(side="left", padx=20, pady=10)

        # ── Tabview chính ───────────────────────────────────────────────
        self.tabview = ctk.CTkTabview(self, fg_color=("white", "#16213E"))
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(5, 5))

        # Tạo các tab theo hethong.txt pipeline
        self.tab_scraper  = self.tabview.add("🔍 Scraper")
        self.tab_download = self.tabview.add("📥 Download")
        self.tab_process  = self.tabview.add("🎬 Process")
        self.tab_proxy    = self.tabview.add("🌐 Proxy")
        self.tab_music    = self.tabview.add("🎵 Nhạc")
        self.tab_snap     = self.tabview.add("📱 Snapchat")
        self.tab_analytics = self.tabview.add("📊 Analytics")
        self.tab_log      = self.tabview.add("📋 Nhật ký")

        self._build_scraper_tab()
        self._build_download_tab()
        self._build_process_tab()
        self._build_proxy_tab()
        self._build_music_tab()
        self._build_snap_tab()
        self._build_analytics_tab()
        self._build_log_tab()
        self._build_footer()

    # ═══════════════════════════════════════════════════════════════════════════
    #  CÁC TAB MỚI - Theo hethong.txt
    # ═══════════════════════════════════════════════════════════════════════════

    # ── TAB SCRAPER ─────────────────────────────────────────────────────────
    def _build_scraper_tab(self):
        f = self.tab_scraper
        ctk.CTkLabel(f, text="🔍 Tìm Video Viral (YouTube, TikTok, Douyin)",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        wrapper = ctk.CTkFrame(f, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=5)

        row_kw = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_kw.pack(fill="x", pady=4)
        ctk.CTkLabel(row_kw, text="Từ khóa tìm kiếm:", width=160, anchor="w").pack(side="left")
        self._vars["scrape_keywords"] = ctk.CTkEntry(
            row_kw, width=340, placeholder_text="sad edit, viral clip, anime edit (cách nhau bởi dấu phẩy)")
        self._vars["scrape_keywords"].pack(side="left")

        row_src = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_src.pack(fill="x", pady=4)
        ctk.CTkLabel(row_src, text="Nguồn:", width=160, anchor="w").pack(side="left")
        self._vars["scrape_sources"] = ctk.CTkOptionMenu(
            row_src, values=["Tất cả", "YouTube Shorts", "TikTok", "Douyin"], width=340)
        self._vars["scrape_sources"].set("YouTube Shorts")
        self._vars["scrape_sources"].pack(side="left")

        row_views = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_views.pack(fill="x", pady=4)
        ctk.CTkLabel(row_views, text="Views tối thiểu:", width=160, anchor="w").pack(side="left")
        self._vars["scrape_min_views"] = ctk.CTkEntry(row_views, width=340, placeholder_text="10000")
        self._vars["scrape_min_views"].insert(0, "10000")
        self._vars["scrape_min_views"].pack(side="left")

        row_dur = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_dur.pack(fill="x", pady=4)
        ctk.CTkLabel(row_dur, text="Thời lượng tối đa (s):", width=160, anchor="w").pack(side="left")
        self._vars["scrape_max_duration"] = ctk.CTkEntry(row_dur, width=340, placeholder_text="60")
        self._vars["scrape_max_duration"].insert(0, "60")
        self._vars["scrape_max_duration"].pack(side="left")

        row_max = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_max.pack(fill="x", pady=4)
        ctk.CTkLabel(row_max, text="Tối đa/khóa:", width=160, anchor="w").pack(side="left")
        self._vars["scrape_max_results"] = ctk.CTkEntry(row_max, width=340, placeholder_text="20")
        self._vars["scrape_max_results"].insert(0, "20")
        self._vars["scrape_max_results"].pack(side="left")

        ctk.CTkButton(wrapper, text="🔍 BẮT ĐẦU SCRAPE",
                      command=self._start_scrape, width=200,
                      fg_color="#00C896", hover_color="#00A87A").pack(pady=(10, 5))

        ctk.CTkLabel(f, text="📌 Kết quả scrape sẽ tự động chuyển sang tab Download.",
                     font=ctk.CTkFont(size=11), text_color=("gray40", "#AAAAAA")).pack(pady=(0, 15))

    # ── TAB DOWNLOAD ────────────────────────────────────────────────────────
    def _build_download_tab(self):
        f = self.tab_download
        ctk.CTkLabel(f, text="📥 Download Video",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        wrapper = ctk.CTkFrame(f, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=5)

        def file_row(label, var_key, placeholder_text=""):
            row = ctk.CTkFrame(wrapper, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=160, anchor="w").pack(side="left")
            self._vars[var_key] = ctk.CTkEntry(row, width=240, placeholder_text=placeholder_text)
            self._vars[var_key].pack(side="left", padx=(0, 5))
            ctk.CTkButton(row, text="📂 Chọn", width=80,
                          command=lambda k=var_key: self._browse_file(k)).pack(side="left")
            return row

        file_row("File URLs (.txt):", "download_url_file", "Danh sách URL/video cần tải")

        row_out = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_out.pack(fill="x", pady=4)
        ctk.CTkLabel(row_out, text="Thư mục lưu:", width=160, anchor="w").pack(side="left")
        self._vars["download_output"] = ctk.CTkEntry(row_out, width=340,
                                                      placeholder_text="uploads/video")
        self._vars["download_output"].insert(0, "uploads/video")
        self._vars["download_output"].pack(side="left")

        row_con = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_con.pack(fill="x", pady=4)
        ctk.CTkLabel(row_con, text="Concurrency:", width=160, anchor="w").pack(side="left")
        self._vars["download_concurrency"] = ctk.CTkOptionMenu(
            row_con, values=["1 (tuần tự)", "2", "3"], width=340)
        self._vars["download_concurrency"].set("2")
        self._vars["download_concurrency"].pack(side="left")

        ctk.CTkButton(wrapper, text="📥 BẮT ĐẦU DOWNLOAD",
                      command=self._start_download, width=200,
                      fg_color="#00C896", hover_color="#00A87A").pack(pady=(10, 5))
        ctk.CTkButton(wrapper, text="📺 Download từ Scraper",
                      command=self._download_from_scraper, width=200).pack(pady=(5, 15))

    # ── TAB PROCESS ─────────────────────────────────────────────────────────
    def _build_process_tab(self):
        f = self.tab_process
        ctk.CTkLabel(f, text="🎬 Xử lý Video (FFmpeg)",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        wrapper = ctk.CTkFrame(f, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=5)

        def file_row(label, var_key, placeholder_text=""):
            row = ctk.CTkFrame(wrapper, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=160, anchor="w").pack(side="left")
            self._vars[var_key] = ctk.CTkEntry(row, width=240, placeholder_text=placeholder_text)
            self._vars[var_key].pack(side="left", padx=(0, 5))
            ctk.CTkButton(row, text="📂 Chọn", width=80,
                          command=lambda k=var_key: self._browse_file(k)).pack(side="left")
            return row

        file_row("Video nguồn:", "process_video_in", "Video cần xử lý")
        file_row("Nhạc nền:", "process_music_in", "File nhạc (.mp3)")

        row_dur = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_dur.pack(fill="x", pady=4)
        ctk.CTkLabel(row_dur, text="Cắt thời lượng (s):", width=160, anchor="w").pack(side="left")
        self._vars["process_duration"] = ctk.CTkEntry(row_dur, width=340, placeholder_text="15")
        self._vars["process_duration"].insert(0, "15")
        self._vars["process_duration"].pack(side="left")

        row_text = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_text.pack(fill="x", pady=4)
        ctk.CTkLabel(row_text, text="Text overlay:", width=160, anchor="w").pack(side="left")
        self._vars["process_text"] = ctk.CTkEntry(row_text, width=340, placeholder_text="Thêm text (tùy chọn)")
        self._vars["process_text"].pack(side="left")

        row_opts = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_opts.pack(fill="x", pady=6)
        self._vars["process_add_blur"]   = ctk.CTkCheckBox(row_opts, text="Thêm blur edge", onvalue=True, offvalue=False)
        self._vars["process_add_blur"].select()
        self._vars["process_add_blur"].pack(side="left", padx=(0, 15))
        self._vars["process_add_zoom"]   = ctk.CTkCheckBox(row_opts, text="Thêm zoom effect", onvalue=True, offvalue=False)
        self._vars["process_add_zoom"].pack(side="left")

        ctk.CTkButton(wrapper, text="🎬 BẮT ĐẦU XỬ LÝ",
                      command=self._start_process_video, width=200,
                      fg_color="#00C896", hover_color="#00A87A").pack(pady=(10, 5))
        ctk.CTkLabel(f, text="📌 Video sau xử lý sẽ ở định dạng 9:16 (dọc), sẵn sàng upload Snapchat.",
                     font=ctk.CTkFont(size=11), text_color=("gray40", "#AAAAAA")).pack(pady=(0, 15))

    # ── TAB ANALYTICS ────────────────────────────────────────────────────────
    def _build_analytics_tab(self):
        f = self.tab_analytics
        ctk.CTkLabel(f, text="📊 Thống kê & Scaling",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        # Stats display area
        self._vars["analytics_stats"] = ctk.CTkTextbox(
            f, width=920, height=200,
            font=ctk.CTkFont(size=13, family="Consolas"),
            fg_color=("white", "#0F0F23"), text_color=("black", "#00FF99"),
            border_width=0)
        self._vars["analytics_stats"].pack(fill="x", padx=20, pady=5)
        self._vars["analytics_stats"].insert("1.0",
            "📊 Nhấn 'Tải thống kê' để xem dữ liệu...")

        row_btns = ctk.CTkFrame(f, fg_color="transparent")
        row_btns.pack(pady=(5, 5))
        ctk.CTkButton(row_btns, text="📊 Tải thống kê",
                      command=self._load_stats, width=160).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_btns, text="🏆 Winning Content",
                      command=self._load_winning, width=160).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_btns, text="📈 Scale từ Winning",
                      command=self._scale_winning, width=160).pack(side="left")

        # Recommendations
        ctk.CTkLabel(f, text="💡 Khuyến nghị Scaling:",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(10, 3))
        self._vars["analytics_recos"] = ctk.CTkTextbox(
            f, width=920, height=120,
            font=ctk.CTkFont(size=12, family="Consolas"),
            fg_color=("white", "#0F0F23"), text_color=("black", "#FFD700"),
            border_width=0)
        self._vars["analytics_recos"].pack(fill="x", padx=20, pady=(0, 15))

    # ── TAB PROXY (nâng cấp) ──────────────────────────────────────────────
    def _build_proxy_tab(self):
        f = self.tab_proxy
        ctk.CTkLabel(f, text="🌐 Proxy Manager — Tích hợp user's code + System",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        # ── Row 1: Cấu hình proxy tùy chỉnh ──────────────────────────────
        wrapper = ctk.CTkFrame(f, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=5)

        row_type = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_type.pack(fill="x")
        ctk.CTkLabel(row_type, text="Loại proxy:", width=140, anchor="w").pack(side="left")
        self._vars["proxy_type"] = ctk.CTkOptionMenu(
            row_type, values=["HTTP", "SOCKS5", "VPN (chạy thủ công)", "Không dùng proxy"],
            width=280)
        self._vars["proxy_type"].pack(side="left")
        self._vars["proxy_type"].set("Không dùng proxy")

        row_addr = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_addr.pack(fill="x", pady=4)
        ctk.CTkLabel(row_addr, text="Địa chỉ proxy:", width=140, anchor="w").pack(side="left")
        self._vars["proxy_addr"] = ctk.CTkEntry(
            row_addr, placeholder_text="Ví dụ: 123.45.67.89:8080 hoặc http://user:pass@ip:port", width=280)
        self._vars["proxy_addr"].pack(side="left")

        row_user = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_user.pack(fill="x", pady=4)
        ctk.CTkLabel(row_user, text="User proxy:", width=140, anchor="w").pack(side="left")
        self._vars["proxy_user"] = ctk.CTkEntry(row_user, placeholder_text="Username (nếu có)", width=280)
        self._vars["proxy_user"].pack(side="left")

        row_pass = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_pass.pack(fill="x", pady=4)
        ctk.CTkLabel(row_pass, text="Pass proxy:", width=140, anchor="w").pack(side="left")
        self._vars["proxy_pass"] = ctk.CTkEntry(row_pass, placeholder_text="Password (nếu có)", width=280, show="●")
        self._vars["proxy_pass"].pack(side="left")

        row_btns = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_btns.pack(fill="x", pady=(10, 4))
        ctk.CTkButton(row_btns, text="🔍 Test Proxy", command=self._test_proxy,
                      width=130).pack(side="left", padx=(0, 5))
        ctk.CTkButton(row_btns, text="💾 Lưu vào DB", command=self._save_proxy_to_db,
                      width=130).pack(side="left", padx=(0, 5))
        ctk.CTkButton(row_btns, text="🌍 Get Current IP", command=self._get_current_ip,
                      width=130).pack(side="left")

        sep_frame = ctk.CTkFrame(f, fg_color=("white", "#1A1A2E"), height=2)
        sep_frame.pack(fill="x", padx=20, pady=(5, 5))
        sep_frame.pack_propagate(False)

        # ── Row 2: Free Proxy Scraper ─────────────────────────────────────
        ctk.CTkLabel(f, text="🔓 Free Proxy Scraper (đa luồng)",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(8, 4))

        wrapper2 = ctk.CTkFrame(f, fg_color="transparent")
        wrapper2.pack(fill="x", padx=20, pady=5)

        row_threads = ctk.CTkFrame(wrapper2, fg_color="transparent")
        row_threads.pack(fill="x", pady=4)
        ctk.CTkLabel(row_threads, text="Threads test:", width=140, anchor="w").pack(side="left")
        self._vars["proxy_threads"] = ctk.CTkOptionMenu(row_threads,
            values=["5", "10", "15", "20"], width=280)
        self._vars["proxy_threads"].set("10")
        self._vars["proxy_threads"].pack(side="left")

        row_timeout = ctk.CTkFrame(wrapper2, fg_color="transparent")
        row_timeout.pack(fill="x", pady=4)
        ctk.CTkLabel(row_timeout, text="Timeout (s):", width=140, anchor="w").pack(side="left")
        self._vars["proxy_timeout"] = ctk.CTkEntry(row_timeout, width=280, placeholder_text="10")
        self._vars["proxy_timeout"].insert(0, "10")
        self._vars["proxy_timeout"].pack(side="left")

        row_free_btns = ctk.CTkFrame(wrapper2, fg_color="transparent")
        row_free_btns.pack(fill="x", pady=(8, 4))
        ctk.CTkButton(row_free_btns, text="🔍 Scrape Free Proxies",
                      command=self._scrape_free_proxies, width=180,
                      fg_color="#E84545", hover_color="#C73535").pack(side="left", padx=(0, 5))
        ctk.CTkButton(row_free_btns, text="🧪 Find Working Proxy",
                      command=self._find_working_proxy, width=180,
                      fg_color="#00C896", hover_color="#00A87A").pack(side="left", padx=(0, 5))
        ctk.CTkButton(row_free_btns, text="📁 Import from File",
                      command=self._import_proxy_file, width=150).pack(side="left")

        self._vars["proxy_status_text"] = ctk.CTkLabel(f, text="",
            font=ctk.CTkFont(size=11), text_color=("gray40", "#AAAAAA"))
        self._vars["proxy_status_text"].pack(pady=(4, 15))

    # ── TAB NHẠC ─────────────────────────────────────────────────────────
    def _build_music_tab(self):
        f = self.tab_music
        ctk.CTkLabel(f, text="Tải nhạc lên dịch vụ phân phối (Ditto Music)",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        wrapper = ctk.CTkFrame(f, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=5)

        def entry_row(label, var_key, width=300, show=None):
            row = ctk.CTkFrame(wrapper, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=170, anchor="w").pack(side="left")
            self._vars[var_key] = ctk.CTkEntry(row, width=width, show=show)
            self._vars[var_key].pack(side="left")
            return row

        def file_row(label, var_key):
            row = ctk.CTkFrame(wrapper, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=170, anchor="w").pack(side="left")
            self._vars[var_key] = ctk.CTkEntry(row, width=240)
            self._vars[var_key].pack(side="left", padx=(0, 5))
            ctk.CTkButton(row, text="📂 Chọn file", width=90,
                          command=lambda k=var_key: self._browse_file(k)).pack(side="left")
            return row

        entry_row("Tài khoản Ditto:", "ditto_user")
        entry_row("Mật khẩu Ditto:", "ditto_pass", show="●")
        entry_row("Tên bài hát:", "music_title")
        entry_row("Tên nghệ sĩ:", "music_artist")

        file_row("File nhạc (.mp3 / .wav):", "music_file")

        row_lang = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_lang.pack(fill="x", pady=4)
        ctk.CTkLabel(row_lang, text="Ngôn ngữ:", width=170, anchor="w").pack(side="left")
        self._vars["music_lang"] = ctk.CTkOptionMenu(row_lang, values=["Tiếng Việt", "Tiếng Anh", "Khác"], width=300)
        self._vars["music_lang"].set("Tiếng Việt")
        self._vars["music_lang"].pack(side="left")

        note = ctk.CTkLabel(f, text="📌 Nhạc sẽ được tải lên Ditto Music trước, sau đó dùng cho Snapchat.",
                            font=ctk.CTkFont(size=11), text_color=("gray40", "#AAAAAA"))
        note.pack(pady=(10, 15))

    # ── TAB VIDEO ─────────────────────────────────────────────────────────
    def _build_video_tab(self):
        f = self.tab_video
        ctk.CTkLabel(f, text="Quản lý Video trước khi đăng lên Snapchat",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        wrapper = ctk.CTkFrame(f, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=5)

        def file_row(label, var_key):
            row = ctk.CTkFrame(wrapper, fg_color="transparent")
            row.pack(fill="x", pady=6)
            ctk.CTkLabel(row, text=label, width=170, anchor="w").pack(side="left")
            self._vars[var_key] = ctk.CTkEntry(row, width=240)
            self._vars[var_key].pack(side="left", padx=(0, 5))
            ctk.CTkButton(row, text="📂 Chọn file", width=90,
                          command=lambda k=var_key: self._browse_file(k)).pack(side="left")
            return row

        file_row("File video (.mp4):", "video_file")

        row_title = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_title.pack(fill="x", pady=4)
        ctk.CTkLabel(row_title, text="Tiêu đề video:", width=170, anchor="w").pack(side="left")
        self._vars["video_title"] = ctk.CTkEntry(row_title, width=300, placeholder_text="Tên hiển thị trên Snapchat")
        self._vars["video_title"].pack(side="left")

        row_desc = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_desc.pack(fill="x", pady=4)
        ctk.CTkLabel(row_desc, text="Mô tả:", width=170, anchor="w").pack(side="left")
        self._vars["video_desc"] = ctk.CTkTextbox(row_desc, width=300, height=70)
        self._vars["video_desc"].pack(side="left")

        row_tags = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_tags.pack(fill="x", pady=4)
        ctk.CTkLabel(row_tags, text="Thẻ (tags):", width=170, anchor="w").pack(side="left")
        self._vars["video_tags"] = ctk.CTkEntry(row_tags, width=300, placeholder_text="#music #cover #viral")
        self._vars["video_tags"].pack(side="left")

        sep = ctk.CTkLabel(f, text="")
        sep.pack()

        info = ctk.CTkLabel(f,
            text="📌 Định dạng khuyến nghị: MP4, ≤ 60 giây, tỉ lệ 9:16 (dọc), ≤ 280MB\n"
                 "   Video sẽ được kiểm tra tự động trước khi tải lên Snapchat.",
            font=ctk.CTkFont(size=11), text_color=("gray40", "#AAAAAA"), justify="left")
        info.pack(pady=(5, 15), padx=20, anchor="w")

    # ── TAB SNAPCHAT ──────────────────────────────────────────────────────
    def _build_snap_tab(self):
        f = self.tab_snap
        ctk.CTkLabel(f, text="Đăng nhập & Đăng video lên Snapchat",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))

        wrapper = ctk.CTkFrame(f, fg_color="transparent")
        wrapper.pack(fill="x", padx=20, pady=5)

        def entry_row(label, var_key, width=300, show=None):
            row = ctk.CTkFrame(wrapper, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=170, anchor="w").pack(side="left")
            self._vars[var_key] = ctk.CTkEntry(row, width=width, show=show)
            self._vars[var_key].pack(side="left")
            return row

        entry_row("Tài khoản Snapchat:", "snap_user")
        entry_row("Mật khẩu Snapchat:", "snap_pass", show="●")
        entry_row("Cookie Snapchat (tùy):", "snap_cookie", width=300)

        # Tùy chọn bổ sung
        sep_frame = ctk.CTkFrame(wrapper, fg_color="transparent")
        sep_frame.pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(sep_frame, text="Tùy chọn bổ sung:",
                     font=ctk.CTkFont(weight="bold"), anchor="w").pack(side="left")

        row_opt = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_opt.pack(fill="x", pady=4)
        ctk.CTkLabel(row_opt, text="Chế độ:", width=170, anchor="w").pack(side="left")
        self._vars["snap_mode"] = ctk.CTkOptionMenu(row_opt,
            values=["Tạo kênh mới", "Dùng kênh hiện có", "Kiểm tra trạng thái"],
            width=300)
        self._vars["snap_mode"].set("Tạo kênh mới")
        self._vars["snap_mode"].pack(side="left")

        row_vis = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_vis.pack(fill="x", pady=4)
        ctk.CTkLabel(row_vis, text="Hiển thị trình duyệt:", width=170, anchor="w").pack(side="left")
        self._vars["snap_headless"] = ctk.CTkOptionMenu(row_vis,
            values=["Có (mặc định)", "Không (debug)"],
            width=300)
        self._vars["snap_headless"].set("Có (mặc định)")
        self._vars["snap_headless"].pack(side="left")

        row_wait = ctk.CTkFrame(wrapper, fg_color="transparent")
        row_wait.pack(fill="x", pady=4)
        ctk.CTkLabel(row_wait, text="Thời gian chờ (giây):", width=170, anchor="w").pack(side="left")
        self._vars["snap_wait"] = ctk.CTkEntry(row_wait, width=300, placeholder_text="10")
        self._vars["snap_wait"].insert(0, "10")
        self._vars["snap_wait"].pack(side="left")

        note = ctk.CTkLabel(f,
            text="📌 Chế độ \"Không hiển thị\" dùng để debug nếu bị lỗi.",
            font=ctk.CTkFont(size=11), text_color=("gray40", "#AAAAAA"))
        note.pack(pady=(10, 15))

    # ── TAB NHẬT KÝ ───────────────────────────────────────────────────────
    def _build_log_tab(self):
        f = self.tab_log

        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 0))
        ctk.CTkLabel(header, text="📋 Nhật ký hoạt động",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="🗑️ Xóa log", width=90,
                      command=self._clear_log).pack(side="right")
        ctk.CTkButton(header, text="💾 Lưu log", width=90,
                      command=self._save_log).pack(side="right", padx=5)

        textbox_frame = ctk.CTkFrame(f, fg_color=("white", "#0F0F23"))
        textbox_frame.pack(fill="both", expand=True, padx=15, pady=(8, 10))

        self.log_textbox = ctk.CTkTextbox(
            textbox_frame, font=("Consolas", 11),
            fg_color=("white", "#0F0F23"),
            text_color=("black", "#00FF99"),
            border_width=0, activate_scrollbars=True)
        self.log_textbox.pack(fill="both", expand=True)

    # ── FOOTER + NÚT CHẠY ─────────────────────────────────────────────────
    def _build_footer(self):
        footer = ctk.CTkFrame(self, height=70, fg_color=("white", "#0F3460"))
        footer.pack(fill="x", padx=10, pady=(0, 10))
        footer.pack_propagate(False)

        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=8)

        self.btn_start = ctk.CTkButton(
            inner, text="▶  BẮT ĐẦU QUY TRÌNH TỰ ĐỘNG",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#00C896", "#00C896"), hover_color=("#00A87A", "#00A87A"),
            text_color="white", height=42,
            command=self._start_process)
        self.btn_start.pack(side="right")

        self.btn_stop = ctk.CTkButton(
            inner, text="⏹  DỪNG LẠI",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#E84545", "#E84545"), hover_color=("#C73535", "#C73535"),
            text_color="white", height=42, state="disabled",
            command=self._stop_process)
        self.btn_stop.pack(side="right", padx=(0, 10))

        status_text = ctk.CTkLabel(
            inner, text="Trạng thái: Sẵn sàng",
            font=ctk.CTkFont(size=11), text_color=("gray40", "#AAAAAA"))
        status_text.pack(side="left")
        self._vars["status_label"] = status_text  # gán widget vào biến

    # ─────────────────────────────────────────────────────────────────────
    #  TẢI TÀI NGUYÊN
    # ─────────────────────────────────────────────────────────────────────
    def _load_assets(self):
        os.makedirs(LOG_DIR, exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────
    #  TRIGGER LOG
    # ─────────────────────────────────────────────────────────────────────
    def _log(self, msg, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}"
        self.log_lines.append(line)

        color_map = {
            "INFO":  "#00FF99",
            "WARN":  "#FFD700",
            "ERROR": "#FF4444",
            "STEP":  "#00D1FF",
        }
        fg = color_map.get(level, "#00FF99")

        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", line + "\n", (level,))
        self.log_textbox.tag_config("INFO", foreground="#00FF99")
        self.log_textbox.tag_config("WARN", foreground="#FFD700")
        self.log_textbox.tag_config("ERROR", foreground="#FF4444")
        self.log_textbox.tag_config("STEP", foreground="#00D1FF")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

        if len(self.log_lines) > self.log_limit:
            excess = len(self.log_lines) - self.log_limit
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", f"{excess+1}.0")
            self.log_textbox.configure(state="disabled")
            self.log_lines = self.log_lines[excess:]

    # ─────────────────────────────────────────────────────────────────────
    #  TIỆN ÍCH GIAO DIỆN
    # ─────────────────────────────────────────────────────────────────────
    def _browse_file(self, var_key):
        path = filedialog.askopenfilename(
            title="Chọn file",
            filetypes=[("Tất cả", "*.*"), ("MP3", "*.mp3"), ("MP4", "*.mp4"), ("WAV", "*.wav")])
        if path:
            self._vars[var_key].delete(0, "end")
            self._vars[var_key].insert(0, path)

    def _clear_log(self):
        self.log_lines.clear()
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            title="Lưu nhật ký",
            initialdir=LOG_DIR,
            defaultextension=".log",
            filetypes=[("Log file", "*.log"), ("Text file", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.log_lines))
            self._log(f"💾 Đã lưu nhật ký: {path}")

    def _get_var(self, key):
        w = self._vars.get(key)
        if w is None:
            return ""
        if isinstance(w, ctk.CTkEntry):
            return w.get().strip()
        if isinstance(w, ctk.CTkOptionMenu):
            return w.get().strip()
        if isinstance(w, ctk.CTkTextbox):
            return w.get("1.0", "end").strip()
        return ""

    # ─────────────────────────────────────────────────────────────────────
    #  PROXY HANDLERS - Tích hợp user's ProxyManager code
    # ─────────────────────────────────────────────────────────────────────
    def _get_proxy_manager(self):
        """Lazy-load ProxyManager với DB integration."""
        try:
            from modules.core.proxy_manager import ProxyManager
            from modules.database import Database
            db = Database()
            return ProxyManager(db=db)
        except Exception as e:
            self._log(f"❌ Lỗi khởi tạo ProxyManager: {e}", "ERROR")
            return None

    def _test_proxy(self):
        self._log("🧪 Testing proxy...", "STEP")
        pm = self._get_proxy_manager()
        if not pm:
            return
        p_type = self._get_var("proxy_type")
        p_addr = self._get_var("proxy_addr")
        p_user = self._get_var("proxy_user")
        p_pass = self._get_var("proxy_pass")

        if p_type == "Không dùng proxy":
            self._log("ℹ️ Không dùng proxy.", "INFO")
            return
        if not p_addr:
            self._log("⚠️ Chưa nhập địa chỉ proxy.", "WARN")
            return

        # Build full proxy URL
        if p_user and p_pass:
            proxy_url = f"{p_type.lower()}://{p_user}:{p_pass}@{p_addr}"
        else:
            proxy_url = f"{p_type.lower()}://{p_addr}"

        ok = pm.test_proxy(proxy_url)
        if ok:
            self._log("✅ Proxy hoạt động!", "INFO")
            ip = pm.get_current_ip(proxy_url)
            if ip:
                self._log(f"🌍 IP hiện tại: {ip}", "STEP")
        else:
            self._log("❌ Proxy không hoạt động!", "ERROR")

    def _get_current_ip(self):
        self._log("🌍 Đang lấy IP hiện tại...", "STEP")
        pm = self._get_proxy_manager()
        if not pm:
            return
        p_type = self._get_var("proxy_type")
        p_addr = self._get_var("proxy_addr")
        p_user = self._get_var("proxy_user")
        p_pass = self._get_var("proxy_pass")

        proxy_url = None
        if p_addr and p_type != "Không dùng proxy":
            if p_user and p_pass:
                proxy_url = f"{p_type.lower()}://{p_user}:{p_pass}@{p_addr}"
            else:
                proxy_url = f"{p_type.lower()}://{p_addr}"

        ip = pm.get_current_ip(proxy_url)
        if ip:
            self._log(f"🌍 IP: {ip}", "STEP")
        else:
            self._log("❌ Không lấy được IP.", "ERROR")

    def _save_proxy_to_db(self):
        self._log("💾 Đang lưu proxy vào DB...", "STEP")
        pm = self._get_proxy_manager()
        if not pm:
            return
        p_type = self._get_var("proxy_type")
        p_addr = self._get_var("proxy_addr")
        p_user = self._get_var("proxy_user")
        p_pass = self._get_var("proxy_pass")

        if p_type == "Không dùng proxy" or not p_addr:
            self._log("⚠️ Không có proxy để lưu.", "WARN")
            return

        if p_user and p_pass:
            proxy_url = f"{p_type.lower()}://{p_user}:{p_pass}@{p_addr}"
        else:
            proxy_url = f"{p_type.lower()}://{p_addr}"

        pid = pm.save_to_db(proxy_url)
        if pid:
            self._log(f"✅ Đã lưu proxy vào DB (ID: {pid})", "INFO")
        else:
            self._log("❌ Lưu proxy thất bại.", "ERROR")

    def _scrape_free_proxies(self):
        self._log("🔍 Scraping free proxies từ free-proxy-list.net...", "STEP")
        self._vars["proxy_status_text"].configure(text="⏳ Đang scrape...")
        threading.Thread(target=self._scrape_proxies_bg, daemon=True).start()

    def _scrape_proxies_bg(self):
        try:
            pm = self._get_proxy_manager()
            if not pm:
                self.after(0, lambda: self._vars["proxy_status_text"].configure(text="❌ Lỗi"))
                return
            proxies = pm.get_free_proxies(force_refresh=True)
            self.after(0, lambda: self._vars["proxy_status_text"].configure(
                text=f"✅ Tìm thấy {len(proxies)} free proxies"))
            self._log(f"✅ Scraped {len(proxies)} free proxies", "STEP")
        except Exception as e:
            self.after(0, lambda: self._vars["proxy_status_text"].configure(text=f"❌ Lỗi: {e}"))
            self._log(f"❌ Scrape failed: {e}", "ERROR")

    def _find_working_proxy(self):
        self._log("🧪 Đang tìm proxy hoạt động (multithread test)...", "STEP")
        self._vars["proxy_status_text"].configure(text="⏳ Đang test proxies...")
        threading.Thread(target=self._find_proxy_bg, daemon=True).start()

    def _find_proxy_bg(self):
        try:
            pm = self._get_proxy_manager()
            if not pm:
                self.after(0, lambda: self._vars["proxy_status_text"].configure(text="❌ Lỗi"))
                return
            threads = int(self._get_var("proxy_threads") or "10")
            timeout = int(self._get_var("proxy_timeout") or "10")
            working = pm.find_working_proxy(max_threads=threads, timeout=timeout)
            if working:
                self.after(0, lambda: self._vars["proxy_status_text"].configure(
                    text=f"✅ Working proxy: {working}"))
                self._log(f"✅ Found working proxy: {working}", "STEP")
                # Auto-fill proxy fields
                self.after(0, lambda: self._vars["proxy_addr"].delete(0, "end"))
                self.after(0, lambda: self._vars["proxy_addr"].insert(0, working.replace("http://", "").replace("https://", "")))
            else:
                self.after(0, lambda: self._vars["proxy_status_text"].configure(
                    text="❌ Không tìm được proxy hoạt động"))
                self._log("❌ Không tìm được proxy hoạt động nào.", "ERROR")
        except Exception as e:
            self.after(0, lambda: self._vars["proxy_status_text"].configure(text=f"❌ Lỗi: {e}"))

    def _import_proxy_file(self):
        path = filedialog.askopenfilename(title="Chọn file proxy",
            filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        pm = self._get_proxy_manager()
        if not pm:
            return
        count = pm.import_proxies_from_file(path)
        self._log(f"✅ Imported {count} proxies từ {path}", "INFO")
        self._vars["proxy_status_text"].configure(text=f"📁 Đã import {count} proxies")

    # ─────────────────────────────────────────────────────────────────────
    #  SCRAPER / DOWNLOAD / PROCESS / ANALYTICS HANDLERS
    # ─────────────────────────────────────────────────────────────────────
    def _start_scrape(self):
        keywords_raw = self._get_var("scrape_keywords")
        if not keywords_raw:
            messagebox.showwarning("Thiếu", "Nhập ít nhất 1 từ khóa tìm kiếm!")
            return
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        self._log(f"🔍 Bắt đầu scrape: {keywords}", "STEP")
        threading.Thread(target=self._scrape_bg, args=(keywords,), daemon=True).start()

    def _scrape_bg(self, keywords):
        import asyncio
        try:
            from modules.automation.scraper import ViralVideoScraper
            scraper = ViralVideoScraper()
            min_views = int(self._get_var("scrape_min_views") or "10000")
            max_dur   = int(self._get_var("scrape_max_duration") or "60")
            max_res   = int(self._get_var("scrape_max_results") or "20")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(scraper.scrape(
                keywords=keywords,
                min_views=min_views,
                max_duration_sec=max_dur,
                max_results=max_res,
            ))
            loop.close()
            self.after(0, lambda: self._log(f"✅ Scrape done: {len(results)} videos", "STEP"))
        except Exception as e:
            self.after(0, lambda: self._log(f"❌ Scrape error: {e}", "ERROR"))

    def _start_download(self):
        self._log("📥 Bắt đầu download...", "STEP")
        threading.Thread(target=self._download_bg, daemon=True).start()

    def _download_bg(self):
        import asyncio
        try:
            from modules.automation.download import VideoDownloader
            url_file = self._get_var("download_url_file")
            out_dir  = self._get_var("download_output") or "uploads/video"
            dl = VideoDownloader(output_dir=out_dir)
            urls = []
            if url_file and os.path.exists(url_file):
                with open(url_file, "r", encoding="utf-8") as f:
                    urls = [{"source_url": u.strip()} for u in f if u.strip()]
            if not urls:
                self.after(0, lambda: self._log("⚠️ Không có URL nào để download.", "WARN"))
                return
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(dl.download_batch(urls))
            loop.close()
            ok = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            self.after(0, lambda: self._log(f"✅ Download hoàn tất: {ok}/{len(urls)} videos", "STEP"))
        except Exception as e:
            self.after(0, lambda: self._log(f"❌ Download error: {e}", "ERROR"))

    def _download_from_scraper(self):
        self._log("📺 Đang chuyển từ Scraper → Download...", "STEP")

    def _start_process_video(self):
        video_in = self._get_var("process_video_in")
        if not video_in:
            messagebox.showwarning("Thiếu", "Chọn video cần xử lý!")
            return
        self._log("🎬 Bắt đầu xử lý video...", "STEP")
        threading.Thread(target=self._process_bg, daemon=True).start()

    def _process_bg(self):
        import asyncio
        try:
            from modules.automation.processor import VideoProcessor
            vp = VideoProcessor()
            result = asyncio.get_event_loop().run_until_complete(vp.process(
                video_path=self._get_var("process_video_in"),
                music_path=self._get_var("process_music_in") or None,
                duration_sec=float(self._get_var("process_duration") or "15"),
                add_text=self._get_var("process_text") or None,
                add_blur=self._get_var("process_add_blur") == True,
                add_zoom=self._get_var("process_add_zoom") == True,
            ))
            ok = result.get("success", False)
            out = result.get("output_path", "")
            self.after(0, lambda: self._log(
                f"{'✅' if ok else '❌'} Process video: {out}", "STEP" if ok else "ERROR"))
        except Exception as e:
            self.after(0, lambda: self._log(f"❌ Process error: {e}", "ERROR"))

    def _load_stats(self):
        try:
            from modules.automation.analytics import AnalyticsTracker
            from modules.database import Database
            db = Database()
            tracker = AnalyticsTracker(db=db)
            stats = tracker.get_stats()
            self._vars["analytics_stats"].configure(state="normal")
            self._vars["analytics_stats"].delete("1.0", "end")
            lines = [
                f"📊 THỐNG KÊ HỆ THỐNG",
                f"───────────────────────────────────────────",
                f"  Videos scraped:    {stats.get('total_videos', 0)}",
                f"  Winning videos:     {stats.get('winning_videos', 0)}  (>10k views)",
                f"  Videos uploaded:    {stats.get('uploaded_videos', 0)}",
                f"  Total views:       {stats.get('total_views', 0):,}",
                f"  Total likes:       {stats.get('total_likes', 0):,}",
                f"  Total shares:      {stats.get('total_shares', 0):,}",
                f"  Active accounts:   {stats.get('active_accounts', 0)}",
                f"  Scale Level:       {stats.get('scale_level', 'N/A')}",
            ]
            self._vars["analytics_stats"].insert("1.0", "\n".join(lines))
            self._vars["analytics_stats"].configure(state="disabled")
        except Exception as e:
            self._log(f"❌ Load stats error: {e}", "ERROR")

    def _load_winning(self):
        try:
            from modules.automation.analytics import AnalyticsTracker
            from modules.database import Database
            tracker = AnalyticsTracker(db=Database())
            winners = tracker.get_winning_videos()
            self._vars["analytics_stats"].configure(state="normal")
            self._vars["analytics_stats"].delete("1.0", "end")
            if not winners:
                self._vars["analytics_stats"].insert("1.0", "🏆 Chưa có winning content.\nHãy upload thêm video để đạt >10k views!")
            else:
                lines = ["🏆 WINNING CONTENT (>10k views)", "─" * 40]
                for v in winners[:10]:
                    lines.append(f"  Video #{v['video_id']}: {v['views']:,} views | {v['likes']:,} likes")
                self._vars["analytics_stats"].insert("1.0", "\n".join(lines))
            self._vars["analytics_stats"].configure(state="disabled")
        except Exception as e:
            self._log(f"❌ Load winning error: {e}", "ERROR")

    def _scale_winning(self):
        self._log("📈 Tạo scale jobs từ winning content...", "STEP")
        try:
            from modules.automation.analytics import AnalyticsTracker
            from modules.database import Database
            tracker = AnalyticsTracker(db=Database())
            winners = tracker.get_winning_videos()
            if not winners:
                self._log("⚠️ Không có winning content để scale.", "WARN")
                return
            top = winners[0]
            job_ids = tracker.create_scale_jobs_from_winning(top["video_id"], num_copies=3)
            self._log(f"✅ Đã tạo {len(job_ids)} scale jobs từ winning video #{top['video_id']}", "STEP")
        except Exception as e:
            self._log(f"❌ Scale error: {e}", "ERROR")

    def _check_proxy(self):
        self._log("🔍 Đang kiểm tra kết nối proxy...", "STEP")
        p_type  = self._get_var("proxy_type")
        p_addr  = self._get_var("proxy_addr")
        if p_type == "Không dùng proxy":
            self._log("ℹ️ Không sử dụng proxy.", "INFO")
            return
        if not p_addr:
            self._log("⚠️ Vui lòng nhập địa chỉ proxy.", "WARN")
            return
        self._log(f"🔗 Proxy: {p_addr}  Loại: {p_type}", "INFO")
        self._log("ℹ️ Chức năng kiểm tra proxy thực tế sẽ được gọi ở backend.", "INFO")

    # ─────────────────────────────────────────────────────────────────────
    #  NÚT BẮT ĐẦU / DỪNG
    # ─────────────────────────────────────────────────────────────────────
    def _validate(self):
        errors = []
        if not self._get_var("snap_user"):
            errors.append("❌ Thiếu tài khoản Snapchat.")
        if not self._get_var("snap_pass"):
            errors.append("❌ Thiếu mật khẩu Snapchat.")
        if not self._get_var("video_file"):
            errors.append("❌ Chưa chọn file video.")
        if not self._get_var("music_file"):
            errors.append("❌ Chưa chọn file nhạc.")
        if errors:
            for e in errors:
                self._log(e, "WARN")
            messagebox.showwarning("Thiếu thông tin", "\n".join(errors))
            return False
        return True

    def _start_process(self):
        if not self._validate():
            return
        if self.is_running:
            self._log("⚠️ Quy trình đang chạy. Vui lòng đợi.", "WARN")
            return

        self.is_running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._vars["status_label"].configure(text="Trạng thái: ▶ Đang chạy...")

        self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "STEP")
        self._log("▶ BẮT ĐẦU QUY TRÌNH TỰ ĐỘNG HÓA", "STEP")
        self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "STEP")

        self.process_thread = threading.Thread(target=self._run_process, daemon=True)
        self.process_thread.start()

    def _stop_process(self):
        self.is_running = False
        self._log("⏹ Đã nhấn dừng. Quy trình sẽ kết thúc sau bước hiện tại.", "WARN")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._vars["status_label"].configure(text="Trạng thái: Đã dừng")

    def _run_process(self):
        """Chạy quy trình chính qua pipeline backend (Playwright automation)."""
        import asyncio
        try:
            from main import run_pipeline_from_gui
            # Chạy async pipeline từ thread (GUI không block)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(run_pipeline_from_gui(self))
            finally:
                loop.close()

            if result.get("success"):
                self._log("🎉 PIPELINE HOÀN TẤT!", "STEP")
                steps = result.get("steps", {})
                for step_name, step_result in steps.items():
                    status = "✅ Thành công" if step_result.get("success") else "❌ Thất bại"
                    self._log(f"  {step_name}: {status} — {step_result.get('message', '')}")
            else:
                self._log(f"❌ Pipeline thất bại: {result.get('error', 'Unknown error')}", "ERROR")

        except ImportError as e:
            self._log(f"⚠️ Import lỗi: {e}", "ERROR")
            self._log("ℹ️ Chạy demo giả lập quy trình...", "INFO")
            import time
            steps = [
                ("🌐 Kiểm tra kết nối proxy...", 2),
                ("🔐 Đăng nhập Ditto Music...", 3),
                ("🎵 Tải nhạc lên dịch vụ...", 4),
                ("🔐 Đăng nhập Snapchat...", 3),
                ("🎬 Tải video lên Snapchat...", 4),
                ("🎵 Tìm kiếm & thêm nhạc...", 3),
                ("✅ Hoàn tất! Video đã đăng.", 1),
            ]
            for step, sec in steps:
                if not self.is_running:
                    self._log("⏹ Quy trình bị dừng bởi người dùng.", "WARN")
                    break
                self._log(step, "STEP")
                time.sleep(sec)
        except Exception as e:
            self._log(f"❌ Lỗi pipeline: {e}", "ERROR")
        finally:
            self.is_running = False
            self.after(0, lambda: self.btn_start.configure(state="normal"))
            self.after(0, lambda: self.btn_stop.configure(state="disabled"))
            self.after(0, lambda: self._vars["status_label"].configure(
                text="Trạng thái: Sẵn sàng"))

    # ─────────────────────────────────────────────────────────────────────
    #  ĐÓNG ỨNG DỤNG
    # ─────────────────────────────────────────────────────────────────────
    def on_close(self):
        if self.is_running:
            if messagebox.askokcancel("Đang chạy", "Quy trình đang hoạt động. Bạn muốn thoát?"):
                self.is_running = False
                self.destroy()
        else:
            self.destroy()


# ═══════════════════════════════════════════════════════════════════════════
#  CHẠY APP
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
