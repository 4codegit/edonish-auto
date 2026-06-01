#!/usr/bin/env python3
"""
eDonish Auto - Desktop application for automated grade management on edonish.tj
Optimized UI/UX with modern design, hotkeys, and intuitive navigation.
"""
import sys
import os
import json
import threading
import logging
import time
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from tkinter import messagebox, filedialog
import tkinter as tk

from config import (
    APP_NAME, APP_VERSION, MIN_GRADE, MAX_GRADE, DEFAULT_WORKERS,
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING,
    SESSION_FILE,
)
from api_client import EdonishAPI, AuthenticationError
from grade_engine import GradeEngine, GradePlan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser("~"), ".edonish_auto.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("edonish_auto")


# ════════════════════════════════════════════════════════════════════
#  TOOLTIP HELPER
# ════════════════════════════════════════════════════════════════════

class ToolTip:
    """Simple hover tooltip for any widget."""

    def __init__(self, widget, text: str, delay: int = 400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tip_window = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self, event=None):
        if self._tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#2b2b2b", foreground="#ffffff",
            relief="solid", borderwidth=1,
            font=("Segoe UI", 10), padx=6, pady=3,
        )
        label.pack()
        self._tip_window = tw

    def _hide(self, event=None):
        self._cancel()
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


# ════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ════════════════════════════════════════════════════════════════════

class EdonishAutoApp(ctk.CTk):
    """Main application window — optimized UI/UX."""

    # ── Colour palette (works in both light & dark) ───────────────
    CLR_SIDEBAR = ("#f0f0f0", "#1e1e2e")
    CLR_SIDEBAR_HOVER = ("#dcdcdc", "#2d2d44")
    CLR_SIDEBAR_ACTIVE = ("#1a73e8", "#3b82f6")
    CLR_CARD = ("#ffffff", "#252540")
    CLR_STATUS_BAR = ("#e8e8e8", "#181828")
    CLR_TEXT_MUTED = ("#666666", "#999999")

    NAV_ITEMS = [
        ("target", "Авто-оценки"),
        ("journal", "Журнал"),
        ("logs", "Логи"),
    ]

    def __init__(self):
        super().__init__()

        self.api = EdonishAPI()
        self.engine = GradeEngine(self.api)
        self.engine.set_callbacks(
            progress_cb=self._on_progress,
            log_cb=self._on_log,
        )

        # Data storage
        self.journal_options = None
        self.groups_data = []
        self.quarters_data = []
        self.teacher_subjects = []

        # State
        self._logged_in = False
        self._current_plan = None
        self._active_nav = 0  # index into NAV_ITEMS
        self._loading_data = False

        # Configure window
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1200x800")
        self.minsize(960, 640)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Build UI
        self._build_ui()
        self._build_menu_bar()

        # Register global hotkeys
        self._register_hotkeys()

        # Show login
        self._show_login()

        # Load saved session
        self._load_session()

    # ════════════════════════════════════════════════════════════════
    #  MENU BAR
    # ════════════════════════════════════════════════════════════════

    def _build_menu_bar(self):
        menubar = tk.Menu(self)

        # File
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Войти", accelerator="Ctrl+L", command=self._on_login)
        file_menu.add_command(label="Выйти из аккаунта", accelerator="Ctrl+W", command=self._on_logout)
        file_menu.add_separator()
        file_menu.add_command(label="Сохранить отчёт", accelerator="Ctrl+S", command=self._save_report)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", accelerator="Ctrl+Q", command=self._on_quit)
        menubar.add_cascade(label="Файл", menu=file_menu)

        # Actions
        actions_menu = tk.Menu(menubar, tearoff=0)
        actions_menu.add_command(label="Анализировать", accelerator="F5", command=self._on_analyze)
        actions_menu.add_command(label="Запустить", accelerator="F9", command=self._on_start)
        actions_menu.add_command(label="Остановить", accelerator="Esc", command=self._on_stop)
        actions_menu.add_separator()
        actions_menu.add_command(label="Загрузить журнал", accelerator="Ctrl+J", command=lambda: self._set_nav(1))
        menubar.add_cascade(label="Действия", menu=actions_menu)

        # View
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Авто-оценки", accelerator="Ctrl+1", command=lambda: self._set_nav(0))
        view_menu.add_command(label="Журнал", accelerator="Ctrl+2", command=lambda: self._set_nav(1))
        view_menu.add_command(label="Логи", accelerator="Ctrl+3", command=lambda: self._set_nav(2))
        view_menu.add_separator()
        view_menu.add_command(label="Тёмная тема", accelerator="Ctrl+T", command=self._toggle_theme)
        view_menu.add_command(label="Очистить логи", accelerator="Ctrl+Shift+L", command=self._clear_logs)
        menubar.add_cascade(label="Вид", menu=view_menu)

        # Help
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Горячие клавиши", accelerator="F1", command=self._show_shortcuts)
        help_menu.add_command(label="О программе", command=self._show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.config(menu=menubar)

    # ════════════════════════════════════════════════════════════════
    #  HOTKEYS
    # ════════════════════════════════════════════════════════════════

    def _register_hotkeys(self):
        # Global
        self.bind_all("<Control-q>", lambda e: self._on_quit())
        self.bind_all("<Control-w>", lambda e: self._on_logout() if self._logged_in else None)
        self.bind_all("<F1>", lambda e: self._show_shortcuts())

        # Login
        self.bind_all("<Control-l>", lambda e: self._focus_login())
        self.bind_all("<Control-Return>", lambda e: self._smart_enter())

        # Dashboard actions
        self.bind_all("<F5>", lambda e: self._on_analyze() if self._logged_in else None)
        self.bind_all("<F9>", lambda e: self._on_start() if self._logged_in else None)
        self.bind_all("<Escape>", lambda e: self._on_escape())

        # Navigation
        self.bind_all("<Control-1>", lambda e: self._set_nav(0) if self._logged_in else None)
        self.bind_all("<Control-2>", lambda e: self._set_nav(1) if self._logged_in else None)
        self.bind_all("<Control-3>", lambda e: self._set_nav(2) if self._logged_in else None)
        self.bind_all("<Control-j>", lambda e: self._set_nav(1) if self._logged_in else None)

        # Save / Search
        self.bind_all("<Control-s>", lambda e: self._save_report() if self._logged_in else None)
        self.bind_all("<Control-f>", lambda e: self._focus_search() if self._logged_in else None)

        # Text editing
        self.bind_all("<Control-a>", self._on_select_all)
        self.bind_all("<Control-c>", self._on_copy)

        # Theme toggle
        self.bind_all("<Control-t>", lambda e: self._toggle_theme())

        # Clear logs
        self.bind_all("<Control-Shift-L>", lambda e: self._clear_logs() if self._logged_in else None)

    def _on_quit(self):
        if self._logged_in and self.engine.is_running:
            if not messagebox.askyesno("Выход", "Оценки ещё заполняются. Выйти?"):
                return
            self.engine.stop()
        self.quit()

    def _on_escape(self):
        if self._logged_in and self.engine.is_running:
            self._on_stop()

    def _smart_enter(self):
        if not self._logged_in:
            self._on_login()
        elif hasattr(self, "_current_plan") and self._current_plan:
            self._on_start()

    def _focus_login(self):
        if not self._logged_in:
            self.login_id_entry.focus_set()

    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode("Dark")

    def _focus_search(self):
        if self._logged_in:
            self.class_menu.focus_set()

    def _on_select_all(self, event):
        widget = event.widget
        if isinstance(widget, (ctk.CTkTextbox, tk.Text)):
            widget.tag_add("sel", "1.0", "end")
            return "break"

    def _on_copy(self, event):
        widget = event.widget
        if isinstance(widget, (ctk.CTkTextbox, tk.Text)):
            try:
                selected = widget.get("sel.first", "sel.last")
                self.clipboard_clear()
                self.clipboard_append(selected)
                return "break"
            except tk.TclError:
                pass

    def _clear_logs(self):
        try:
            self.logs_text.configure(state="normal")
            self.logs_text.delete("1.0", "end")
            self.logs_text.configure(state="disabled")
            self._log_message("Логи очищены")
        except Exception:
            pass

    def _save_report(self):
        try:
            if not hasattr(self, "_current_plan") or not self._current_plan:
                messagebox.showinfo("Инфо", "Сначала выполните анализ (F5)")
                return

            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[
                    ("Текстовый файл", "*.txt"),
                    ("JSON", "*.json"),
                    ("Все файлы", "*.*"),
                ],
                title="Сохранить отчёт",
                initialfile=f"edonish_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )
            if not filepath:
                return

            plan = self._current_plan
            if filepath.endswith(".json"):
                import json as _json
                report = {
                    "timestamp": datetime.now().isoformat(),
                    "total_tasks": plan.total_tasks,
                    "completed": plan.completed,
                    "failed": plan.failed,
                    "skipped": plan.skipped,
                    "tasks": [
                        {
                            "student": t.student_name,
                            "date": t.date_str,
                            "grade": t.mark,
                            "subject": t.subject_name,
                            "group": t.group_name,
                            "status": t.status,
                        }
                        for t in plan.tasks
                    ],
                }
                with open(filepath, "w", encoding="utf-8") as f:
                    _json.dump(report, f, ensure_ascii=False, indent=2)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"eDonish Auto — Отчёт\n")
                    f.write(f"{'=' * 60}\n")
                    f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Всего задач: {plan.total_tasks}\n")
                    f.write(f"Выполнено: {plan.completed}\n")
                    f.write(f"Ошибки: {plan.failed}\n")
                    f.write(f"Пропущено: {plan.skipped}\n\n")
                    for t in plan.tasks:
                        f.write(
                            f"{t.status:<8} {t.student_name:<25} -> {t.mark} "
                            f"({t.date_str}) [{t.group_name} | {t.subject_name}]\n"
                        )

            self._log_message(f"Отчёт сохранён: {filepath}")
            messagebox.showinfo("Сохранено", f"Отчёт сохранён:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")

    def _show_shortcuts(self):
        shortcuts = """
Горячие клавиши — eDonish Auto
================================

ВХОД:
  Ctrl+L          Фокус на поле логина
  Ctrl+Enter      Войти / Запустить
  Enter           Войти (в поле пароля)

АВТО-ОЦЕНКИ:
  F5              Анализировать
  F9              Запустить заполнение
  Escape          Остановить выполнение
  Ctrl+S          Сохранить отчёт

НАВИГАЦИЯ:
  Ctrl+1          Авто-оценки
  Ctrl+2          Журнал
  Ctrl+3          Логи
  Ctrl+J          Перейти к журналу

РАБОТА С ТЕКСТОМ:
  Ctrl+A          Выделить всё
  Ctrl+C          Копировать
  Ctrl+Shift+L    Очистить логи
  Ctrl+F          Фокус на фильтр класса

ОБЩИЕ:
  Ctrl+Q          Выход из программы
  Ctrl+W          Выйти из аккаунта
  Ctrl+T          Переключить тему
  F1              Эта справка
"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Горячие клавиши")
        dialog.geometry("480x520")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 480) // 2
        y = self.winfo_y() + (self.winfo_height() - 520) // 2
        dialog.geometry(f"+{x}+{y}")

        text = ctk.CTkTextbox(dialog, font=ctk.CTkFont(family="Courier", size=13), wrap="none")
        text.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        text.insert("1.0", shortcuts.strip())
        text.configure(state="disabled")

        ctk.CTkButton(
            dialog, text="Закрыть (Esc)", width=140,
            command=dialog.destroy,
        ).pack(pady=(6, 12))

        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Return>", lambda e: dialog.destroy())

    def _show_about(self):
        messagebox.showinfo(
            "О программе",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"Автоматизация электронного журнала\n"
            f"edonish.tj\n\n"
            f"Горячие клавиши: F1",
        )

    # ════════════════════════════════════════════════════════════════
    #  SESSION PERSISTENCE
    # ════════════════════════════════════════════════════════════════

    def _load_session(self):
        """Load saved login credentials from session file."""
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, "r") as f:
                    data = json.load(f)
                login_id = data.get("login_id", "")
                if login_id:
                    self.login_id_entry.insert(0, login_id)
                if data.get("remember", False):
                    self.remember_var.set(True)
                    pwd = data.get("password", "")
                    if pwd:
                        self.password_entry.insert(0, pwd)
        except Exception:
            pass

    def _save_session(self, login_id: str, password: str, remember: bool):
        """Save login credentials to session file."""
        try:
            data = {
                "login_id": login_id if remember else "",
                "password": password if remember else "",
                "remember": remember,
            }
            with open(SESSION_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════
    #  UI CONSTRUCTION
    # ════════════════════════════════════════════════════════════════

    def _build_ui(self):
        """Build the main UI structure."""
        # Root container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Login Frame
        self.login_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self._build_login_frame()

        # Dashboard Frame (sidebar + content + status bar)
        self.dashboard_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self._build_dashboard_frame()

    # ── Login Screen ───────────────────────────────────────────────

    def _build_login_frame(self):
        """Build a modern, centered login card."""
        frame = self.login_frame

        # Centering wrapper
        center = ctk.CTkFrame(frame, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        # Card
        card = ctk.CTkFrame(center, width=420, corner_radius=16)
        card.pack(padx=20, pady=20)

        # Logo / Title
        ctk.CTkLabel(
            card, text="eDonish Auto",
            font=ctk.CTkFont(size=30, weight="bold"),
        ).pack(pady=(32, 4))

        ctk.CTkLabel(
            card, text="Автоматизация электронного журнала",
            font=ctk.CTkFont(size=13),
            text_color=self.CLR_TEXT_MUTED,
        ).pack(pady=(0, 24))

        # Form fields
        self.login_id_entry = ctk.CTkEntry(
            card, width=320, placeholder_text="Логин (ID)",
            height=44, font=ctk.CTkFont(size=14),
            corner_radius=8,
        )
        self.login_id_entry.pack(pady=(0, 12))

        # Password row with show/hide toggle
        pwd_row = ctk.CTkFrame(card, fg_color="transparent")
        pwd_row.pack(pady=(0, 8))

        self.password_entry = ctk.CTkEntry(
            pwd_row, width=270, placeholder_text="Пароль",
            height=44, show="*", font=ctk.CTkFont(size=14),
            corner_radius=8,
        )
        self.password_entry.pack(side="left", padx=(0, 6))

        self.show_pwd_btn = ctk.CTkButton(
            pwd_row, text="", width=44, height=44,
            corner_radius=8, font=ctk.CTkFont(size=18),
            fg_color="transparent", border_width=1,
            hover_color=self.CLR_SIDEBAR_HOVER,
            command=self._toggle_password_visibility,
        )
        self.show_pwd_btn.pack(side="left")
        self._pwd_visible = False
        self._update_pwd_toggle_icon()

        # Remember me
        self.remember_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            card, text="Запомнить меня",
            variable=self.remember_var,
            font=ctk.CTkFont(size=12),
            checkbox_width=18, checkbox_height=18,
        ).pack(pady=(4, 16))

        # Login button
        self.login_btn = ctk.CTkButton(
            card, text="Войти", width=320, height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=8,
            command=self._on_login,
        )
        self.login_btn.pack(pady=(0, 10))

        # Hint
        ctk.CTkLabel(
            card,
            text="Ctrl+Enter для быстрого входа",
            font=ctk.CTkFont(size=11),
            text_color=self.CLR_TEXT_MUTED,
        ).pack(pady=(0, 24))

        # Status label (for errors)
        self.login_status = ctk.CTkLabel(
            card, text="",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_ERROR, wraplength=300,
        )
        self.login_status.pack(pady=(0, 16))

        # Enter key bindings
        self.password_entry.bind("<Return>", lambda e: self._on_login())
        self.login_id_entry.bind("<Return>", lambda e: self.password_entry.focus_set())

    def _toggle_password_visibility(self):
        self._pwd_visible = not self._pwd_visible
        self.password_entry.configure(show="" if self._pwd_visible else "*")
        self._update_pwd_toggle_icon()

    def _update_pwd_toggle_icon(self):
        # Use simple text icons that work cross-platform
        self.show_pwd_btn.configure(text="Hide" if self._pwd_visible else "Show")

    # ── Dashboard ──────────────────────────────────────────────────

    def _build_dashboard_frame(self):
        """Build the main dashboard with sidebar + content + status bar."""
        frame = self.dashboard_frame

        # ── Sidebar ────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(frame, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # User info card in sidebar
        self.user_card = ctk.CTkFrame(self.sidebar, corner_radius=10)
        self.user_card.pack(fill="x", padx=12, pady=(16, 8))

        self.user_label = ctk.CTkLabel(
            self.user_card, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            wraplength=170,
        )
        self.user_label.pack(pady=(10, 2), padx=8)

        self.school_label = ctk.CTkLabel(
            self.user_card, text="",
            font=ctk.CTkFont(size=11),
            text_color=self.CLR_TEXT_MUTED,
            wraplength=170,
        )
        self.school_label.pack(pady=(0, 10), padx=8)

        # Navigation buttons
        self._nav_buttons = []
        for i, (icon, label) in enumerate(self.NAV_ITEMS):
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {label}",
                font=ctk.CTkFont(size=13),
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color="transparent",
                text_color=self.CLR_TEXT_MUTED,
                hover_color=self.CLR_SIDEBAR_HOVER,
                command=lambda idx=i: self._set_nav(idx),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_buttons.append(btn)
            ToolTip(btn, f"{label} (Ctrl+{i + 1})")

        # Spacer
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Theme toggle
        self.theme_btn = ctk.CTkButton(
            self.sidebar,
            text="  Сменить тему",
            font=ctk.CTkFont(size=12),
            anchor="w",
            height=36,
            corner_radius=8,
            fg_color="transparent",
            text_color=self.CLR_TEXT_MUTED,
            hover_color=self.CLR_SIDEBAR_HOVER,
            command=self._toggle_theme,
        )
        self.theme_btn.pack(fill="x", padx=10, pady=(2, 4))
        ToolTip(self.theme_btn, "Переключить тему (Ctrl+T)")

        # Logout button
        self.logout_btn = ctk.CTkButton(
            self.sidebar,
            text="  Выйти",
            font=ctk.CTkFont(size=12),
            anchor="w",
            height=36,
            corner_radius=8,
            fg_color="transparent",
            text_color=COLOR_ERROR,
            hover_color=self.CLR_SIDEBAR_HOVER,
            command=self._on_logout,
        )
        self.logout_btn.pack(fill="x", padx=10, pady=(2, 16))
        ToolTip(self.logout_btn, "Выйти из аккаунта (Ctrl+W)")

        # ── Main Content Area ──────────────────────────────────────
        content_wrapper = ctk.CTkFrame(frame, fg_color="transparent")
        content_wrapper.pack(side="left", fill="both", expand=True)

        # Scrollable content
        self.content_area = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        self.content_area.pack(fill="both", expand=True, padx=4, pady=(4, 0))

        # Build all page frames (only one visible at a time)
        self._pages = []
        self._build_auto_grade_page()
        self._build_journal_page()
        self._build_logs_page()

        # ── Status Bar ─────────────────────────────────────────────
        self.status_bar = ctk.CTkFrame(content_wrapper, height=28, corner_radius=0)
        self.status_bar.pack(fill="x", side="bottom", pady=(2, 0))
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar, text="Готов",
            font=ctk.CTkFont(size=11),
            text_color=self.CLR_TEXT_MUTED,
        )
        self.status_label.pack(side="left", padx=10)

        self.status_right = ctk.CTkLabel(
            self.status_bar,
            text=f"{APP_NAME} v{APP_VERSION}",
            font=ctk.CTkFont(size=10),
            text_color=self.CLR_TEXT_MUTED,
        )
        self.status_right.pack(side="right", padx=10)

        # Initial nav state
        self._set_nav(0)

    # ── Navigation ─────────────────────────────────────────────────

    def _set_nav(self, index: int):
        """Switch to a navigation page and update sidebar highlighting."""
        self._active_nav = index
        for i, btn in enumerate(self._nav_buttons):
            if i == index:
                btn.configure(
                    fg_color=self.CLR_SIDEBAR_ACTIVE,
                    text_color="#ffffff",
                    hover_color=self.CLR_SIDEBAR_ACTIVE,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=self.CLR_TEXT_MUTED,
                    hover_color=self.CLR_SIDEBAR_HOVER,
                )
        # Show/hide pages
        for i, page in enumerate(self._pages):
            if i == index:
                page.pack(fill="both", expand=True, in_=self.content_area)
            else:
                page.pack_forget()

    # ── Auto Grade Page ────────────────────────────────────────────

    def _build_auto_grade_page(self):
        page = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self._pages.append(page)

        # ── Settings Card ──────────────────────────────────────────
        settings_card = ctk.CTkFrame(page, corner_radius=10)
        settings_card.pack(fill="x", padx=8, pady=(0, 8))

        # Header
        ctk.CTkLabel(
            settings_card, text="Настройки",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 8))

        # Two-column grid for settings
        grid = ctk.CTkFrame(settings_card, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(0, 12))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # Column 1
        col1 = ctk.CTkFrame(grid, fg_color="transparent")
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Class
        ctk.CTkLabel(col1, text="Класс", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.class_var = ctk.StringVar(value="Все классы")
        self.class_menu = ctk.CTkOptionMenu(
            col1, variable=self.class_var,
            values=["Загрузка..."], height=34, corner_radius=6,
        )
        self.class_menu.pack(fill="x", pady=(2, 10))

        # Quarter
        ctk.CTkLabel(col1, text="Четверть", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.quarter_var = ctk.StringVar(value="Все четверти")
        self.quarter_menu = ctk.CTkOptionMenu(
            col1, variable=self.quarter_var,
            values=["Загрузка..."], height=34, corner_radius=6,
        )
        self.quarter_menu.pack(fill="x", pady=(2, 10))

        # Workers
        ctk.CTkLabel(col1, text="Воркеры", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.workers_var = ctk.IntVar(value=DEFAULT_WORKERS)
        ctk.CTkEntry(
            col1, textvariable=self.workers_var, height=34,
            corner_radius=6, width=80,
        ).pack(fill="x", pady=(2, 4))

        # Column 2
        col2 = ctk.CTkFrame(grid, fg_color="transparent")
        col2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # Subject
        ctk.CTkLabel(col2, text="Предмет", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.subject_var = ctk.StringVar(value="Все предметы")
        self.subject_menu = ctk.CTkOptionMenu(
            col2, variable=self.subject_var,
            values=["Загрузка..."], height=34, corner_radius=6,
        )
        self.subject_menu.pack(fill="x", pady=(2, 10))

        # Grade range
        ctk.CTkLabel(col2, text="Диапазон оценок", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        grade_row = ctk.CTkFrame(col2, fg_color="transparent")
        grade_row.pack(fill="x", pady=(2, 10))

        self.min_grade_var = ctk.IntVar(value=MIN_GRADE)
        ctk.CTkEntry(
            grade_row, textvariable=self.min_grade_var, width=60, height=34,
            corner_radius=6, placeholder_text="Мин",
        ).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(grade_row, text="—", font=ctk.CTkFont(size=14)).pack(side="left", padx=4)
        self.max_grade_var = ctk.IntVar(value=MAX_GRADE)
        ctk.CTkEntry(
            grade_row, textvariable=self.max_grade_var, width=60, height=34,
            corner_radius=6, placeholder_text="Макс",
        ).pack(side="left", padx=(4, 0))

        # Options checkboxes
        ctk.CTkLabel(col2, text="Параметры", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(0, 4))
        opts_row = ctk.CTkFrame(col2, fg_color="transparent")
        opts_row.pack(fill="x")

        self.fill_empty_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opts_row, text="Только пустые ячейки",
            variable=self.fill_empty_var,
            font=ctk.CTkFont(size=12),
            checkbox_width=18, checkbox_height=18,
        ).pack(anchor="w", pady=2)

        self.quarter_marks_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opts_row, text="Четвертные оценки",
            variable=self.quarter_marks_var,
            font=ctk.CTkFont(size=12),
            checkbox_width=18, checkbox_height=18,
        ).pack(anchor="w", pady=2)

        # ── Action Buttons Card ────────────────────────────────────
        action_card = ctk.CTkFrame(page, corner_radius=10)
        action_card.pack(fill="x", padx=8, pady=(0, 8))

        btn_row = ctk.CTkFrame(action_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)

        self.analyze_btn = ctk.CTkButton(
            btn_row, text="Анализировать", width=170, height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8, command=self._on_analyze,
        )
        self.analyze_btn.pack(side="left", padx=(0, 8))
        ToolTip(self.analyze_btn, "Анализировать журнал (F5)")

        self.start_btn = ctk.CTkButton(
            btn_row, text="Запустить", width=170, height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8,
            fg_color=COLOR_SUCCESS, hover_color="#2d8e47",
            command=self._on_start, state="disabled",
        )
        self.start_btn.pack(side="left", padx=(0, 8))
        ToolTip(self.start_btn, "Запустить заполнение оценок (F9)")

        self.stop_btn = ctk.CTkButton(
            btn_row, text="Стоп", width=120, height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8,
            fg_color=COLOR_ERROR, hover_color="#c5221f",
            command=self._on_stop, state="disabled",
        )
        self.stop_btn.pack(side="left")
        ToolTip(self.stop_btn, "Остановить выполнение (Esc)")

        # ── Progress Card ──────────────────────────────────────────
        progress_card = ctk.CTkFrame(page, corner_radius=10)
        progress_card.pack(fill="x", padx=8, pady=(0, 8))

        self.progress_label = ctk.CTkLabel(
            progress_card, text="Готов к работе",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.progress_label.pack(anchor="w", padx=16, pady=(12, 4))

        self.progress_bar = ctk.CTkProgressBar(progress_card, height=10, corner_radius=5)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 4))
        self.progress_bar.set(0)

        self.stats_label = ctk.CTkLabel(
            progress_card, text="",
            font=ctk.CTkFont(size=12),
            text_color=self.CLR_TEXT_MUTED,
        )
        self.stats_label.pack(anchor="w", padx=16, pady=(0, 12))

        # ── Results Card ───────────────────────────────────────────
        results_card = ctk.CTkFrame(page, corner_radius=10)
        results_card.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        ctk.CTkLabel(
            results_card, text="Результаты",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(10, 4))

        self.results_text = ctk.CTkTextbox(
            results_card, font=ctk.CTkFont(family="Courier", size=12),
            state="disabled", corner_radius=6,
        )
        self.results_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ── Journal Page ───────────────────────────────────────────────

    def _build_journal_page(self):
        page = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self._pages.append(page)

        # Controls card
        ctrl_card = ctk.CTkFrame(page, corner_radius=10)
        ctrl_card.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(
            ctrl_card, text="Просмотр журнала",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 8))

        sel_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        sel_row.pack(fill="x", padx=16, pady=(0, 12))

        # Class
        ctk.CTkLabel(sel_row, text="Класс", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 4))
        self.journal_class_var = ctk.StringVar()
        self.journal_class_menu = ctk.CTkOptionMenu(
            sel_row, variable=self.journal_class_var,
            values=["Выберите..."], width=140, height=34, corner_radius=6,
            command=self._on_journal_class_change,
        )
        self.journal_class_menu.pack(side="left", padx=(0, 16))

        # Subject
        ctk.CTkLabel(sel_row, text="Предмет", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 4))
        self.journal_subject_var = ctk.StringVar()
        self.journal_subject_menu = ctk.CTkOptionMenu(
            sel_row, variable=self.journal_subject_var,
            values=["Выберите..."], width=180, height=34, corner_radius=6,
        )
        self.journal_subject_menu.pack(side="left", padx=(0, 16))

        # Quarter
        ctk.CTkLabel(sel_row, text="Четверть", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 4))
        self.journal_quarter_var = ctk.StringVar()
        self.journal_quarter_menu = ctk.CTkOptionMenu(
            sel_row, variable=self.journal_quarter_var,
            values=["Выберите..."], width=140, height=34, corner_radius=6,
        )
        self.journal_quarter_menu.pack(side="left", padx=(0, 16))

        load_btn = ctk.CTkButton(
            sel_row, text="Загрузить", width=120, height=34,
            corner_radius=6, command=self._on_load_journal,
        )
        load_btn.pack(side="left")
        ToolTip(load_btn, "Загрузить журнал (Ctrl+J)")

        # Journal display
        journal_card = ctk.CTkFrame(page, corner_radius=10)
        journal_card.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.journal_text = ctk.CTkTextbox(
            journal_card, font=ctk.CTkFont(family="Courier", size=12),
            state="disabled", corner_radius=6,
        )
        self.journal_text.pack(fill="both", expand=True, padx=12, pady=12)

    # ── Logs Page ──────────────────────────────────────────────────

    def _build_logs_page(self):
        page = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self._pages.append(page)

        # Header
        logs_header = ctk.CTkFrame(page, fg_color="transparent")
        logs_header.pack(fill="x", padx=8, pady=(0, 4))

        ctk.CTkLabel(
            logs_header, text="Логи",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            logs_header, text="Очистить", width=100, height=30,
            corner_radius=6, font=ctk.CTkFont(size=12),
            fg_color="transparent", border_width=1,
            command=self._clear_logs,
        ).pack(side="right")
        ToolTip(logs_header.winfo_children()[-1], "Очистить логи (Ctrl+Shift+L)")

        # Logs text
        logs_card = ctk.CTkFrame(page, corner_radius=10)
        logs_card.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.logs_text = ctk.CTkTextbox(
            logs_card, font=ctk.CTkFont(family="Courier", size=12),
            state="disabled", corner_radius=6,
        )
        self.logs_text.pack(fill="both", expand=True, padx=12, pady=12)

    # ════════════════════════════════════════════════════════════════
    #  LOGIN / LOGOUT
    # ════════════════════════════════════════════════════════════════

    def _show_login(self):
        self.dashboard_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True)

    def _show_dashboard(self):
        self.login_frame.pack_forget()
        self.dashboard_frame.pack(fill="both", expand=True)

    def _on_login(self):
        login_id = self.login_id_entry.get().strip()
        password = self.password_entry.get().strip()

        if not login_id or not password:
            self.login_status.configure(text="Введите логин и пароль")
            return

        self.login_btn.configure(state="disabled", text="Вход...")
        self.login_status.configure(text="Подключение...", text_color=self.CLR_TEXT_MUTED)

        # Save session
        self._save_session(login_id, password, self.remember_var.get())

        def do_login():
            try:
                user_info = self.api.login(login_id, password)
                self.after(0, self._on_login_success, user_info)
            except AuthenticationError as e:
                self.after(0, self._on_login_error, str(e))
            except Exception as e:
                self.after(0, self._on_login_error, f"Ошибка: {e}")

        threading.Thread(target=do_login, daemon=True).start()

    def _on_login_success(self, user_info):
        self.login_btn.configure(state="normal", text="Войти")
        self.login_status.configure(text="Вход выполнен!", text_color=COLOR_SUCCESS)

        name = f"{user_info.get('last_name', '')} {user_info.get('first_name', '')}"
        self.user_label.configure(text=name)
        self.school_label.configure(text=f"Школа ID: {self.api.school_id} | {self.api.role}")

        self._logged_in = True
        self._show_dashboard()
        self._load_initial_data()

        self.status_label.configure(text=f"Вход выполнен: {name}")

    def _on_login_error(self, error_msg):
        self.login_btn.configure(state="normal", text="Войти")
        self.login_status.configure(text=error_msg, text_color=COLOR_ERROR)

    def _on_logout(self):
        if self.engine.is_running:
            if not messagebox.askyesno("Выход", "Оценки ещё заполняются. Выйти из аккаунта?"):
                return
            self.engine.stop()
        self._logged_in = False
        self._current_plan = None
        self.api = EdonishAPI()
        self.engine = GradeEngine(self.api)
        self.engine.set_callbacks(
            progress_cb=self._on_progress,
            log_cb=self._on_log,
        )
        self._show_login()
        self.login_status.configure(text="")
        self.status_label.configure(text="Вы вышли из аккаунта")

    # ════════════════════════════════════════════════════════════════
    #  DATA LOADING
    # ════════════════════════════════════════════════════════════════

    def _load_initial_data(self):
        self._log_message("Загрузка данных журнала...")
        self.status_label.configure(text="Загрузка данных...")
        self._loading_data = True

        def load():
            try:
                self.journal_options = self.api.get_journal_options()
                groups = []
                subjects_set = set()

                if self.journal_options and "groups" in self.journal_options:
                    for g in self.journal_options["groups"]:
                        group_name = f"{g.get('number', '')}{g.get('name', '')}"
                        groups.append({
                            "id": g["id"],
                            "name": group_name,
                            "number": g.get("number", ""),
                            "group": g.get("name", ""),
                            "edit": g.get("edit", False),
                            "myClass": g.get("myClass", False),
                        })
                        for s in g.get("subjects", []):
                            subj_key = (s["subjectId"], s["subjectName"])
                            subjects_set.add(subj_key)

                self.groups_data = groups
                self.teacher_subjects = [
                    {"id": sid, "name": sname} for sid, sname in subjects_set
                ]

                self.quarters_data = self.api.get_quarters() or []
                self.after(0, self._update_dropdowns)

            except Exception as e:
                self.after(0, lambda: self._log_message(f"Ошибка загрузки: {e}", "error"))
                self.after(0, lambda: self.status_label.configure(text=f"Ошибка загрузки: {e}"))
            finally:
                self._loading_data = False

        threading.Thread(target=load, daemon=True).start()

    def _update_dropdowns(self):
        class_names = ["Все классы"] + [g["name"] for g in self.groups_data]
        self.class_menu.configure(values=class_names)
        self.journal_class_menu.configure(values=class_names)
        if class_names:
            self.class_var.set(class_names[0])
            self.journal_class_var.set(class_names[1] if len(class_names) > 1 else class_names[0])

        subject_names = ["Все предметы"] + [s["name"] for s in self.teacher_subjects]
        self.subject_menu.configure(values=subject_names)
        self.journal_subject_menu.configure(values=subject_names)
        if subject_names:
            self.subject_var.set(subject_names[0])

        quarter_names = ["Все четверти"] + [q.get("name", "") for q in self.quarters_data]
        self.quarter_menu.configure(values=quarter_names)
        self.journal_quarter_menu.configure(values=quarter_names)
        if quarter_names:
            self.quarter_var.set(quarter_names[0])

        msg = f"Загружено: {len(self.groups_data)} классов, {len(self.teacher_subjects)} предметов, {len(self.quarters_data)} четвертей"
        self._log_message(msg)
        self.status_label.configure(text=msg)

    def _on_journal_class_change(self, value):
        if not self.journal_options or value == "Выберите...":
            return
        subjects = []
        for g in self.journal_options.get("groups", []):
            gname = f"{g.get('number', '')}{g.get('name', '')}"
            if gname == value or value == "Все классы":
                for s in g.get("subjects", []):
                    subjects.append(s["subjectName"])
        subjects = list(set(subjects))
        self.journal_subject_menu.configure(values=subjects)

    # ════════════════════════════════════════════════════════════════
    #  GRADE AUTOMATION
    # ════════════════════════════════════════════════════════════════

    def _get_selected_groups(self) -> list:
        selected = self.class_var.get()
        if selected == "Все классы":
            return self.groups_data
        return [g for g in self.groups_data if g["name"] == selected]

    def _get_selected_subjects(self) -> list:
        selected = self.subject_var.get()
        if selected == "Все предметы":
            return self.teacher_subjects

        subjects = []
        for g in (self.journal_options or {}).get("groups", []):
            for s in g.get("subjects", []):
                if s["subjectName"] == selected or selected == "Все предметы":
                    subjects.append({
                        "subjectId": s["subjectId"],
                        "subjectName": s["subjectName"],
                    })
        seen = set()
        unique = []
        for s in subjects:
            key = s["subjectId"]
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique if unique else self.teacher_subjects

    def _get_selected_quarters(self) -> list:
        selected = self.quarter_var.get()
        if selected == "Все четверти":
            return self.quarters_data
        return [q for q in self.quarters_data if q.get("name") == selected]

    def _on_analyze(self):
        self.analyze_btn.configure(state="disabled", text="Анализ...")
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.configure(state="disabled")
        self.status_label.configure(text="Анализ журнала...")
        self.progress_label.configure(text="Анализ...")
        self.progress_bar.set(0)

        def analyze():
            try:
                groups = self._get_selected_groups()
                subjects = self._get_selected_subjects()
                quarters = self._get_selected_quarters()
                min_grade = self.min_grade_var.get()
                max_grade = self.max_grade_var.get()

                plan = self.engine.build_grade_plan(
                    groups=groups,
                    subjects=subjects,
                    quarters=quarters,
                    min_grade=min_grade,
                    max_grade=max_grade,
                    fill_empty_only=self.fill_empty_var.get(),
                )

                self._current_plan = plan
                self.after(0, self._on_analyze_complete, plan)

            except Exception as e:
                self.after(0, lambda: self._log_message(f"Ошибка анализа: {e}", "error"))
                self.after(0, lambda: self.analyze_btn.configure(state="normal", text="Анализировать"))
                self.after(0, lambda: self.status_label.configure(text=f"Ошибка: {e}"))

        threading.Thread(target=analyze, daemon=True).start()

    def _on_analyze_complete(self, plan: GradePlan):
        self.analyze_btn.configure(state="normal", text="Анализировать")
        self.start_btn.configure(state="normal")

        to_execute = sum(1 for t in plan.tasks if t.status == "pending")
        self.results_text.configure(state="normal")
        self.results_text.insert("end", f"{'=' * 60}\n")
        self.results_text.insert("end", f"  ПЛАН ОЦЕНОК\n")
        self.results_text.insert("end", f"{'=' * 60}\n\n")
        self.results_text.insert("end", f"  Всего задач:      {plan.total_tasks}\n")
        self.results_text.insert("end", f"  Будет выполнено:  {to_execute}\n")
        self.results_text.insert("end", f"  Пропущено:        {plan.skipped}\n\n")

        from collections import defaultdict
        by_group = defaultdict(list)
        for task in plan.tasks:
            if task.status == "pending":
                key = f"{task.group_name} | {task.subject_name}"
                by_group[key].append(task)

        for key, tasks in sorted(by_group.items()):
            self.results_text.insert("end", f"  {key}\n")
            self.results_text.insert("end", f"    Оценок: {len(tasks)}\n")
            for t in tasks[:5]:
                self.results_text.insert("end", f"    - {t.student_name} -> {t.mark} ({t.date_str})\n")
            if len(tasks) > 5:
                self.results_text.insert("end", f"    ... и ещё {len(tasks) - 5}\n")
            self.results_text.insert("end", "\n")

        self.results_text.configure(state="disabled")
        self.progress_label.configure(text=f"Анализ завершён: {to_execute} оценок будет добавлено")
        self.status_label.configure(text=f"Готово: {to_execute} оценок к заполнению")

    def _on_start(self):
        if not hasattr(self, "_current_plan"):
            messagebox.showwarning("Внимание", "Сначала выполните анализ (F5)!")
            return

        to_execute = sum(1 for t in self._current_plan.tasks if t.status == "pending")
        if to_execute == 0:
            messagebox.showinfo("Инфо", "Нет оценок для добавления!")
            return

        if not messagebox.askyesno(
            "Подтверждение",
            f"Добавить {to_execute} оценок?\n\n"
            f"Оценки: {self.min_grade_var.get()}-{self.max_grade_var.get()}\n"
            f"Воркеры: {self.workers_var.get()}",
        ):
            return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.analyze_btn.configure(state="disabled")
        self.status_label.configure(text=f"Заполнение: 0/{to_execute}...")
        self.progress_label.configure(text="Заполнение...")

        num_workers = self.workers_var.get()

        def run():
            try:
                self.engine.execute_plan(
                    plan=self._current_plan,
                    num_workers=num_workers,
                )

                if self.quarter_marks_var.get():
                    self._log_message("Заполнение четвертных оценок...")
                    qplan = self.engine.build_grade_plan_for_quarter_marks(
                        groups=self._get_selected_groups(),
                        subjects=self._get_selected_subjects(),
                        quarters=self._get_selected_quarters(),
                        min_grade=self.min_grade_var.get(),
                        max_grade=self.max_grade_var.get(),
                        fill_empty_only=self.fill_empty_var.get(),
                    )
                    if qplan.total_tasks > 0:
                        self.engine.execute_quarter_marks(qplan)

            except Exception as e:
                self._log_message(f"Критическая ошибка: {e}", "error")
            finally:
                self.after(0, self._on_execution_complete)

        threading.Thread(target=run, daemon=True).start()

    def _on_stop(self):
        self.engine.stop()
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Остановка...")

    def _on_execution_complete(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.analyze_btn.configure(state="normal")

        if self._current_plan:
            plan = self._current_plan
            done = plan.completed + plan.failed
            total = plan.total_tasks - plan.skipped
            self.status_label.configure(
                text=f"Завершено: {done}/{total} | Успешно: {plan.completed} | Ошибки: {plan.failed}"
            )

    # ════════════════════════════════════════════════════════════════
    #  JOURNAL VIEWER
    # ════════════════════════════════════════════════════════════════

    def _on_load_journal(self):
        class_name = self.journal_class_var.get()
        subject_name = self.journal_subject_var.get()
        quarter_name = self.journal_quarter_var.get()

        if class_name in ("Выберите...", ""):
            return

        group_id = None
        subject_id = None
        qprop_id = None

        for g in self.groups_data:
            if g["name"] == class_name:
                group_id = g["id"]
                break

        for s in self.teacher_subjects:
            if s["name"] == subject_name:
                subject_id = s["id"]
                break

        for q in self.quarters_data:
            if q.get("name") == quarter_name:
                qprop_id = q["qpropId"]
                break

        if not all([group_id, subject_id, qprop_id]):
            self.journal_text.configure(state="normal")
            self.journal_text.delete("1.0", "end")
            self.journal_text.insert("end", "Выберите класс, предмет и четверть")
            self.journal_text.configure(state="disabled")
            return

        self.status_label.configure(text="Загрузка журнала...")

        def load():
            try:
                students = self.api.get_journal_students(
                    group_id=group_id,
                    subject_id=subject_id,
                    quarter_property_id=qprop_id,
                )
                dates_data = self.api.get_journal_dates(
                    group_id=group_id,
                    subject_id=subject_id,
                    quarter_property_id=qprop_id,
                )
                self.after(0, self._display_journal, students, dates_data)
                self.after(0, lambda: self.status_label.configure(text="Журнал загружен"))

            except Exception as e:
                self.after(0, lambda: self._log_message(f"Ошибка загрузки журнала: {e}", "error"))
                self.after(0, lambda: self.status_label.configure(text=f"Ошибка: {e}"))

        threading.Thread(target=load, daemon=True).start()

    def _display_journal(self, students, dates_data):
        self.journal_text.configure(state="normal")
        self.journal_text.delete("1.0", "end")

        if not students:
            self.journal_text.insert("end", "Нет данных")
            self.journal_text.configure(state="disabled")
            return

        dates = []
        if dates_data and dates_data[0].get("days"):
            dates = dates_data[0]["days"]

        header = f"{'N':<4} {'Ученик':<30}"
        for d in dates:
            date_str = d.get("assignmentDate", "")[5:]
            header += f" {date_str:>6}"
        header += f"  {'Чтв':>4}  {'Смст':>4}  {'Год':>4}"
        self.journal_text.insert("end", header + "\n")
        self.journal_text.insert("end", "-" * len(header) + "\n")

        for i, s in enumerate(students, 1):
            name = f"{s.get('lastName', '')} {s.get('firstName', '')}"
            row = f"{i:<4} {name:<30}"

            marks_by_date = {}
            for m in s.get("subjectMarks", []):
                marks_by_date[m["assignmentDateId"]] = m.get("shortName", "")

            for d in dates:
                mark = marks_by_date.get(d["assignmentDateId"], "")
                row += f" {mark:>6}"

            qm = s.get("quarterMark", [{}])
            row += f"  {qm[0].get('shortName', ''):>4}" if qm else f"  {'':>4}"

            sm = s.get("semesterMark", [{}])
            row += f"  {sm[0].get('shortName', ''):>4}" if sm else f"  {'':>4}"

            ym = s.get("yearMark", [{}])
            row += f"  {ym[0].get('shortName', ''):>4}" if ym else f"  {'':>4}"

            self.journal_text.insert("end", row + "\n")

        self.journal_text.configure(state="disabled")

    # ════════════════════════════════════════════════════════════════
    #  CALLBACKS
    # ════════════════════════════════════════════════════════════════

    def _on_progress(self, plan: GradePlan):
        total = plan.total_tasks - plan.skipped
        if total > 0:
            done = plan.completed + plan.failed
            pct = done / total
            self.progress_bar.set(pct)
            self.progress_label.configure(
                text=f"Прогресс: {done}/{total} ({pct * 100:.1f}%)"
            )
            self.stats_label.configure(
                text=f"Успешно: {plan.completed}  |  Ошибки: {plan.failed}  |  Пропущено: {plan.skipped}"
            )
            self.status_label.configure(
                text=f"Заполнение: {done}/{total} ({pct * 100:.0f}%)"
            )

    def _on_log(self, message: str, level: str = "info"):
        self.after(0, self._log_message, message, level)

    def _log_message(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "INFO", "warning": "WARN", "error": "ERR!"}.get(level, "INFO")
        line = f"[{timestamp}] [{prefix}] {message}\n"

        try:
            self.logs_text.configure(state="normal")
            self.logs_text.insert("end", line)
            self.logs_text.see("end")
            self.logs_text.configure(state="disabled")
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def main():
    app = EdonishAutoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
