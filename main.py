#!/usr/bin/env python3
"""
eDonish Auto — Modern desktop application (Flet/Flutter UI)
Automated grade management for edonish.tj
"""
import sys
import os

# Fix SSL certificate verification in PyInstaller bundles.
# Must be set BEFORE any library (flet, requests, urllib) uses HTTPS.
try:
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
except ImportError:
    pass

# Monkey-patch ssl.create_default_context to load certifi's CA bundle.
# This fixes SSL errors when flet_desktop tries to download the Flutter
# engine via urllib.request (which doesn't always respect SSL_CERT_FILE).
try:
    import ssl as _ssl
    _orig_create_default_context = _ssl.create_default_context

    def _patched_create_default_context(*args, **kwargs):
        ctx = _orig_create_default_context(*args, **kwargs)
        try:
            import certifi as _certifi
            ctx.load_verify_locations(_certifi.where())
        except Exception:
            pass
        return ctx

    _ssl.create_default_context = _patched_create_default_context
except Exception:
    pass

# Fix Flet View path for PyInstaller bundles.
# When running from a PyInstaller/flet pack bundle, the Flutter engine
# is included in _MEIPASS/flet. Set FLET_VIEW_PATH so flet_desktop
# finds it without trying to download at runtime.
if getattr(sys, 'frozen', False):
    _flet_view_dir = os.path.join(sys._MEIPASS, 'flet')
    if os.path.isdir(_flet_view_dir):
        os.environ['FLET_VIEW_PATH'] = _flet_view_dir

import json
import threading
import logging
import time
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from flet import (
    AppBar, Icon, Icons, IconButton, NavigationRail, NavigationRailDestination,
    NavigationRailLabelType, Page, Text, TextField, ElevatedButton,
    OutlinedButton, TextButton, Checkbox, Dropdown, dropdown,
    ProgressRing, ProgressBar, Container, Card, Column, Row,
    Tabs, Tab, ListView, Divider, SnackBar, AlertDialog, FontWeight,
    MainAxisAlignment, CrossAxisAlignment, TextAlign, padding, margin,
    border_radius, Border, BorderSide, BoxShadow, ThemeMode,
    Switch, FilledButton, FloatingActionButton, Badge, Tooltip,
    ButtonStyle, ControlState, VerticalDivider,
    Colors, ScrollMode,
)

from config import (
    APP_NAME, APP_VERSION, MIN_GRADE, MAX_GRADE, DEFAULT_WORKERS,
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING,
    SESSION_FILE,
)
from api_client import EdonishAPI, AuthenticationError
from grade_engine import GradeEngine, GradePlan

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
#  MAIN APPLICATION
# ════════════════════════════════════════════════════════════════════

class EdonishAutoApp:
    """Flet-based eDonish Auto application with modern Material Design UI."""

    def __init__(self, page: Page):
        self.page = page
        self.api = EdonishAPI()
        self.engine = GradeEngine(self.api)
        self.engine.set_callbacks(
            progress_cb=self._on_progress,
            log_cb=self._on_log,
        )

        # Data
        self.journal_options = None
        self.groups_data = []
        self.quarters_data = []
        self.teacher_subjects = []

        # State
        self._logged_in = False
        self._current_plan = None
        self._loading_data = False
        self._logs_lines = []

        # Page config
        self.page.title = f"{APP_NAME} v{APP_VERSION}"
        self.page.window.width = 1280
        self.page.window.height = 820
        self.page.window.min_width = 960
        self.page.window.min_height = 640
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        self.page.padding = 0
        self.page.spacing = 0
        self.page.fonts = {
            "Roboto": "/fonts/Roboto-Regular.ttf",
            "RobotoBold": "/fonts/Roboto-Bold.ttf",
        }
        self.page.theme = ft.Theme(font_family="Roboto")
        self.page.dark_theme = ft.Theme(font_family="Roboto")

        # Show login
        self._build_login_view()

    # ════════════════════════════════════════════════════════════════
    #  LOGIN VIEW
    # ════════════════════════════════════════════════════════════════

    def _build_login_view(self):
        """Build modern centered login card."""
        self.login_id_field = TextField(
            label="Логин (ID)",
            width=380,
            text_size=16,
            height=60,
            autofocus=True,
            border_radius=12,
            prefix_icon=Icons.PERSON,
        )
        self.password_field = TextField(
            label="Пароль",
            width=380,
            text_size=16,
            height=60,
            password=True,
            can_reveal_password=True,
            border_radius=12,
            prefix_icon=Icons.LOCK,
            on_submit=lambda _: self._on_login(),
        )
        self.remember_check = Checkbox(
            label="Запомнить меня",
            value=False,
            label_style=ft.TextStyle(size=14),
        )
        self.login_status_text = Text(
            "",
            size=14,
            color=ft.Colors.RED_400,
            text_align=TextAlign.CENTER,
        )
        self.login_btn = FilledButton(
            text="Войти",
            width=380,
            height=52,
            style=ButtonStyle(
                text_style=ft.TextStyle(size=17, weight=FontWeight.W_600),
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
            on_click=lambda _: self._on_login(),
        )

        card = Card(
            elevation=8,
            surface_tint_color=ft.Colors.BLUE_50,
            content=Container(
                width=460,
                padding=padding.all(40),
                content=Column(
                    horizontal_alignment=CrossAxisAlignment.CENTER,
                    controls=[
                        Icon(Icons.SCHOOL, size=56, color=ft.Colors.BLUE_600),
                        Text("eDonish Auto", size=32, weight=FontWeight.BOLD, color=ft.Colors.BLUE_700),
                        Text("Автоматизация электронного журнала", size=15, color=ft.Colors.GREY_600),
                        Container(height=24),
                        self.login_id_field,
                        Container(height=8),
                        self.password_field,
                        Container(height=4),
                        self.remember_check,
                        Container(height=16),
                        self.login_btn,
                        Container(height=4),
                        Text("Ctrl+Enter для быстрого входа", size=12, color=ft.Colors.GREY_500),
                        Container(height=4),
                        self.login_status_text,
                    ],
                ),
            ),
        )

        self.page.add(
            Container(
                expand=True,
                alignment=ft.alignment.center,
                content=card,
            )
        )

        # Load saved session
        self._load_session()

        # Keyboard shortcut
        self.page.on_keyboard_event = self._on_login_keyboard

    def _on_login_keyboard(self, e):
        if e.key == "Enter" and e.ctrl:
            self._on_login()

    # ════════════════════════════════════════════════════════════════
    #  DASHBOARD VIEW
    # ════════════════════════════════════════════════════════════════

    def _build_dashboard_view(self, user_info):
        """Build main dashboard with navigation rail + content area."""
        name = f"{user_info.get('last_name', '')} {user_info.get('first_name', '')}"
        school_info = f"Школа ID: {self.api.school_id} | {self.api.role}"

        # ── Navigation Rail ─────────────────────────────────────────
        self.nav_rail = NavigationRail(
            selected_index=0,
            label_type=NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=220,
            group_alignment=-0.9,
            destinations=[
                NavigationRailDestination(
                    icon=Icons.ASSIGNMENT_OUTLINED,
                    selected_icon=Icons.ASSIGNMENT,
                    label="Авто-оценки",
                ),
                NavigationRailDestination(
                    icon=Icons.MENU_BOOK_OUTLINED,
                    selected_icon=Icons.MENU_BOOK,
                    label="Журнал",
                ),
                NavigationRailDestination(
                    icon=Icons.TERMINAL_OUTLINED,
                    selected_icon=Icons.TERMINAL,
                    label="Логи",
                ),
            ],
            on_change=self._on_nav_change,
        )

        # ── Build pages ────────────────────────────────────────────
        self._build_auto_grade_page()
        self._build_journal_page()
        self._build_logs_page()

        self.pages = [
            self.auto_grade_page,
            self.journal_page,
            self.logs_page,
        ]

        # ── AppBar ─────────────────────────────────────────────────
        appbar = AppBar(
            leading=Icon(Icons.SCHOOL, color=ft.Colors.BLUE_600, size=28),
            leading_width=40,
            title=Text(f"{APP_NAME} v{APP_VERSION}", size=18, weight=FontWeight.W_600),
            center_title=False,
            bgcolor=ft.Colors.SURFACE,
            actions=[
                Container(
                    content=Row([
                        Icon(Icons.PERSON, size=20, color=ft.Colors.GREY_700),
                        Text(name, size=14, weight=FontWeight.W_500),
                        Text(school_info, size=12, color=ft.Colors.GREY_500),
                    ], spacing=8),
                    padding=padding.only(right=16),
                ),
                IconButton(
                    icon=Icons.DARK_MODE_OUTLINED,
                    tooltip="Сменить тему",
                    on_click=self._toggle_theme,
                ),
                IconButton(
                    icon=Icons.LOGOUT,
                    tooltip="Выйти из аккаунта",
                    on_click=lambda _: self._on_logout(),
                ),
            ],
        )

        # ── Main layout ────────────────────────────────────────────
        self.page.clean()
        self.page.appbar = appbar
        self.page.add(
            Row(
                expand=True,
                controls=[
                    self.nav_rail,
                    VerticalDivider(width=1),
                    Container(
                        expand=True,
                        content=self.pages[0],
                    ),
                ],
            )
        )

        # Status bar at bottom
        self.status_text = Text("Готов", size=13, color=ft.Colors.GREY_600)
        self.page.overlay.append(
            Container(
                content=self.status_text,
                padding=padding.symmetric(horizontal=16, vertical=6),
                bgcolor=ft.Colors.SURFACE_VARIANT,
                border=Border.only(top=BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                left=0, right=0, bottom=0,
            )
        )
        self.page.update()

    def _on_nav_change(self, e):
        index = e.control.selected_index
        # Replace the content area (3rd child of the Row)
        row = self.page.controls[0] if self.page.controls else None
        if row and isinstance(row, Row) and len(row.controls) >= 3:
            row.controls[2] = Container(
                expand=True,
                content=self.pages[index],
            )
            self.page.update()

    def _toggle_theme(self, e=None):
        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.page.theme_mode = ft.ThemeMode.LIGHT
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
        self.page.update()

    # ════════════════════════════════════════════════════════════════
    #  AUTO GRADE PAGE
    # ════════════════════════════════════════════════════════════════

    def _build_auto_grade_page(self):
        """Settings + Actions + Progress + Results."""
        # ── Settings ────────────────────────────────────────────────
        self.class_dropdown = Dropdown(
            label="Класс",
            width=300,
            text_size=15,
            options=[dropdown.Option("Все классы")],
            value="Все классы",
        )
        self.subject_dropdown = Dropdown(
            label="Предмет",
            width=300,
            text_size=15,
            options=[dropdown.Option("Все предметы")],
            value="Все предметы",
        )
        self.quarter_dropdown = Dropdown(
            label="Четверть",
            width=300,
            text_size=15,
            options=[dropdown.Option("Все четверти")],
            value="Все четверти",
        )
        self.min_grade_field = TextField(
            label="Мин. оценка",
            width=120,
            text_size=16,
            value=str(MIN_GRADE),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.max_grade_field = TextField(
            label="Макс. оценка",
            width=120,
            text_size=16,
            value=str(MAX_GRADE),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.workers_field = TextField(
            label="Воркеры",
            width=120,
            text_size=16,
            value=str(DEFAULT_WORKERS),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.fill_empty_check = Checkbox(
            label="Только пустые ячейки",
            value=True,
            label_style=ft.TextStyle(size=15),
        )
        self.quarter_marks_check = Checkbox(
            label="Четвертные оценки",
            value=True,
            label_style=ft.TextStyle(size=15),
        )

        settings_card = Card(
            elevation=2,
            content=Container(
                padding=padding.all(24),
                content=Column(
                    controls=[
                        Row([
                            Icon(Icons.SETTINGS, size=24, color=ft.Colors.BLUE_600),
                            Text("Настройки", size=20, weight=FontWeight.W_600),
                        ], spacing=10),
                        Container(height=16),
                        Row([
                            Column([self.class_dropdown, Container(height=12), self.quarter_dropdown, Container(height=12), self.workers_field]),
                            Container(width=24),
                            Column([self.subject_dropdown, Container(height=12),
                                Row([self.min_grade_field, Text("—", size=20, weight=FontWeight.BOLD), self.max_grade_field], alignment=MainAxisAlignment.START, spacing=8),
                                Container(height=12),
                                Column([self.fill_empty_check, self.quarter_marks_check]),
                            ]),
                        ], alignment=MainAxisAlignment.START),
                    ],
                ),
            ),
        )

        # ── Action buttons ──────────────────────────────────────────
        self.analyze_btn = ElevatedButton(
            text="Анализировать",
            icon=Icons.SEARCH,
            style=ButtonStyle(
                text_style=ft.TextStyle(size=15, weight=FontWeight.W_600),
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=padding.symmetric(horizontal=24, vertical=14),
            ),
            on_click=lambda _: self._on_analyze(),
        )
        self.start_btn = FilledButton(
            text="Запустить",
            icon=Icons.PLAY_ARROW,
            style=ButtonStyle(
                text_style=ft.TextStyle(size=15, weight=FontWeight.W_600),
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=padding.symmetric(horizontal=24, vertical=14),
                bgcolor=ft.Colors.GREEN_600,
            ),
            on_click=lambda _: self._on_start(),
            disabled=True,
        )
        self.stop_btn = OutlinedButton(
            text="Стоп",
            icon=Icons.STOP,
            style=ButtonStyle(
                text_style=ft.TextStyle(size=15, weight=FontWeight.W_600),
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=padding.symmetric(horizontal=24, vertical=14),
                color=ft.Colors.RED_600,
            ),
            on_click=lambda _: self._on_stop(),
            disabled=True,
        )

        action_card = Card(
            elevation=2,
            content=Container(
                padding=padding.all(20),
                content=Row([
                    self.analyze_btn,
                    Container(width=12),
                    self.start_btn,
                    Container(width=12),
                    self.stop_btn,
                ], alignment=MainAxisAlignment.START),
            ),
        )

        # ── Progress ────────────────────────────────────────────────
        self.progress_label = Text("Готов к работе", size=16, weight=FontWeight.W_600)
        self.progress_bar = ProgressBar(width=800, bar_height=8, color=ft.Colors.BLUE_600, bgcolor=ft.Colors.BLUE_100)
        self.stats_label = Text("", size=14, color=ft.Colors.GREY_600)

        progress_card = Card(
            elevation=2,
            content=Container(
                padding=padding.all(24),
                content=Column([
                    self.progress_label,
                    Container(height=8),
                    self.progress_bar,
                    Container(height=4),
                    self.stats_label,
                ]),
            ),
        )

        # ── Results ─────────────────────────────────────────────────
        self.results_text = Text(
            "Результаты анализа появятся здесь",
            size=14,
            font_family="Roboto Mono",
            color=ft.Colors.GREY_600,
        )

        results_card = Card(
            elevation=2,
            expand=True,
            content=Container(
                padding=padding.all(24),
                expand=True,
                content=Column([
                    Row([
                        Icon(Icons.LIST_ALT, size=22, color=ft.Colors.BLUE_600),
                        Text("Результаты", size=18, weight=FontWeight.W_600),
                    ], spacing=8),
                    Container(height=12),
                    Container(
                        expand=True,
                        content=Column(
                            [self.results_text],
                            scroll=ScrollMode.AUTO,
                            expand=True,
                        ),
                    ),
                ], expand=True),
            ),
        )

        self.auto_grade_page = Column(
            scroll=ScrollMode.AUTO,
            expand=True,
            padding=padding.all(20),
            controls=[
                settings_card,
                Container(height=12),
                action_card,
                Container(height=12),
                progress_card,
                Container(height=12),
                results_card,
            ],
        )

    # ════════════════════════════════════════════════════════════════
    #  JOURNAL PAGE
    # ════════════════════════════════════════════════════════════════

    def _build_journal_page(self):
        """Journal viewer page."""
        self.journal_class_dropdown = Dropdown(
            label="Класс",
            width=200,
            text_size=15,
            options=[dropdown.Option("Выберите...")],
        )
        self.journal_subject_dropdown = Dropdown(
            label="Предмет",
            width=250,
            text_size=15,
            options=[dropdown.Option("Выберите...")],
            on_change=self._on_journal_class_change,
        )
        self.journal_quarter_dropdown = Dropdown(
            label="Четверть",
            width=200,
            text_size=15,
            options=[dropdown.Option("Выберите...")],
        )
        self.journal_load_btn = FilledButton(
            text="Загрузить",
            icon=Icons.DOWNLOAD,
            style=ButtonStyle(
                text_style=ft.TextStyle(size=15, weight=FontWeight.W_500),
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
            on_click=lambda _: self._on_load_journal(),
        )

        self.journal_text = Text(
            "Выберите класс, предмет и четверть для просмотра журнала",
            size=14,
            font_family="Roboto Mono",
            color=ft.Colors.GREY_600,
        )

        self.journal_page = Column(
            scroll=ScrollMode.AUTO,
            expand=True,
            padding=padding.all(20),
            controls=[
                Card(
                    elevation=2,
                    content=Container(
                        padding=padding.all(24),
                        content=Column([
                            Row([
                                Icon(Icons.MENU_BOOK, size=24, color=ft.Colors.BLUE_600),
                                Text("Просмотр журнала", size=20, weight=FontWeight.W_600),
                            ], spacing=10),
                            Container(height=16),
                            Row([
                                self.journal_class_dropdown,
                                Container(width=16),
                                self.journal_subject_dropdown,
                                Container(width=16),
                                self.journal_quarter_dropdown,
                                Container(width=16),
                                self.journal_load_btn,
                            ], alignment=MainAxisAlignment.START),
                        ]),
                    ),
                ),
                Container(height=12),
                Card(
                    elevation=2,
                    expand=True,
                    content=Container(
                        padding=padding.all(24),
                        expand=True,
                        content=Column(
                            [self.journal_text],
                            scroll=ScrollMode.AUTO,
                            expand=True,
                        ),
                    ),
                ),
            ],
        )

    # ════════════════════════════════════════════════════════════════
    #  LOGS PAGE
    # ════════════════════════════════════════════════════════════════

    def _build_logs_page(self):
        """Logs viewer page."""
        self.logs_list = Column(
            scroll=ScrollMode.AUTO,
            expand=True,
            spacing=2,
        )

        clear_btn = OutlinedButton(
            text="Очистить",
            icon=Icons.DELETE_OUTLINE,
            style=ButtonStyle(
                text_style=ft.TextStyle(size=14),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=lambda _: self._clear_logs(),
        )

        self.logs_page = Column(
            expand=True,
            padding=padding.all(20),
            controls=[
                Row([
                    Icon(Icons.TERMINAL, size=24, color=ft.Colors.BLUE_600),
                    Text("Логи", size=20, weight=FontWeight.W_600),
                    Container(expand=True),
                    clear_btn,
                ], spacing=10),
                Container(height=12),
                Card(
                    elevation=2,
                    expand=True,
                    content=Container(
                        padding=padding.all(16),
                        expand=True,
                        content=self.logs_list,
                    ),
                ),
            ],
        )

    # ════════════════════════════════════════════════════════════════
    #  SESSION PERSISTENCE
    # ════════════════════════════════════════════════════════════════

    def _load_session(self):
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, "r") as f:
                    data = json.load(f)
                login_id = data.get("login_id", "")
                if login_id:
                    self.login_id_field.value = login_id
                if data.get("remember", False):
                    self.remember_check.value = True
                    pwd = data.get("password", "")
                    if pwd:
                        self.password_field.value = pwd
                self.page.update()
        except Exception:
            pass

    def _save_session(self, login_id: str, password: str, remember: bool):
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
    #  LOGIN / LOGOUT
    # ════════════════════════════════════════════════════════════════

    def _on_login(self):
        login_id = self.login_id_field.value.strip() if self.login_id_field.value else ""
        password = self.password_field.value.strip() if self.password_field.value else ""

        if not login_id or not password:
            self.login_status_text.value = "Введите логин и пароль"
            self.page.update()
            return

        self.login_btn.disabled = True
        self.login_btn.text = "Вход..."
        self.login_status_text.value = "Подключение..."
        self.login_status_text.color = ft.Colors.GREY_600
        self.page.update()

        self._save_session(login_id, password, self.remember_check.value)

        def do_login():
            try:
                user_info = self.api.login(login_id, password)
                self.page.run_thread(lambda: self._on_login_success(user_info))
            except AuthenticationError as e:
                self.page.run_thread(lambda: self._on_login_error(str(e)))
            except Exception as e:
                self.page.run_thread(lambda: self._on_login_error(f"Ошибка: {e}"))

        threading.Thread(target=do_login, daemon=True).start()

    def _on_login_success(self, user_info):
        self._logged_in = True
        self._build_dashboard_view(user_info)
        self._load_initial_data()

    def _on_login_error(self, error_msg):
        self.login_btn.disabled = False
        self.login_btn.text = "Войти"
        self.login_status_text.value = error_msg
        self.login_status_text.color = ft.Colors.RED_400
        self.page.update()

    def _on_logout(self):
        if self.engine.is_running:
            self.engine.stop()
        self._logged_in = False
        self._current_plan = None
        self.api = EdonishAPI()
        self.engine = GradeEngine(self.api)
        self.engine.set_callbacks(
            progress_cb=self._on_progress,
            log_cb=self._on_log,
        )
        self.page.clean()
        self.page.appbar = None
        self._build_login_view()

    # ════════════════════════════════════════════════════════════════
    #  DATA LOADING
    # ════════════════════════════════════════════════════════════════

    def _load_initial_data(self):
        self._log_message("Загрузка данных журнала...")
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
                self._update_dropdowns()

            except Exception as e:
                self._log_message(f"Ошибка загрузки: {e}", "error")
            finally:
                self._loading_data = False

        threading.Thread(target=load, daemon=True).start()

    def _update_dropdowns(self):
        class_options = [dropdown.Option("Все классы")] + [
            dropdown.Option(g["name"]) for g in self.groups_data
        ]
        self.class_dropdown.options = class_options
        self.journal_class_dropdown.options = class_options

        subject_options = [dropdown.Option("Все предметы")] + [
            dropdown.Option(s["name"]) for s in self.teacher_subjects
        ]
        self.subject_dropdown.options = subject_options
        self.journal_subject_dropdown.options = subject_options

        quarter_options = [dropdown.Option("Все четверти")] + [
            dropdown.Option(q.get("name", "")) for q in self.quarters_data
        ]
        self.quarter_dropdown.options = quarter_options
        self.journal_quarter_dropdown.options = quarter_options

        msg = f"Загружено: {len(self.groups_data)} классов, {len(self.teacher_subjects)} предметов"
        self._log_message(msg)
        try:
            self.page.update()
        except Exception:
            pass

    def _on_journal_class_change(self, e):
        if not self.journal_options:
            return
        value = e.control.value
        subjects = []
        for g in self.journal_options.get("groups", []):
            gname = f"{g.get('number', '')}{g.get('name', '')}"
            if gname == value or value == "Все классы":
                for s in g.get("subjects", []):
                    subjects.append(s["subjectName"])
        subjects = list(set(subjects))
        self.journal_subject_dropdown.options = [dropdown.Option(s) for s in subjects]
        self.page.update()

    # ════════════════════════════════════════════════════════════════
    #  GRADE AUTOMATION
    # ════════════════════════════════════════════════════════════════

    def _get_selected_groups(self) -> list:
        selected = self.class_dropdown.value
        if selected == "Все классы":
            return self.groups_data
        return [g for g in self.groups_data if g["name"] == selected]

    def _get_selected_subjects(self) -> list:
        selected = self.subject_dropdown.value
        if selected == "Все предметы":
            return self.teacher_subjects
        subjects = []
        for g in (self.journal_options or {}).get("groups", []):
            for s in g.get("subjects", []):
                if s["subjectName"] == selected or selected == "Все предметы":
                    subjects.append({"subjectId": s["subjectId"], "subjectName": s["subjectName"]})
        seen = set()
        unique = []
        for s in subjects:
            key = s["subjectId"]
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique if unique else self.teacher_subjects

    def _get_selected_quarters(self) -> list:
        selected = self.quarter_dropdown.value
        if selected == "Все четверти":
            return self.quarters_data
        return [q for q in self.quarters_data if q.get("name") == selected]

    def _on_analyze(self):
        self.analyze_btn.disabled = True
        self.analyze_btn.text = "Анализ..."
        self.progress_bar.value = 0
        self.progress_label.value = "Анализ..."
        self.results_text.value = "Анализ журнала..."
        self.page.update()

        def analyze():
            try:
                groups = self._get_selected_groups()
                subjects = self._get_selected_subjects()
                quarters = self._get_selected_quarters()
                min_grade = int(self.min_grade_field.value or MIN_GRADE)
                max_grade = int(self.max_grade_field.value or MAX_GRADE)

                plan = self.engine.build_grade_plan(
                    groups=groups,
                    subjects=subjects,
                    quarters=quarters,
                    min_grade=min_grade,
                    max_grade=max_grade,
                    fill_empty_only=self.fill_empty_check.value,
                )

                self._current_plan = plan
                self._on_analyze_complete(plan)

            except Exception as e:
                self._log_message(f"Ошибка анализа: {e}", "error")
                self.analyze_btn.disabled = False
                self.analyze_btn.text = "Анализировать"
                self.page.update()

        threading.Thread(target=analyze, daemon=True).start()

    def _on_analyze_complete(self, plan: GradePlan):
        self.analyze_btn.disabled = False
        self.analyze_btn.text = "Анализировать"
        self.start_btn.disabled = False

        to_execute = sum(1 for t in plan.tasks if t.status == "pending")

        lines = []
        lines.append(f"{'=' * 60}")
        lines.append(f"  ПЛАН ОЦЕНОК")
        lines.append(f"{'=' * 60}")
        lines.append(f"")
        lines.append(f"  Всего задач:      {plan.total_tasks}")
        lines.append(f"  Будет выполнено:  {to_execute}")
        lines.append(f"  Пропущено:        {plan.skipped}")
        lines.append(f"")

        by_group = defaultdict(list)
        for task in plan.tasks:
            if task.status == "pending":
                key = f"{task.group_name} | {task.subject_name}"
                by_group[key].append(task)

        for key, tasks in sorted(by_group.items()):
            lines.append(f"  {key}")
            lines.append(f"    Оценок: {len(tasks)}")
            for t in tasks[:5]:
                lines.append(f"    - {t.student_name} -> {t.mark} ({t.date_str})")
            if len(tasks) > 5:
                lines.append(f"    ... и ещё {len(tasks) - 5}")
            lines.append("")

        self.results_text.value = "\n".join(lines)
        self.progress_label.value = f"Анализ завершён: {to_execute} оценок будет добавлено"

        try:
            self.page.update()
        except Exception:
            pass

    def _on_start(self):
        if not self._current_plan:
            self._show_snackbar("Сначала выполните анализ (F5)!")
            return

        to_execute = sum(1 for t in self._current_plan.tasks if t.status == "pending")
        if to_execute == 0:
            self._show_snackbar("Нет оценок для добавления!")
            return

        # Confirmation dialog
        self.start_btn.disabled = True
        self.stop_btn.disabled = False
        self.analyze_btn.disabled = True
        self.progress_label.value = "Заполнение..."
        self.page.update()

        num_workers = int(self.workers_field.value or DEFAULT_WORKERS)

        def run():
            try:
                self.engine.execute_plan(
                    plan=self._current_plan,
                    num_workers=num_workers,
                )
                if self.quarter_marks_check.value:
                    self._log_message("Заполнение четвертных оценок...")
                    qplan = self.engine.build_grade_plan_for_quarter_marks(
                        groups=self._get_selected_groups(),
                        subjects=self._get_selected_subjects(),
                        quarters=self._get_selected_quarters(),
                        min_grade=int(self.min_grade_field.value or MIN_GRADE),
                        max_grade=int(self.max_grade_field.value or MAX_GRADE),
                        fill_empty_only=self.fill_empty_check.value,
                    )
                    if qplan.total_tasks > 0:
                        self.engine.execute_quarter_marks(qplan)

            except Exception as e:
                self._log_message(f"Критическая ошибка: {e}", "error")
            finally:
                self._on_execution_complete()

        threading.Thread(target=run, daemon=True).start()

    def _on_stop(self):
        self.engine.stop()
        self.stop_btn.disabled = True
        self._log_message("Остановка...")
        self.page.update()

    def _on_execution_complete(self):
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
        self.analyze_btn.disabled = False
        if self._current_plan:
            plan = self._current_plan
            done = plan.completed + plan.failed
            total = plan.total_tasks - plan.skipped
            self.progress_label.value = f"Завершено: {done}/{total}"
            self.stats_label.value = f"Успешно: {plan.completed}  |  Ошибки: {plan.failed}  |  Пропущено: {plan.skipped}"
        try:
            self.page.update()
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════
    #  JOURNAL VIEWER
    # ════════════════════════════════════════════════════════════════

    def _on_load_journal(self):
        class_name = self.journal_class_dropdown.value
        subject_name = self.journal_subject_dropdown.value
        quarter_name = self.journal_quarter_dropdown.value

        if not class_name or class_name in ("Выберите...", ""):
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
            self.journal_text.value = "Выберите класс, предмет и четверть"
            self.page.update()
            return

        self._log_message("Загрузка журнала...")

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
                self._display_journal(students, dates_data)
            except Exception as e:
                self._log_message(f"Ошибка загрузки журнала: {e}", "error")

        threading.Thread(target=load, daemon=True).start()

    def _display_journal(self, students, dates_data):
        lines = []

        if not students:
            self.journal_text.value = "Нет данных"
            self.page.update()
            return

        dates = []
        if dates_data and dates_data[0].get("days"):
            dates = dates_data[0]["days"]

        header = f"{'N':<4} {'Ученик':<30}"
        for d in dates:
            date_str = d.get("assignmentDate", "")[5:]
            header += f" {date_str:>6}"
        header += f"  {'Чтв':>4}  {'Смст':>4}  {'Год':>4}"
        lines.append(header)
        lines.append("-" * len(header))

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
            lines.append(row)

        self.journal_text.value = "\n".join(lines)
        self._log_message("Журнал загружен")
        try:
            self.page.update()
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════
    #  CALLBACKS
    # ════════════════════════════════════════════════════════════════

    def _on_progress(self, plan: GradePlan):
        total = plan.total_tasks - plan.skipped
        if total > 0:
            done = plan.completed + plan.failed
            pct = done / total
            self.progress_bar.value = pct
            self.progress_label.value = f"Прогресс: {done}/{total} ({pct * 100:.1f}%)"
            self.stats_label.value = f"Успешно: {plan.completed}  |  Ошибки: {plan.failed}  |  Пропущено: {plan.skipped}"
        try:
            self.page.update()
        except Exception:
            pass

    def _on_log(self, message: str, level: str = "info"):
        self._log_message(message, level)

    def _log_message(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "INFO", "warning": "WARN", "error": "ERR!"}.get(level, "INFO")
        color = {"info": ft.Colors.GREY_800, "warning": ft.Colors.ORANGE_700, "error": ft.Colors.RED_700}.get(level, ft.Colors.GREY_800)
        line = f"[{timestamp}] [{prefix}] {message}"

        try:
            self.logs_list.controls.append(
                Text(line, size=13, font_family="Roboto Mono", color=color)
            )
            # Keep max 500 lines
            if len(self.logs_list.controls) > 500:
                self.logs_list.controls = self.logs_list.controls[-500:]
            self.page.update()
        except Exception:
            pass

    def _clear_logs(self):
        self.logs_list.controls.clear()
        self._log_message("Логи очищены")
        self.page.update()

    def _show_snackbar(self, message: str):
        try:
            self.page.overlay.append(
                SnackBar(content=Text(message, size=15))
            )
            self.page.update()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def main(page: Page):
    EdonishAutoApp(page)


if __name__ == "__main__":
    ft.run(target=main)
