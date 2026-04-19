# Snapchat Automation Platform v2.5 - Premium Dashboard
# Requires: pip install customtkinter Pillow loguru

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from PIL import Image
import os
import sys
import threading
import asyncio
from datetime import datetime
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "SNAPCHAT VIRAL MACHINE"
APP_WIDTH = 1100
APP_HEIGHT = 700

# Colors
BG_SIDEBAR = "#1A1A2E"
BG_MAIN    = "#16213E"
ACCENT     = "#00D1FF"
CRIMSON    = "#E94560"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        
        # Grid config
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # State vars
        self.current_page = None
        self.is_running = False
        
        # Build UI
        self._build_sidebar()
        self._build_main_container()
        
        # Default view
        self._show_page("home")
        
        self.after(500, self._init_log)

    # ─────────────────────────────────────────────────────────────────────
    #  LAYOUT COMPONENTS
    # ─────────────────────────────────────────────────────────────────────
    
    def _build_sidebar(self):
        """Thanh dieu huong ben trai."""
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1) # Spacer

        # Logo/Title
        self.logo_label = ctk.CTkLabel(self.sidebar, text="VIRAL ROBOT", 
                                       font=ctk.CTkFont(size=22, weight="bold"),
                                       text_color=ACCENT)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 40))

        # Nav Buttons
        self.btn_home = self._create_nav_btn("🏠 DASHBOARD", 1, lambda: self._show_page("home"))
        self.btn_viral = self._create_nav_btn("🔥 VIRAL MACHINE", 2, lambda: self._show_page("viral"))
        self.btn_pub   = self._create_nav_btn("📱 UPLOAD MGR", 3, lambda: self._show_page("upload"))
        self.btn_conf  = self._create_nav_btn("⚙️ SETTINGS", 4, lambda: self._show_page("config"))
        self.btn_logs  = self._create_nav_btn("📋 SYSTEM LOGS", 5, lambda: self._show_page("logs"))

    def _create_nav_btn(self, text, row, command):
        btn = ctk.CTkButton(self.sidebar, text=text, corner_radius=10, 
                            height=45, fg_color="transparent", 
                            anchor="w", font=ctk.CTkFont(size=13, weight="normal"),
                            hover_color=BG_MAIN, command=command)
        btn.grid(row=row, column=0, padx=15, pady=8, sticky="ew")
        return btn

    def _build_main_container(self):
        """Vung noi dung chinh ben phai."""
        self.main_view = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_MAIN)
        self.main_view.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_view.grid_columnconfigure(0, weight=1)
        self.main_view.grid_rowconfigure(0, weight=1)

    # ─────────────────────────────────────────────────────────────────────
    #  PAGES (VIEWS)
    # ─────────────────────────────────────────────────────────────────────

    def _show_page(self, name):
        """Chuyen doi giua cac trang giao dien."""
        if self.current_page:
            self.current_page.destroy()
            
        # Reset colors
        for btn in [self.btn_home, self.btn_viral, self.btn_pub, self.btn_conf, self.btn_logs]:
            btn.configure(fg_color="transparent")
        
        if name == "home":
            self.btn_home.configure(fg_color=BG_MAIN)
            self.current_page = self._view_home()
        elif name == "viral":
            self.btn_viral.configure(fg_color=BG_MAIN)
            self.current_page = self._view_viral_machine()
        elif name == "upload":
            self.btn_pub.configure(fg_color=BG_MAIN)
            self.current_page = self._view_upload_mgr()
        elif name == "config":
            self.btn_conf.configure(fg_color=BG_MAIN)
            self.current_page = self._view_settings()
        elif name == "logs":
            self.btn_logs.configure(fg_color=BG_MAIN)
            self.current_page = self._view_logs()

    # ── VIEW: HOME ────────────────────────────────────────────────────────
    def _view_home(self):
        f = ctk.CTkFrame(self.main_view, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        lbl = ctk.CTkLabel(f, text="Welcome back, Commander", 
                           font=ctk.CTkFont(size=28, weight="bold"))
        lbl.pack(anchor="w", pady=(0, 10))
        
        sub = ctk.CTkLabel(f, text="He thong Viral Machine dang o trang thai san sang.", 
                            text_color="gray70", font=ctk.CTkFont(size=14))
        sub.pack(anchor="w", pady=(0, 40))
        
        # Stats Row
        stats_frame = ctk.CTkFrame(f, fg_color="transparent")
        stats_frame.pack(fill="x")
        
        self._create_stat_card(stats_frame, "VIDEO DA SAN", "1,248", ACCENT).grid(row=0, column=0, padx=(0, 20))
        self._create_stat_card(stats_frame, "DA DANG SNAP", "856", "#00FF99").grid(row=0, column=1, padx=20)
        self._create_stat_card(stats_frame, "TY LE THANH CONG", "98.2%", "#FFD100").grid(row=0, column=2, padx=20)
        
        return f

    def _create_stat_card(self, parent, title, value, color):
        card = ctk.CTkFrame(parent, width=220, height=120, corner_radius=15, fg_color=BG_SIDEBAR)
        card.grid_propagate(False)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray60").pack(pady=(20, 0))
        ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=32, weight="bold"), text_color=color).pack(pady=(5, 0))
        return card

    # ── VIEW: VIRAL MACHINE (Combined) ───────────────────────────────────
    def _view_viral_machine(self):
        f = ctk.CTkFrame(self.main_view, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        ctk.CTkLabel(f, text="🔥 VIRAL MACHINE PIPELINE", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 20))
        
        # Step Wrapper
        wrap = ctk.CTkFrame(f, corner_radius=20, fg_color=BG_SIDEBAR, border_width=1, border_color="#303A52")
        wrap.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Settings
        ctk.CTkLabel(wrap, text="NHAP THONG TIN CHIEN DICH", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(20, 10))
        
        entry_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        entry_frame.pack(fill="x", padx=40)
        
        self.kw_entry = ctk.CTkEntry(entry_frame, placeholder_text="Tu khoa (sad edit, cat video...)", 
                                     height=45, width=400, corner_radius=10, border_color=ACCENT)
        self.kw_entry.pack(side="left", padx=(0, 10))
        
        self.src_menu = ctk.CTkOptionMenu(entry_frame, values=["YouTube Shorts", "TikTok", "Facebook Reels"], 
                                          height=45, width=200, corner_radius=10, fg_color="#303A52")
        self.src_menu.pack(side="left")
        
        # Secondary Controls
        ctrl = ctk.CTkFrame(wrap, fg_color="transparent")
        ctrl.pack(fill="x", padx=40, pady=20)
        
        ctk.CTkLabel(ctrl, text="Views tối thiểu:").grid(row=0, column=0, padx=(0, 10))
        self.min_views = ctk.CTkEntry(ctrl, width=100, placeholder_text="1000")
        self.min_views.insert(0, "1000")
        self.min_views.grid(row=0, column=1, padx=(0, 30))
        
        ctk.CTkLabel(ctrl, text="Thanh thoi gian (s):").grid(row=0, column=2, padx=(0, 10))
        self.max_dur = ctk.CTkEntry(ctrl, width=100, placeholder_text="60")
        self.max_dur.insert(0, "60")
        self.max_dur.grid(row=0, column=3)
        
        # Actions
        self.btn_go = ctk.CTkButton(wrap, text="🚀 KICH HOAT ROBOT", 
                                    font=ctk.CTkFont(size=16, weight="bold"),
                                    height=50, width=250, corner_radius=25,
                                    fg_color="#00C896", hover_color="#00A87A",
                                    command=self._run_all_in_one)
        self.btn_go.pack(pady=30)
        
        # Progress Progress
        self.p_bar = ctk.CTkProgressBar(wrap, width=600, height=12, corner_radius=10)
        self.p_bar.set(0)
        self.p_bar.pack(pady=(0, 10))
        self.p_status = ctk.CTkLabel(wrap, text="Waiting for orders...", text_color="gray60")
        self.p_status.pack()
        
        return f

    # ── VIEW: LOGS ────────────────────────────────────────────────────────
    def _view_logs(self):
        f = ctk.CTkFrame(self.main_view, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        ctk.CTkLabel(f, text="📋 SYSTEM CONSOLE", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 10))
        
        self.log_box = ctk.CTkTextbox(f, corner_radius=15, fg_color="#0F0F23", 
                                      text_color="#00FF99", font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True)
        
        return f

    # ── VIEW: SETTINGS ─────────────────────────────────────────────────────
    def _view_settings(self):
        f = ctk.CTkFrame(self.main_view, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        ctk.CTkLabel(f, text="⚙️ SYSTEM CONFIGURATION", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 20))
        
        # Group: Directories
        group = ctk.CTkFrame(f, fg_color=BG_SIDEBAR, corner_radius=15)
        group.pack(fill="x", pady=10)
        ctk.CTkLabel(group, text="📁 PATHS", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=10)
        
        row1 = ctk.CTkFrame(group, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row1, text="FFmpeg Path:", width=120, anchor="w").pack(side="left")
        self.ffmpeg_path = ctk.CTkEntry(row1, width=400)
        self.ffmpeg_path.insert(0, "ffmpeg")
        self.ffmpeg_path.pack(side="left", padx=10)
        
        # Group: API & Auth
        group2 = ctk.CTkFrame(f, fg_color=BG_SIDEBAR, corner_radius=15)
        group2.pack(fill="x", pady=10)
        ctk.CTkLabel(group2, text="🔑 API CREDENTIALS", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=10)
        
        return f

    def _view_upload_mgr(self):
        # Placeholder for brevity
        f = ctk.CTkFrame(self.main_view, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        ctk.CTkLabel(f, text="📱 UPLOAD MANAGER", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 20))
        return f

    # ─────────────────────────────────────────────────────────────────────
    #  LOGIC HANDLERS
    # ─────────────────────────────────────────────────────────────────────

    def _init_log(self):
        self._log("Ready to conquer social media.")

    def _log(self, text):
        if hasattr(self, "log_box"):
            self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
            self.log_box.see("end")
        print(f"[GUI LOG] {text}")

    def _run_all_in_one(self):
        """Kich hoat luong Full Viral Flow."""
        kw = self.kw_entry.get().strip()
        if not kw:
            messagebox.showwarning("Warning", "Vui lòng nhập từ khóa!")
            return
            
        self._log(f"Starting Viral Machine for keyword: {kw}")
        self.btn_go.configure(state="disabled", text="RUNNING...")
        self.p_bar.start()
        
        # Run in thread
        threading.Thread(target=self._viral_flow_bg, args=(kw,), daemon=True).start()

    def _viral_flow_bg(self, keywords):
        try:
            # Day la noi goi cac module cua ban
            self.after(0, lambda: self.p_status.configure(text="🔍 Searching videos..."))
            # Logic: scraper.scrape(...)
            import time
            time.sleep(2)
            
            self.after(0, lambda: self.p_status.configure(text="📥 Downloading top videos..."))
            # Logic: downloader.download(...)
            time.sleep(2)
            
            self.after(0, lambda: self.p_status.configure(text="🎬 AI Processing & Editing..."))
            # Logic: processor.process(...)
            time.sleep(2)
            
            self.after(0, lambda: self._log("🎉 Viral Flow Completed successfully! Files in uploads/processed/"))
            self.after(0, lambda: self.p_status.configure(text="✅ Done! Check processed folder."))
        except Exception as e:
            self.after(0, lambda: self._log(f"❌ Error in flow: {e}"))
        finally:
            self.after(0, self.p_bar.stop)
            self.after(0, lambda: self.btn_go.configure(state="normal", text="🚀 KICH HOAT ROBOT"))

    def on_close(self):
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
