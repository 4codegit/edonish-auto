#!/usr/bin/env python3
"""
eDonish Auto - Desktop application for automated grade management on edonish.tj
"""
import sys
import os
import threading
import logging
import time
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from tkinter import messagebox, filedialog
import tkinter as tk

from config import APP_NAME, APP_VERSION, MIN_GRADE, MAX_GRADE, DEFAULT_WORKERS, COLOR_PRIMARY, COLOR_SUCCESS, COLOR_ERROR
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


class EdonishAutoApp(ctk.CTk):
    """Main application window."""

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

        # Configure window
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1100x750")
        self.minsize(900, 600)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Build UI
        self._build_ui()
        self._build_menu_bar()

        # Register global hotkeys
        self._register_hotkeys()

        # Show login frame
        self._show_login()

    # ── Menu Bar ───────────────────────────────────────────────────

    def _build_menu_bar(self):
        """Build the top menu bar with keyboard shortcuts."""
        menubar = tk.Menu(self)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Войти", accelerator="Ctrl+L", command=self._on_login)
        file_menu.add_command(label="Выйти из аккаунта", accelerator="Ctrl+W", command=self._on_logout)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", accelerator="Ctrl+Q", command=self._on_quit)
        menubar.add_cascade(label="Файл", menu=file_menu)

        # Actions menu
        actions_menu = tk.Menu(menubar, tearoff=0)
        actions_menu.add_command(label="Анализировать", accelerator="F5", command=self._on_analyze)
        actions_menu.add_command(label="Запустить", accelerator="F9", command=self._on_start)
        actions_menu.add_command(label="Остановить", accelerator="Esc", command=self._on_stop)
        actions_menu.add_separator()
        actions_menu.add_command(label="Загрузить журнал", accelerator="Ctrl+J", command=self._on_load_journal)
        menubar.add_cascade(label="Действия", menu=actions_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Авто-оценки", accelerator="Ctrl+1", command=lambda: self._switch_tab(0))
        view_menu.add_command(label="Журнал", accelerator="Ctrl+2", command=lambda: self._switch_tab(1))
        view_menu.add_command(label="Логи", accelerator="Ctrl+3", command=lambda: self._switch_tab(2))
        view_menu.add_separator()
        view_menu.add_command(label="Очистить логи", accelerator="Ctrl+Shift+C", command=self._clear_logs)
        menubar.add_cascade(label="Вид", menu=view_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Горячие клавиши", accelerator="F1", command=self._show_shortcuts)
        help_menu.add_command(label="О программе", command=self._show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.config(menu=menubar)

    # ── Hotkeys ─────────────────────────────────────────────────────

    def _register_hotkeys(self):
        """Register all keyboard shortcuts."""
        # Global shortcuts (work everywhere)
        self.bind_all("<Control-q>", lambda e: self._on_quit())
        self.bind_all("<Control-w>", lambda e: self._on_logout() if self._logged_in else None)
        self.bind_all("<F1>", lambda e: self._show_shortcuts())

        # Login screen shortcuts
        self.bind_all("<Control-l>", lambda e: self._focus_login())
        self.bind_all("<Control-Return>", lambda e: self._smart_enter())

        # Dashboard shortcuts
        self.bind_all("<F5>", lambda e: self._on_analyze() if self._logged_in else None)
        self.bind_all("<F9>", lambda e: self._on_start() if self._logged_in else None)
        self.bind_all("<Escape>", lambda e: self._on_escape())

        # Tab switching
        self.bind_all("<Control-1>", lambda e: self._switch_tab(0) if self._logged_in else None)
        self.bind_all("<Control-2>", lambda e: self._switch_tab(1) if self._logged_in else None)
        self.bind_all("<Control-3>", lambda e: self._switch_tab(2) if self._logged_in else None)

        # Journal / Logs
        self.bind_all("<Control-j>", lambda e: self._switch_tab(1) if self._logged_in else None)
        self.bind_all("<Control-Shift-C>", lambda e: self._clear_logs() if self._logged_in else None)

        # Quick save report
        self.bind_all("<Control-s>", lambda e: self._save_report() if self._logged_in else None)

        # Select all in text widgets
        self.bind_all("<Control-a>", self._on_select_all)

        # Copy from text widgets
        self.bind_all("<Control-c>", self._on_copy)

        # Find/Search
        self.bind_all("<Control-f>", lambda e: self._focus_search() if self._logged_in else None)

    def _on_quit(self):
        """Quit the application."""
        if self._logged_in and self.engine.is_running:
            if not messagebox.askyesno("Выход", "Оценки ещё заполняются. Выйти?"):
                return
            self.engine.stop()
        self.quit()

    def _on_escape(self):
        """Handle Escape key — context-sensitive."""
        if self._logged_in and self.engine.is_running:
            self._on_stop()
        elif self._logged_in:
            # Could close dialogs, etc.
            pass

    def _smart_enter(self):
        """Ctrl+Enter — context-sensitive action."""
        if not self._logged_in:
            self._on_login()
        elif hasattr(self, '_current_plan') and self._current_plan:
            self._on_start()

    def _focus_login(self):
        """Focus on login entry."""
        if not self._logged_in:
            self.login_id_entry.focus_set()

    def _switch_tab(self, index: int):
        """Switch to tab by index."""
        try:
            if hasattr(self, 'tabview') and self._logged_in:
                self.tabview.set(self.tabview._tab_dict[list(self.tabview._tab_dict.keys())[index]])
        except (IndexError, AttributeError):
            pass

    def _clear_logs(self):
        """Clear the logs text widget."""
        try:
            self.logs_text.configure(state="normal")
            self.logs_text.delete("1.0", "end")
            self.logs_text.configure(state="disabled")
            self._log_message("Логи очищены")
        except Exception:
            pass

    def _save_report(self):
        """Save current results/report to file."""
        try:
            if not hasattr(self, '_current_plan') or not self._current_plan:
                messagebox.showinfo("Инфо", "Сначала выполните анализ (F5)")
                return

            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Текстовый файл", "*.txt"), ("JSON", "*.json"), ("Все файлы", "*.*")],
                title="Сохранить отчёт",
                initialfile=f"edonish_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            )
            if not filepath:
                return

            plan = self._current_plan
            if filepath.endswith(".json"):
                import json
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
                    json.dump(report, f, ensure_ascii=False, indent=2)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"eDonish Auto — Отчёт\n")
                    f.write(f"{'='*60}\n")
                    f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Всего задач: {plan.total_tasks}\n")
                    f.write(f"Выполнено: {plan.completed}\n")
                    f.write(f"Ошибки: {plan.failed}\n")
                    f.write(f"Пропущено: {plan.skipped}\n\n")
                    for t in plan.tasks:
                        f.write(f"{t.status:<8} {t.student_name:<25} -> {t.mark} ({t.date_str}) [{t.group_name} | {t.subject_name}]\n")

            self._log_message(f"Отчёт сохранён: {filepath}")
            messagebox.showinfo("Сохранено", f"Отчёт сохранён:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить: {e}")

    def _on_select_all(self, event):
        """Select all text in text widgets."""
        widget = event.widget
        if isinstance(widget, (ctk.CTkTextbox, tk.Text)):
            widget.tag_add("sel", "1.0", "end")
            return "break"

    def _on_copy(self, event):
        """Copy selected text from text widgets."""
        widget = event.widget
        if isinstance(widget, (ctk.CTkTextbox, tk.Text)):
            try:
                selected = widget.get("sel.first", "sel.last")
                self.clipboard_clear()
                self.clipboard_append(selected)
                return "break"
            except tk.TclError:
                pass

    def _focus_search(self):
        """Focus on class dropdown (as search/filter)."""
        if self._logged_in:
            self.class_menu.focus_set()

    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        shortcuts = """
╔══════════════════════════════════════════════╗
║        ГОРЯЧИЕ КЛАВИШИ — eDonish Auto        ║
╚══════════════════════════════════════════════╝

🔑 ВХОД:
  Ctrl+L           Фокус на поле логина
  Ctrl+Enter       Войти / Запустить
  Enter            Войти (в поле пароля)

🎯 АВТО-ОЦЕНКИ:
  F5               Анализировать
  F9               Запустить заполнение
  Escape           Остановить выполнение
  Ctrl+S           Сохранить отчёт

📋 НАВИГАЦИЯ:
  Ctrl+1           Вкладка «Авто-оценки»
  Ctrl+2           Вкладка «Журнал»
  Ctrl+3           Вкладка «Логи»
  Ctrl+J           Перейти к журналу

📝 РАБОТА С ТЕКСТОМ:
  Ctrl+A           Выделить всё
  Ctrl+C           Копировать
  Ctrl+Shift+C     Очистить логи
  Ctrl+F           Фокус на фильтр класса

🏠 ОБЩИЕ:
  Ctrl+Q           Выход из программы
  Ctrl+W           Выйти из аккаунта
  F1               Показать эту справку
"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Горячие клавиши")
        dialog.geometry("480x560")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 480) // 2
        y = self.winfo_y() + (self.winfo_height() - 560) // 2
        dialog.geometry(f"+{x}+{y}")

        text = ctk.CTkTextbox(dialog, font=ctk.CTkFont(family="Courier", size=12), wrap="none")
        text.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        text.insert("1.0", shortcuts)
        text.configure(state="disabled")

        ctk.CTkButton(
            dialog, text="Закрыть", width=120,
            command=dialog.destroy,
        ).pack(pady=(5, 10))

        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Return>", lambda e: dialog.destroy())

    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "О программе",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"Автоматизация электронного журнала\n"
            f"edonish.tj\n\n"
            f"Горячие клавиши: F1"
        )

    # ── UI Build ────────────────────────────────────────────────────

    def _build_ui(self):
        """Build the main UI structure."""
        # Main container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        # Login Frame
        self.login_frame = ctk.CTkFrame(self.container)
        self._build_login_frame()

        # Main Dashboard Frame
        self.dashboard_frame = ctk.CTkFrame(self.container)
        self._build_dashboard_frame()

    def _build_login_frame(self):
        """Build the login screen."""
        frame = self.login_frame

        # Title
        title = ctk.CTkLabel(
            frame, text="📚 eDonish Auto",
            font=ctk.CTkFont(size=32, weight="bold"),
        )
        title.pack(pady=(40, 5))

        subtitle = ctk.CTkLabel(
            frame, text="Автоматизация электронного журнала",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        subtitle.pack(pady=(0, 30))

        # Login form
        form = ctk.CTkFrame(frame, width=400)
        form.pack(pady=10)

        self.login_id_entry = ctk.CTkEntry(
            form, width=300, placeholder_text="Логин (ID)",
            height=45, font=ctk.CTkFont(size=14),
        )
        self.login_id_entry.pack(pady=(20, 10), padx=30)

        self.password_entry = ctk.CTkEntry(
            form, width=300, placeholder_text="Пароль",
            height=45, show="●", font=ctk.CTkFont(size=14),
        )
        self.password_entry.pack(pady=(0, 20), padx=30)

        self.login_btn = ctk.CTkButton(
            form, text="Войти (Ctrl+Enter)", width=300, height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_login,
        )
        self.login_btn.pack(pady=(0, 20), padx=30)

        self.login_status = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.login_status.pack(pady=5)

        # Bind Enter key
        self.password_entry.bind("<Return>", lambda e: self._on_login())
        self.login_id_entry.bind("<Return>", lambda e: self.password_entry.focus_set())

    def _build_dashboard_frame(self):
        """Build the main dashboard."""
        frame = self.dashboard_frame

        # Top bar
        top_bar = ctk.CTkFrame(frame, height=50)
        top_bar.pack(fill="x", pady=(0, 10))
        top_bar.pack_propagate(False)

        self.user_label = ctk.CTkLabel(
            top_bar, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.user_label.pack(side="left", padx=10)

        self.school_label = ctk.CTkLabel(
            top_bar, text="",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.school_label.pack(side="left", padx=10)

        logout_btn = ctk.CTkButton(
            top_bar, text="Выйти (Ctrl+W)", width=120, height=30,
            fg_color="transparent", border_width=1,
            text_color=COLOR_ERROR, hover_color=COLOR_ERROR,
            command=self._on_logout,
        )
        logout_btn.pack(side="right", padx=10)

        # Main content area with tabs
        self.tabview = ctk.CTkTabview(frame)
        self.tabview.pack(fill="both", expand=True)

        # Tab 1: Auto Grade
        tab_auto = self.tabview.add("🎯 Авто-оценки")
        self._build_auto_grade_tab(tab_auto)

        # Tab 2: Journal View
        tab_journal = self.tabview.add("📋 Журнал")
        self._build_journal_tab(tab_journal)

        # Tab 3: Logs
        tab_logs = self.tabview.add("📝 Логи")
        self._build_logs_tab(tab_logs)

    def _build_auto_grade_tab(self, parent):
        """Build the auto grade tab."""
        # Settings section
        settings = ctk.CTkFrame(parent)
        settings.pack(fill="x", pady=(0, 10))

        # Row 1: Class and Subject selection
        row1 = ctk.CTkFrame(settings, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(row1, text="Класс:", width=80).pack(side="left")
        self.class_var = ctk.StringVar(value="Все классы")
        self.class_menu = ctk.CTkOptionMenu(row1, variable=self.class_var, values=["Загрузка..."], width=200)
        self.class_menu.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(row1, text="Предмет:", width=80).pack(side="left")
        self.subject_var = ctk.StringVar(value="Все предметы")
        self.subject_menu = ctk.CTkOptionMenu(row1, variable=self.subject_var, values=["Загрузка..."], width=250)
        self.subject_menu.pack(side="left", padx=(0, 20))

        # Row 2: Quarter and Grade settings
        row2 = ctk.CTkFrame(settings, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(row2, text="Четверть:", width=80).pack(side="left")
        self.quarter_var = ctk.StringVar(value="Все четверти")
        self.quarter_menu = ctk.CTkOptionMenu(row2, variable=self.quarter_var, values=["Загрузка..."], width=200)
        self.quarter_menu.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(row2, text="Мин. оценка:", width=90).pack(side="left")
        self.min_grade_var = ctk.IntVar(value=MIN_GRADE)
        ctk.CTkEntry(row2, textvariable=self.min_grade_var, width=60, height=30).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(row2, text="Макс. оценка:", width=100).pack(side="left")
        self.max_grade_var = ctk.IntVar(value=MAX_GRADE)
        ctk.CTkEntry(row2, textvariable=self.max_grade_var, width=60, height=30).pack(side="left", padx=(0, 10))

        # Row 3: Workers and options
        row3 = ctk.CTkFrame(settings, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(row3, text="Воркеры:", width=80).pack(side="left")
        self.workers_var = ctk.IntVar(value=DEFAULT_WORKERS)
        ctk.CTkEntry(row3, textvariable=self.workers_var, width=60, height=30).pack(side="left", padx=(0, 20))

        self.fill_empty_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            row3, text="Только пустые ячейки",
            variable=self.fill_empty_var,
        ).pack(side="left", padx=(0, 20))

        self.quarter_marks_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            row3, text="Четвертные оценки",
            variable=self.quarter_marks_var,
        ).pack(side="left")

        # Action buttons
        btn_row = ctk.CTkFrame(settings, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(5, 10))

        self.analyze_btn = ctk.CTkButton(
            btn_row, text="🔍 Анализировать (F5)", width=180,
            command=self._on_analyze,
        )
        self.analyze_btn.pack(side="left", padx=(0, 10))

        self.start_btn = ctk.CTkButton(
            btn_row, text="🚀 Запустить (F9)", width=180,
            fg_color=COLOR_SUCCESS, hover_color="#2d8e47",
            command=self._on_start,
            state="disabled",
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            btn_row, text="⏹ Стоп (Esc)", width=150,
            fg_color=COLOR_ERROR, hover_color="#c5221f",
            command=self._on_stop,
            state="disabled",
        )
        self.stop_btn.pack(side="left")

        # Progress section
        progress_frame = ctk.CTkFrame(parent)
        progress_frame.pack(fill="x", pady=(0, 10))

        self.progress_label = ctk.CTkLabel(
            progress_frame, text="Готов к работе",
            font=ctk.CTkFont(size=12),
        )
        self.progress_label.pack(pady=(5, 0), padx=10, anchor="w")

        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=500)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)

        self.stats_label = ctk.CTkLabel(
            progress_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.stats_label.pack(pady=(0, 5), padx=10, anchor="w")

        # Results table
        results_frame = ctk.CTkFrame(parent)
        results_frame.pack(fill="both", expand=True)

        self.results_text = ctk.CTkTextbox(
            results_frame, font=ctk.CTkFont(family="Courier", size=11),
            state="disabled",
        )
        self.results_text.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_journal_tab(self, parent):
        """Build the journal viewer tab."""
        # Controls
        ctrl = ctk.CTkFrame(parent)
        ctrl.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(ctrl, text="Класс:", width=60).pack(side="left", padx=5)
        self.journal_class_var = ctk.StringVar()
        self.journal_class_menu = ctk.CTkOptionMenu(
            ctrl, variable=self.journal_class_var, values=["Выберите..."], width=150,
            command=self._on_journal_class_change,
        )
        self.journal_class_menu.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(ctrl, text="Предмет:", width=70).pack(side="left", padx=5)
        self.journal_subject_var = ctk.StringVar()
        self.journal_subject_menu = ctk.CTkOptionMenu(
            ctrl, variable=self.journal_subject_var, values=["Выберите..."], width=200,
        )
        self.journal_subject_menu.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(ctrl, text="Четверть:", width=70).pack(side="left", padx=5)
        self.journal_quarter_var = ctk.StringVar()
        self.journal_quarter_menu = ctk.CTkOptionMenu(
            ctrl, variable=self.journal_quarter_var, values=["Выберите..."], width=150,
        )
        self.journal_quarter_menu.pack(side="left", padx=(0, 10))

        load_btn = ctk.CTkButton(
            ctrl, text="📂 Загрузить", width=120,
            command=self._on_load_journal,
        )
        load_btn.pack(side="left", padx=10)

        # Journal display
        self.journal_text = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Courier", size=11),
            state="disabled",
        )
        self.journal_text.pack(fill="both", expand=True)

    def _build_logs_tab(self, parent):
        """Build the logs tab."""
        self.logs_text = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Courier", size=11),
            state="disabled",
        )
        self.logs_text.pack(fill="both", expand=True)

        # Clear button
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", pady=5)

        ctk.CTkButton(
            btn_frame, text="🗑 Очистить логи", width=120,
            command=lambda: self.logs_text.configure(state="normal") or self.logs_text.delete("1.0", "end") or self.logs_text.configure(state="disabled"),
        ).pack(side="right", padx=10)

    # ── Login ──────────────────────────────────────────

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
            self.login_status.configure(text="⚠️ Введите логин и пароль", text_color=COLOR_ERROR)
            return

        self.login_btn.configure(state="disabled", text="Вход...")
        self.login_status.configure(text="🔄 Подключение...", text_color="gray")

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
        self.login_status.configure(text="✅ Вход выполнен!", text_color=COLOR_SUCCESS)

        # Update dashboard
        name = f"{user_info.get('last_name', '')} {user_info.get('first_name', '')}"
        self.user_label.configure(text=f"👤 {name}")
        self.school_label.configure(text=f"🏫 Школа ID: {self.api.school_id} | Роль: {self.api.role}")

        self._logged_in = True
        self._show_dashboard()
        self._load_initial_data()

    def _on_login_error(self, error_msg):
        self.login_btn.configure(state="normal", text="Войти")
        self.login_status.configure(text=f"❌ {error_msg}", text_color=COLOR_ERROR)

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

    # ── Data Loading ───────────────────────────────────

    def _load_initial_data(self):
        """Load classes, subjects, and quarters after login."""
        self._log_message("🔄 Загрузка данных журнала...")

        def load():
            try:
                # Get journal options (classes + subjects)
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

                # Get quarters
                self.quarters_data = self.api.get_quarters() or []

                self.after(0, self._update_dropdowns)

            except Exception as e:
                self.after(0, lambda: self._log_message(f"❌ Ошибка загрузки: {e}", "error"))

        threading.Thread(target=load, daemon=True).start()

    def _update_dropdowns(self):
        """Update dropdown menus with loaded data."""
        # Classes
        class_names = ["Все классы"] + [g["name"] for g in self.groups_data]
        self.class_menu.configure(values=class_names)
        self.journal_class_menu.configure(values=class_names)
        if class_names:
            self.class_var.set(class_names[0])
            self.journal_class_var.set(class_names[1] if len(class_names) > 1 else class_names[0])

        # Subjects
        subject_names = ["Все предметы"] + [s["name"] for s in self.teacher_subjects]
        self.subject_menu.configure(values=subject_names)
        self.journal_subject_menu.configure(values=subject_names)
        if subject_names:
            self.subject_var.set(subject_names[0])

        # Quarters
        quarter_names = ["Все четверти"] + [q.get("name", "") for q in self.quarters_data]
        self.quarter_menu.configure(values=quarter_names)
        self.journal_quarter_menu.configure(values=quarter_names)
        if quarter_names:
            self.quarter_var.set(quarter_names[0])

        self._log_message(f"✅ Загружено: {len(self.groups_data)} классов, "
                         f"{len(self.teacher_subjects)} предметов, "
                         f"{len(self.quarters_data)} четвертей")

    def _on_journal_class_change(self, value):
        """When class changes in journal tab, update subjects."""
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

    # ── Grade Automation ───────────────────────────────

    def _get_selected_groups(self) -> list:
        """Get groups based on selection."""
        selected = self.class_var.get()
        if selected == "Все классы":
            return self.groups_data
        return [g for g in self.groups_data if g["name"] == selected]

    def _get_selected_subjects(self) -> list:
        """Get subjects based on selection."""
        selected = self.subject_var.get()
        if selected == "Все предметы":
            return self.teacher_subjects

        # Find subject from journal options
        subjects = []
        for g in self.journal_options.get("groups", []):
            for s in g.get("subjects", []):
                if s["subjectName"] == selected or selected == "Все предметы":
                    subjects.append({
                        "subjectId": s["subjectId"],
                        "subjectName": s["subjectName"],
                    })
        # Deduplicate
        seen = set()
        unique = []
        for s in subjects:
            key = s["subjectId"]
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique if unique else self.teacher_subjects

    def _get_selected_quarters(self) -> list:
        """Get quarters based on selection."""
        selected = self.quarter_var.get()
        if selected == "Все четверти":
            return self.quarters_data
        return [q for q in self.quarters_data if q.get("name") == selected]

    def _on_analyze(self):
        """Analyze the journal and show what would be filled."""
        self.analyze_btn.configure(state="disabled", text="Анализ...")
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.configure(state="disabled")

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
                self.after(0, lambda: self._log_message(f"❌ Ошибка анализа: {e}", "error"))
                self.after(0, lambda: self.analyze_btn.configure(state="normal", text="🔍 Анализировать"))

        threading.Thread(target=analyze, daemon=True).start()

    def _on_analyze_complete(self, plan: GradePlan):
        self.analyze_btn.configure(state="normal", text="🔍 Анализировать (F5)")
        self.start_btn.configure(state="normal")

        # Show results
        to_execute = sum(1 for t in plan.tasks if t.status == "pending")
        self.results_text.configure(state="normal")
        self.results_text.insert("end", f"{'='*60}\n")
        self.results_text.insert("end", f"  ПЛАН ОЦЕНОК\n")
        self.results_text.insert("end", f"{'='*60}\n\n")
        self.results_text.insert("end", f"  Всего задач: {plan.total_tasks}\n")
        self.results_text.insert("end", f"  Будет выполнено: {to_execute}\n")
        self.results_text.insert("end", f"  Пропущено (уже есть): {plan.skipped}\n\n")

        # Group by class/subject
        from collections import defaultdict
        by_group = defaultdict(list)
        for task in plan.tasks:
            if task.status == "pending":
                key = f"{task.group_name} | {task.subject_name}"
                by_group[key].append(task)

        for key, tasks in sorted(by_group.items()):
            self.results_text.insert("end", f"  📚 {key}\n")
            self.results_text.insert("end", f"     Оценок: {len(tasks)}\n")

            # Show sample
            for t in tasks[:5]:
                self.results_text.insert("end", f"     • {t.student_name} -> {t.mark} ({t.date_str})\n")
            if len(tasks) > 5:
                self.results_text.insert("end", f"     ... и ещё {len(tasks)-5}\n")
            self.results_text.insert("end", "\n")

        self.results_text.configure(state="disabled")

        self.progress_label.configure(text=f"Анализ завершён: {to_execute} оценок будет добавлено")

    def _on_start(self):
        """Start the grade creation process."""
        if not hasattr(self, "_current_plan"):
            messagebox.showwarning("Внимание", "Сначала выполните анализ!")
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

        num_workers = self.workers_var.get()

        def run():
            try:
                self.engine.execute_plan(
                    plan=self._current_plan,
                    num_workers=num_workers,
                )

                # Also do quarter marks if enabled
                if self.quarter_marks_var.get():
                    self._log_message("📋 Заполнение четвертных оценок...")
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
                self._log_message(f"❌ Критическая ошибка: {e}", "error")
            finally:
                self.after(0, self._on_execution_complete)

        threading.Thread(target=run, daemon=True).start()

    def _on_stop(self):
        self.engine.stop()
        self.stop_btn.configure(state="disabled")

    def _on_execution_complete(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.analyze_btn.configure(state="normal")

    # ── Journal Viewer ─────────────────────────────────

    def _on_load_journal(self):
        """Load and display journal data."""
        class_name = self.journal_class_var.get()
        subject_name = self.journal_subject_var.get()
        quarter_name = self.journal_quarter_var.get()

        if class_name == "Выберите...":
            return

        # Find group_id
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
            self.journal_text.insert("end", "⚠️ Выберите класс, предмет и четверть")
            self.journal_text.configure(state="disabled")
            return

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

            except Exception as e:
                self.after(0, lambda: self._log_message(f"❌ Ошибка загрузки журнала: {e}", "error"))

        threading.Thread(target=load, daemon=True).start()

    def _display_journal(self, students, dates_data):
        """Display journal data in the text widget."""
        self.journal_text.configure(state="normal")
        self.journal_text.delete("1.0", "end")

        if not students:
            self.journal_text.insert("end", "Нет данных")
            self.journal_text.configure(state="disabled")
            return

        # Get dates
        dates = []
        if dates_data and dates_data[0].get("days"):
            dates = dates_data[0]["days"]

        # Header
        header = f"{'№':<3} {'Ученик':<30}"
        for d in dates:
            date_str = d.get("assignmentDate", "")[5:]  # MM-DD
            header += f" {date_str:>6}"
        header += f"  {'Чтв':>4}  {'Смст':>4}  {'Год':>4}"
        self.journal_text.insert("end", header + "\n")
        self.journal_text.insert("end", "─" * len(header) + "\n")

        # Students
        for i, s in enumerate(students, 1):
            name = f"{s.get('lastName', '')} {s.get('firstName', '')}"
            row = f"{i:<3} {name:<30}"

            # Marks per date
            marks_by_date = {}
            for m in s.get("subjectMarks", []):
                marks_by_date[m["assignmentDateId"]] = m.get("shortName", "")

            for d in dates:
                mark = marks_by_date.get(d["assignmentDateId"], "")
                row += f" {mark:>6}"

            # Quarter mark
            qm = s.get("quarterMark", [{}])
            row += f"  {qm[0].get('shortName', ''):>4}" if qm else f"  {'':>4}"

            # Semester mark
            sm = s.get("semesterMark", [{}])
            row += f"  {sm[0].get('shortName', ''):>4}" if sm else f"  {'':>4}"

            # Year mark
            ym = s.get("yearMark", [{}])
            row += f"  {ym[0].get('shortName', ''):>4}" if ym else f"  {'':>4}"

            self.journal_text.insert("end", row + "\n")

        self.journal_text.configure(state="disabled")

    # ── Callbacks ──────────────────────────────────────

    def _on_progress(self, plan: GradePlan):
        """Handle progress updates from the engine."""
        total = plan.total_tasks - plan.skipped
        if total > 0:
            done = plan.completed + plan.failed
            pct = done / total
            self.progress_bar.set(pct)
            self.progress_label.configure(
                text=f"Прогресс: {done}/{total} ({pct*100:.1f}%)"
            )
            self.stats_label.configure(
                text=f"✅ Успешно: {plan.completed}  |  ❌ Ошибки: {plan.failed}  |  ⏭️ Пропущено: {plan.skipped}"
            )

    def _on_log(self, message: str, level: str = "info"):
        """Handle log messages from the engine."""
        self.after(0, self._log_message, message, level)

    def _log_message(self, message: str, level: str = "info"):
        """Add a message to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(level, "ℹ️")
        line = f"[{timestamp}] {prefix} {message}\n"

        try:
            self.logs_text.configure(state="normal")
            self.logs_text.insert("end", line)
            self.logs_text.see("end")
            self.logs_text.configure(state="disabled")
        except Exception:
            pass


def main():
    app = EdonishAutoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
