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
import math
import random
import threading
import logging
import time
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from flet import (
    AppBar, Icon, Icons, IconButton, NavigationRail, NavigationRailDestination,
    NavigationRailLabelType, Page, Text, TextField,
    ElevatedButton, OutlinedButton, TextButton, Checkbox, Dropdown, dropdown,
    ProgressRing, ProgressBar, Container, Card, Column, Row,
    Tabs, Tab, ListView, Divider, SnackBar, AlertDialog, FontWeight,
    MainAxisAlignment, CrossAxisAlignment, TextAlign,
    border_radius, Border, BorderSide, BoxShadow, ThemeMode,
    Switch, FilledButton, FloatingActionButton, Badge, Tooltip,
    ButtonStyle, VerticalDivider,
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
        self._grade_cells = {}
        self._grade_data = {}
        self._selected_cell = None
        self._grid_rows = 0
        self._grid_cols = 0
        self._journal_loaded = False
        self._current_journal_params = {}

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
        )
        self.login_status_text = Text(
            "",
            size=14,
            color=ft.Colors.RED_400,
            text_align=TextAlign.CENTER,
        )
        self.login_btn = FilledButton(
            content=ft.Text("Войти", size=17, weight=FontWeight.W_600),
            width=380,
            height=52,
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
            ),
            on_click=lambda _: self._on_login(),
        )

        card = Card(
            elevation=8,
            content=Container(
                width=460,
                padding=40,
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
                alignment=ft.Alignment(0, 0),
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

    def _on_dashboard_keyboard(self, e):
        """Handle keyboard shortcuts on the dashboard and journal grid navigation."""
        # Global shortcuts (always active, regardless of cell selection)
        if e.key == "s" and e.ctrl:
            self._on_save_journal()
            return
        elif e.key == "F5":
            self._on_analyze()
            return

        # Arrow key navigation in journal grid
        if self._selected_cell and self._journal_loaded:
            row, col = self._selected_cell
            if e.key == "ArrowRight":
                self._move_to_cell(row, col + 1)
                return
            elif e.key == "ArrowLeft":
                self._move_to_cell(row, col - 1)
                return
            elif e.key == "ArrowDown":
                self._move_to_cell(row + 1, col)
                return
            elif e.key == "ArrowUp":
                self._move_to_cell(row - 1, col)
                return
            elif e.key == "Delete":
                # Delete grade from current cell in journal
                self._delete_cell_grade(row, col)
                return
            elif e.key == "Tab":
                if e.shift:
                    self._move_to_cell(row, col - 1)
                else:
                    self._move_to_cell(row, col + 1)
                return
            elif e.key == "Enter":
                # Enter on a cell — submit and move to next
                cell = self._grade_cells.get((row, col))
                if cell:
                    val = cell.value
                    if val and val.strip() and val.strip().isdigit():
                        grade = int(val.strip())
                        if MIN_GRADE <= grade <= MAX_GRADE:
                            self._set_cell_grade(row, col, grade)
                return

        # Global Delete (when no cell selected)
        if e.key == "Delete" and not self._selected_cell:
            self._on_delete_grades()

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
                    padding=0,
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
                content=Row([
                    self.status_text,
                    Container(expand=True),
                    Text("Ctrl+S: сохранить | Del: удалить | Стрелки: навигация | F5: анализировать", size=11, color=ft.Colors.GREY_400),
                ]),
                padding=ft.controls.padding.Padding(left=12, top=6, right=12, bottom=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border=Border(
                    top=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    right=BorderSide(0, ft.Colors.TRANSPARENT),
                    bottom=BorderSide(0, ft.Colors.TRANSPARENT),
                    left=BorderSide(0, ft.Colors.TRANSPARENT),
                ),
                left=0, right=0, bottom=0,
            )
        )

        # Keyboard shortcuts
        self.page.on_keyboard_event = self._on_dashboard_keyboard
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
            on_select=self._on_class_change,
        )
        self.subject_dropdown = Dropdown(
            label="Предмет",
            width=300,
            text_size=15,
            options=[dropdown.Option("Все предметы")],
            value="Все предметы",
            on_select=self._on_subject_change,
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
        )
        self.quarter_marks_check = Checkbox(
            label="Четвертные оценки",
            value=True,
        )
        self.signature_check = Checkbox(
            label="Добавить подпись",
            value=False,
            on_change=self._on_signature_check_change,
        )
        self.signature_field = TextField(
            label="Текст подписи",
            width=200,
            text_size=15,
            value="Подпись",
            visible=False,
        )

        settings_card = Card(
            elevation=2,
            content=Container(
                padding=24,
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
                                Column([self.fill_empty_check, self.quarter_marks_check, self.signature_check, self.signature_field]),
                            ]),
                        ], alignment=MainAxisAlignment.START),
                    ],
                ),
            ),
        )

        # ── Action buttons ──────────────────────────────────────────
        self.analyze_btn = ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.SEARCH, size=18),
                ft.Text("Анализировать", size=15, weight=FontWeight.W_600),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=14,
            ),
            on_click=lambda _: self._on_analyze(),
        )
        self.start_btn = FilledButton(
            content=ft.Row([
                ft.Icon(Icons.PLAY_ARROW, size=18),
                ft.Text("Запустить", size=15, weight=FontWeight.W_600),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=14,
                bgcolor=ft.Colors.GREEN_600,
            ),
            on_click=lambda _: self._on_start(),
            disabled=True,
        )
        self.stop_btn = OutlinedButton(
            content=ft.Row([
                ft.Icon(Icons.STOP, size=18),
                ft.Text("Стоп", size=15, weight=FontWeight.W_600),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=14,
                color=ft.Colors.RED_600,
            ),
            on_click=lambda _: self._on_stop(),
            disabled=True,
        )
        self.signature_btn = ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.DRAW, size=18),
                ft.Text("Подпись", size=15, weight=FontWeight.W_600),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=14,
                bgcolor=ft.Colors.PURPLE_100,
                color=ft.Colors.PURPLE_700,
            ),
            on_click=lambda _: self._on_sign(),
            disabled=True,
        )
        self.quarter_marks_btn = FilledButton(
            content=ft.Row([
                ft.Icon(Icons.CALCULATE, size=18),
                ft.Text("Вставить Чтв", size=15, weight=FontWeight.W_600),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=14,
                bgcolor=ft.Colors.AMBER_600,
            ),
            on_click=lambda _: self._on_set_quarter_marks(),
            tooltip="Вставить четвертные оценки (ceil от среднего, пропуская без оценок)",
        )
        self.delete_quarter_btn = OutlinedButton(
            content=ft.Row([
                ft.Icon(Icons.REMOVE_CIRCLE_OUTLINE, size=18),
                ft.Text("Удалить Чтв", size=15, weight=FontWeight.W_600),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=14,
                color=ft.Colors.ORANGE_700,
            ),
            on_click=lambda _: self._on_delete_quarter_marks(),
            tooltip="Удалить ТОЛЬКО четвертные оценки",
        )
        self.delete_btn = OutlinedButton(
            content=ft.Row([
                ft.Icon(Icons.DELETE_FOREVER, size=18),
                ft.Text("Удалить все", size=15, weight=FontWeight.W_600),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=14,
                color=ft.Colors.RED_700,
            ),
            on_click=lambda _: self._on_delete_grades(),
            tooltip="Удалить все оценки (Del)",
        )

        action_card = Card(
            elevation=2,
            content=Container(
                padding=20,
                content=Column([
                    Row([
                        self.analyze_btn,
                        Container(width=12),
                        self.start_btn,
                        Container(width=12),
                        self.stop_btn,
                        Container(width=12),
                        self.signature_btn,
                    ], alignment=MainAxisAlignment.START, wrap=True),
                    Container(height=8),
                    Row([
                        self.quarter_marks_btn,
                        Container(width=12),
                        self.delete_quarter_btn,
                        Container(width=12),
                        self.delete_btn,
                    ], alignment=MainAxisAlignment.START, wrap=True),
                ]),
            ),
        )

        # ── Progress ────────────────────────────────────────────────
        self.progress_label = Text("Готов к работе", size=16, weight=FontWeight.W_600)
        self.progress_pct = Text("0%", size=20, weight=FontWeight.BOLD, color=ft.Colors.BLUE_600)
        self.progress_bar = ProgressBar(width=700, bar_height=10, color=ft.Colors.BLUE_600, bgcolor=ft.Colors.BLUE_100)
        self.stats_label = Text("", size=14, color=ft.Colors.GREY_600)

        progress_card = Card(
            elevation=2,
            content=Container(
                padding=24,
                content=Column([
                    Row([
                        self.progress_label,
                        Container(expand=True),
                        self.progress_pct,
                    ]),
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
                padding=24,
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
        self.auto_grade_page.padding = 20

    # ════════════════════════════════════════════════════════════════
    #  JOURNAL PAGE
    # ════════════════════════════════════════════════════════════════

    def _build_journal_page(self):
        """Interactive journal page with editable grade grid, arrow-key navigation, and Delete support."""
        self.journal_class_dropdown = Dropdown(
            label="Класс",
            width=200,
            text_size=15,
            options=[dropdown.Option("Все классы")],
            value="Все классы",
        )
        self.journal_class_dropdown.on_select = self._on_journal_class_change
        self.journal_subject_dropdown = Dropdown(
            label="Предмет",
            width=250,
            text_size=15,
            options=[dropdown.Option("Все предметы")],
            value="Все предметы",
            on_select=lambda e: self._safe_update(),
        )
        self.journal_quarter_dropdown = Dropdown(
            label="Четверть",
            width=200,
            text_size=15,
            options=[dropdown.Option("Все четверти")],
            value="Все четверти",
            on_select=lambda e: self._safe_update(),
        )
        self.journal_load_btn = FilledButton(
            content=ft.Row([
                ft.Icon(Icons.DOWNLOAD, size=18),
                ft.Text("Загрузить", size=15, weight=FontWeight.W_500),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
            on_click=lambda _: self._on_load_journal(),
        )

        self.journal_save_btn = ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.SAVE, size=18),
                ft.Text("Сохранить", size=15, weight=FontWeight.W_600),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=14,
            ),
            on_click=lambda _: self._on_save_journal(),
            tooltip="Ctrl+S",
            disabled=True,
        )

        self.journal_insert_quarter_btn = FilledButton(
            content=ft.Row([
                ft.Icon(Icons.CALCULATE, size=16),
                ft.Text("Вставить Чтв", size=14, weight=FontWeight.W_500),
            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                bgcolor=ft.Colors.AMBER_600,
            ),
            on_click=lambda _: self._on_journal_insert_quarter(),
            tooltip="Вставить четвертные оценки для текущего журнала",
            visible=False,
        )
        self.journal_delete_quarter_btn = OutlinedButton(
            content=ft.Row([
                ft.Icon(Icons.REMOVE_CIRCLE_OUTLINE, size=16),
                ft.Text("Удалить Чтв", size=14),
            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                color=ft.Colors.ORANGE_700,
            ),
            on_click=lambda _: self._on_journal_delete_quarter(),
            tooltip="Удалить ТОЛЬКО четвертные оценки в текущем журнале",
            visible=False,
        )
        self.journal_clear_btn = OutlinedButton(
            content=ft.Row([
                ft.Icon(Icons.CLEANING_SERVICES, size=16),
                ft.Text("Очистить все", size=14),
            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                color=ft.Colors.RED_700,
            ),
            on_click=lambda _: self._on_clear_all_grades(),
            tooltip="Удалить все оценки в журнале",
            visible=False,
        )
        self.journal_topic_field = TextField(
            label="Тема урока",
            width=250,
            text_size=14,
            height=45,
            visible=False,
            hint_text="Введите тему урока",
        )
        self.journal_fill_topics_btn = ElevatedButton(
            content=ft.Row([
                ft.Icon(Icons.EDIT_NOTE, size=16),
                ft.Text("Заполнить темы", size=14, weight=FontWeight.W_500),
            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                bgcolor=ft.Colors.TEAL_100,
                color=ft.Colors.TEAL_700,
            ),
            on_click=lambda _: self._on_fill_topics(),
            tooltip="Заполнить тему урока для всех пустых дат",
            visible=False,
        )

        self.journal_student_count = Text("", size=13, color=ft.Colors.GREY_500)

        # Placeholder text when no journal loaded
        self.journal_placeholder = Text(
            "Выберите класс, предмет и четверть для просмотра журнала\n\n"
            "Стрелки — навигация по ячейкам | Ввод цифры — поставить оценку\n"
            "Delete — удалить оценку из ячейки",
            size=14,
            color=ft.Colors.GREY_600,
            text_align=TextAlign.CENTER,
        )

        # The grid container — will be populated by _display_journal_grid
        self.journal_grid_container = Container(
            expand=True,
            content=Column(
                [self.journal_placeholder],
                scroll=ScrollMode.AUTO,
                expand=True,
                horizontal_alignment=CrossAxisAlignment.CENTER,
            ),
        )

        self.journal_page = Column(
            scroll=ScrollMode.AUTO,
            expand=True,
            controls=[
                Card(
                    elevation=2,
                    content=Container(
                        padding=24,
                        content=Column([
                            Row([
                                Icon(Icons.MENU_BOOK, size=24, color=ft.Colors.BLUE_600),
                                Text("Просмотр журнала", size=20, weight=FontWeight.W_600),
                                Container(expand=True),
                                self.journal_student_count,
                            ], spacing=10),
                            Container(height=16),
                            Row([
                                self.journal_class_dropdown,
                                Container(width=12),
                                self.journal_subject_dropdown,
                                Container(width=12),
                                self.journal_quarter_dropdown,
                            ], alignment=MainAxisAlignment.START, wrap=True),
                            Container(height=12),
                            Row([
                                self.journal_load_btn,
                                Container(width=12),
                                self.journal_save_btn,
                                Container(width=12),
                                self.journal_insert_quarter_btn,
                                Container(width=8),
                                self.journal_delete_quarter_btn,
                                Container(width=8),
                                self.journal_clear_btn,
                            ], alignment=MainAxisAlignment.START, wrap=True),
                            Container(height=8),
                            Row([
                                self.journal_topic_field,
                                Container(width=8),
                                self.journal_fill_topics_btn,
                            ], alignment=MainAxisAlignment.START, wrap=True),
                        ]),
                    ),
                ),
                Container(height=12),
                Card(
                    elevation=2,
                    expand=True,
                    content=Container(
                        padding=16,
                        expand=True,
                        content=self.journal_grid_container,
                    ),
                ),
            ],
        )
        self.journal_page.padding = 20

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
            content=ft.Row([
                ft.Icon(Icons.DELETE_OUTLINE, size=16),
                ft.Text("Очистить", size=14),
            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            style=ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=lambda _: self._clear_logs(),
        )

        self.logs_page = Column(
            expand=True,
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
                        padding=16,
                        expand=True,
                        content=self.logs_list,
                    ),
                ),
            ],
        )
        self.logs_page.padding = 20

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
        self.login_btn.content.value = "Вход..."
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
        self.login_btn.content.value = "Войти"
        self.login_status_text.value = error_msg
        self.login_status_text.color = ft.Colors.RED_400
        self.page.update()

    def _on_logout(self):
        if self.engine.is_running:
            self.engine.stop()
        self._logged_in = False
        self._current_plan = None
        self._grade_cells = {}
        self._grade_data = {}
        self._selected_cell = None
        self._grid_rows = 0
        self._grid_cols = 0
        self._journal_loaded = False
        self._current_journal_params = {}
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
                    {"subjectId": sid, "subjectName": sname} for sid, sname in subjects_set
                ]

                # Build quarters from journal_options (group-specific, not school-level)
                # school-level get_quarters() returns wrong qpropId for specific groups
                quarters_by_name = {}
                for g in self.journal_options.get("groups", []):
                    for q in g.get("quarters", []):
                        qname = q.get("name", "")
                        if qname and qname not in quarters_by_name:
                            quarters_by_name[qname] = {
                                "qpropId": q["id"],
                                "name": qname,
                                "startDate": q.get("startDate", ""),
                                "endDate": q.get("endDate", ""),
                                "currentQuarter": q.get("currentQuarter", False),
                            }
                self.quarters_data = list(quarters_by_name.values())

                # Build subjects with curriculumPropertyId from journal_options
                subjects_with_curriculum = {}
                for g in self.journal_options.get("groups", []):
                    for s in g.get("subjects", []):
                        sid = s["subjectId"]
                        if sid not in subjects_with_curriculum:
                            subjects_with_curriculum[sid] = {
                                "subjectId": sid,
                                "subjectName": s["subjectName"],
                                "curriculumPropertyId": s.get("curriculumPropertyId", 0),
                            }
                self.teacher_subjects = list(subjects_with_curriculum.values())

                # Enrich groups_data with group-specific quarters and subjects
                # (each group has its own quarter IDs and subject list)
                for gd in self.groups_data:
                    for g in self.journal_options.get("groups", []):
                        gname = f"{g.get('number', '')}{g.get('name', '')}"
                        if gname == gd["name"]:
                            gd["quarters"] = [
                                {
                                    "qpropId": q["id"],
                                    "name": q.get("name", ""),
                                    "startDate": q.get("startDate", ""),
                                    "endDate": q.get("endDate", ""),
                                    "currentQuarter": q.get("currentQuarter", False),
                                }
                                for q in g.get("quarters", [])
                            ]
                            gd["subjects"] = [
                                {
                                    "subjectId": s["subjectId"],
                                    "subjectName": s["subjectName"],
                                    "curriculumPropertyId": s.get("curriculumPropertyId", 0),
                                }
                                for s in g.get("subjects", [])
                            ]
                            break

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
            dropdown.Option(s["subjectName"]) for s in sorted(self.teacher_subjects, key=lambda x: x["subjectName"])
        ]
        self.subject_dropdown.options = subject_options
        self.journal_subject_dropdown.options = subject_options

        quarter_options = [dropdown.Option("Все четверти")] + [
            dropdown.Option(q.get("name", "")) for q in self.quarters_data
        ]
        self.quarter_dropdown.options = quarter_options
        self.journal_quarter_dropdown.options = quarter_options

        # Auto-detect current quarter based on date
        current_quarter_name = self._detect_current_quarter()
        if current_quarter_name:
            self.quarter_dropdown.value = current_quarter_name
            self.journal_quarter_dropdown.value = current_quarter_name
            self._log_message(f"Автоопределение: текущая четверть — {current_quarter_name}")

        msg = f"Загружено: {len(self.groups_data)} классов, {len(self.teacher_subjects)} предметов"
        self._log_message(msg)
        try:
            self.page.run_thread(self._safe_update)
        except Exception:
            pass

    def _on_class_change(self, e):
        """Filter subjects when class changes on the auto-grade page."""
        if not self.journal_options:
            return
        value = e.control.value
        subjects = []
        for g in self.journal_options.get("groups", []):
            gname = f"{g.get('number', '')}{g.get('name', '')}"
            if gname == value or value == "Все классы":
                for s in g.get("subjects", []):
                    subjects.append(s["subjectName"])
        subjects = sorted(list(set(subjects)))
        subject_options = [dropdown.Option("Все предметы")] + [dropdown.Option(s) for s in subjects]
        self.subject_dropdown.options = subject_options
        self.subject_dropdown.value = "Все предметы"
        try:
            self.page.update()
        except Exception:
            pass

    def _on_subject_change(self, e):
        """Handle subject selection change on the auto-grade page."""
        # Value is already updated by the dropdown itself
        # This handler exists to ensure the dropdown responds properly
        try:
            self.page.update()
        except Exception:
            pass

    def _on_journal_class_change(self, e):
        """Filter subjects when class changes in the journal page."""
        if not self.journal_options:
            return
        value = e.control.value
        subjects = []
        for g in self.journal_options.get("groups", []):
            gname = f"{g.get('number', '')}{g.get('name', '')}"
            if gname == value or value == "Все классы":
                for s in g.get("subjects", []):
                    subjects.append(s["subjectName"])
        subjects = sorted(list(set(subjects)))
        subject_options = [dropdown.Option("Все предметы")] + [dropdown.Option(s) for s in subjects]
        self.journal_subject_dropdown.options = subject_options
        self.journal_subject_dropdown.value = "Все предметы"
        try:
            self.page.update()
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════
    #  QUARTER AUTO-DETECTION
    # ════════════════════════════════════════════════════════════════

    def _detect_current_quarter(self) -> str:
        """Auto-detect the current quarter based on today's date."""
        today = datetime.now()
        for q in self.quarters_data:
            start = q.get("startDate", "")
            end = q.get("endDate", "")
            name = q.get("name", "")
            if not start or not end:
                continue
            try:
                start_dt = datetime.strptime(start[:10], "%Y-%m-%d")
                end_dt = datetime.strptime(end[:10], "%Y-%m-%d")
                if start_dt <= today <= end_dt:
                    return name
            except (ValueError, TypeError):
                continue
        # Fallback: determine quarter by month
        month = today.month
        if month in (9, 10, 11):
            q_num = 1
        elif month in (12, 1, 2):
            q_num = 2
        elif month in (3, 4, 5):
            q_num = 3
        else:
            q_num = 4
        for q in self.quarters_data:
            name = q.get("name", "")
            if str(q_num) in name:
                return name
        # Last resort: return first quarter name
        if self.quarters_data:
            return self.quarters_data[0].get("name", "")
        return ""

    # ════════════════════════════════════════════════════════════════
    #  SIGNATURE FEATURE
    # ════════════════════════════════════════════════════════════════

    def _on_signature_check_change(self, e=None):
        """Toggle signature field visibility."""
        self.signature_field.visible = self.signature_check.value
        try:
            self.page.update()
        except Exception:
            pass

    def _on_sign(self):
        """Execute signature for all selected students."""
        if not self.signature_check.value:
            self._show_snackbar("Включите чекбокс 'Добавить подпись'!")
            return

        signature_text = self.signature_field.value or "Подпись"
        groups = self._get_selected_groups()
        subjects = self._get_selected_subjects()
        quarters = self._get_selected_quarters()

        if not groups or not subjects or not quarters:
            self._show_snackbar("Выберите класс, предмет и четверть!")
            return

        self.signature_btn.disabled = True
        self.start_btn.disabled = True
        self.analyze_btn.disabled = True
        self.stop_btn.disabled = False
        self.progress_label.value = "Добавление подписей..."
        self.page.update()

        def run():
            try:
                self.engine.execute_signatures(
                    groups=groups,
                    subjects=subjects,
                    quarters=quarters,
                    signature_text=signature_text,
                    fill_empty_only=self.fill_empty_check.value,
                )
            except Exception as e:
                self._log_message(f"Ошибка подписей: {e}", "error")
            finally:
                self._on_sign_complete()

        threading.Thread(target=run, daemon=True).start()

    def _on_sign_complete(self):
        self.signature_btn.disabled = False
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
        self.analyze_btn.disabled = False
        self.progress_label.value = "Подписи добавлены"
        self.page.run_thread(self._safe_update)

    # ════════════════════════════════════════════════════════════════
    #  QUARTER MARKS
    # ════════════════════════════════════════════════════════════════

    def _on_set_quarter_marks(self):
        """Set quarter marks for all selected groups/subjects/quarters (ceil of average)."""
        groups = self._get_selected_groups()
        subjects = self._get_selected_subjects()
        quarters = self._get_selected_quarters()

        if not groups or not subjects or not quarters:
            self._show_snackbar("Выберите класс, предмет и четверть!")
            return

        # Confirmation dialog
        self._ins_qt_dialog = AlertDialog(
            modal=True,
            title=Text("Вставка четвертных оценок", weight=FontWeight.W_700),
            content=Text(
                "Вставить четвертные оценки\n"
                "для выбранных класса, предмета и четверти?\n\n"
                "Расчёт: ceil(среднее арифметическое)\n"
                "Ученики без оценок будут ПРОПУЩЕНЫ.",
                size=15,
            ),
            actions=[
                TextButton(
                    content=Text("Отмена", size=15),
                    on_click=lambda _: self._close_ins_qt_dialog(),
                ),
                FilledButton(
                    content=ft.Text("Вставить четвертные", size=15, weight=FontWeight.W_600),
                    style=ButtonStyle(bgcolor=ft.Colors.AMBER_600),
                    on_click=lambda _: self._confirm_set_quarter_marks(),
                ),
            ],
        )
        self.page.overlay.append(self._ins_qt_dialog)
        self._ins_qt_dialog.open = True
        self.page.update()

    def _close_ins_qt_dialog(self):
        if hasattr(self, '_ins_qt_dialog') and self._ins_qt_dialog:
            self._ins_qt_dialog.open = False
            self.page.update()

    def _confirm_set_quarter_marks(self):
        self._close_ins_qt_dialog()
        groups = self._get_selected_groups()
        subjects = self._get_selected_subjects()
        quarters = self._get_selected_quarters()

        self.quarter_marks_btn.disabled = True
        self.start_btn.disabled = True
        self.analyze_btn.disabled = True
        self.delete_quarter_btn.disabled = True
        self.stop_btn.disabled = False
        self.progress_label.value = "Расчёт четвертных оценок..."
        self.progress_pct.color = ft.Colors.AMBER_600
        self.page.update()

        def run():
            try:
                # Step 1: Wait for edonish API to sync (if grades were just inserted)
                self._log_message("Запрос свежих данных с edonish...")
                time.sleep(1)

                # Step 2: Build quarter marks plan using ceil(average)
                qplan = self.engine.build_grade_plan_for_quarter_marks(
                    groups=groups,
                    subjects=subjects,
                    quarters=quarters,
                    min_grade=int(self.min_grade_field.value or MIN_GRADE),
                    max_grade=int(self.max_grade_field.value or MAX_GRADE),
                    fill_empty_only=self.fill_empty_check.value,
                )
                if qplan.total_tasks > 0:
                    self._log_message(f"Установка {qplan.total_tasks} четвертных оценок...")
                    self.engine.execute_quarter_marks(qplan)
                else:
                    self._log_message("Все четвертные оценки уже поставлены или нет оценок для расчёта")
            except Exception as e:
                self._log_message(f"Ошибка четвертных: {e}", "error")
            finally:
                self._on_set_quarter_marks_complete()

        threading.Thread(target=run, daemon=True).start()

    def _on_set_quarter_marks_complete(self):
        self.quarter_marks_btn.disabled = False
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
        self.analyze_btn.disabled = False
        self.delete_quarter_btn.disabled = False
        self.progress_pct.color = ft.Colors.BLUE_600
        self.progress_label.value = "Четвертные оценки поставлены"
        # Reload journal if loaded
        if self._journal_loaded and self._current_journal_params:
            self._log_message("Обновление журнала...")
            self._reload_journal()
        self.page.run_thread(self._safe_update)

    def _on_delete_quarter_marks(self):
        """Delete ONLY quarter marks for selected groups/subjects/quarters."""
        groups = self._get_selected_groups()
        subjects = self._get_selected_subjects()
        quarters = self._get_selected_quarters()

        if not groups or not subjects or not quarters:
            self._show_snackbar("Выберите класс, предмет и четверть!")
            return

        # Confirmation dialog
        self._del_qt_dialog = AlertDialog(
            modal=True,
            title=Text("Удаление четвертных оценок", weight=FontWeight.W_700),
            content=Text(
                "Удалить ТОЛЬКО четвертные оценки\n"
                "для выбранных класса, предмета и четверти?\n\n"
                "Обычные оценки НЕ будут затронуты.",
                size=15,
            ),
            actions=[
                TextButton(
                    content=Text("Отмена", size=15),
                    on_click=lambda _: self._close_del_qt_dialog(),
                ),
                FilledButton(
                    content=ft.Text("Удалить четвертные", size=15, weight=FontWeight.W_600),
                    style=ButtonStyle(bgcolor=ft.Colors.ORANGE_600),
                    on_click=lambda _: self._confirm_delete_quarter_marks(),
                ),
            ],
        )
        self.page.overlay.append(self._del_qt_dialog)
        self._del_qt_dialog.open = True
        self.page.update()

    def _close_del_qt_dialog(self):
        if hasattr(self, '_del_qt_dialog') and self._del_qt_dialog:
            self._del_qt_dialog.open = False
            self.page.update()

    def _confirm_delete_quarter_marks(self):
        self._close_del_qt_dialog()
        groups = self._get_selected_groups()
        subjects = self._get_selected_subjects()
        quarters = self._get_selected_quarters()

        self.delete_quarter_btn.disabled = True
        self.quarter_marks_btn.disabled = True
        self.start_btn.disabled = True
        self.analyze_btn.disabled = True
        self.stop_btn.disabled = False
        self.progress_label.value = "Удаление четвертных оценок..."
        self.progress_pct.value = "0%"
        self.progress_pct.color = ft.Colors.ORANGE_600
        self.page.update()

        def run():
            try:
                self.engine.execute_delete_quarter_marks(
                    groups=groups,
                    subjects=subjects,
                    quarters=quarters,
                )
            except Exception as e:
                self._log_message(f"Ошибка удаления четвертных: {e}", "error")
            finally:
                self._on_delete_quarter_marks_complete()

        threading.Thread(target=run, daemon=True).start()

    def _on_delete_quarter_marks_complete(self):
        self.delete_quarter_btn.disabled = False
        self.quarter_marks_btn.disabled = False
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
        self.analyze_btn.disabled = False
        self.progress_pct.color = ft.Colors.BLUE_600
        self.progress_label.value = "Четвертные удалены"
        # Reload journal if loaded
        if self._journal_loaded and self._current_journal_params:
            self._log_message("Обновление журнала...")
            self._reload_journal()
        self.page.run_thread(self._safe_update)

    def _on_set_quarter_mark(self, row: int):
        """Set quarter mark for a single student as ceil(average of their subject marks).
        
        Fetches fresh data from edonish API first, then calculates ceil(average).
        """
        if not self._journal_loaded:
            return

        qdata = self._student_quarter_data.get(row)
        if not qdata:
            self._show_snackbar("Нет данных ученика")
            return

        params = self._current_journal_params
        student_id = qdata["student_id"]

        self._log_message(f"Запрос данных с edonish для расчёта четвертной (строка {row + 1})...")

        def do_set():
            try:
                # Step 1: Fetch FRESH student data from edonish API
                students = self.api.get_journal_students(
                    group_id=params["group_id"],
                    subject_id=params["subject_id"],
                    quarter_property_id=params["qprop_id"],
                )

                # Step 2: Find our student in the fresh data
                student = None
                for s in (students or []):
                    if s.get("studentId") == student_id:
                        student = s
                        break

                if not student:
                    self._log_message(f"Ученик не найден в ответе API (строка {row + 1})", "error")
                    return

                # Step 3: Extract grades from fresh API response
                grade_values = []
                for m in (student.get("subjectMarks") or []):
                    sn = m.get("shortName", "")
                    if sn and sn.isdigit():
                        v = int(sn)
                        if MIN_GRADE <= v <= MAX_GRADE:
                            grade_values.append(v)

                if not grade_values:
                    self._log_message(f"У ученика нет оценок для расчёта четвертной (строка {row + 1})", "error")
                    return

                # Step 4: Calculate ceil(average)
                avg = sum(grade_values) / len(grade_values)
                grade = min(max(int(math.ceil(avg)), MIN_GRADE), MAX_GRADE)
                self._log_message(
                    f"Четвертная (строка {row + 1}): оценки={grade_values}, "
                    f"ср.={avg:.2f}, ceil={grade}"
                )

                # Step 5: Save quarter mark to edonish
                result = self.api.create_quarter_mark(
                    student_id=student_id,
                    quarter_property_id=qdata["qprop_id"],
                    mark=grade,
                    subject_id=qdata["subject_id"],
                    curriculum_property_id=qdata["curriculum_property_id"],
                )
                if result and not (isinstance(result, dict) and result.get("error")):
                    self._log_message(f"✅ Четвертная оценка {grade} поставлена (строка {row + 1})")
                    # Reload journal to show the updated quarter mark
                    self._reload_journal()
                else:
                    self._log_message(f"Ошибка четвертной оценки: {result}", "error")
            except Exception as ex:
                self._log_message(f"Ошибка: {ex}", "error")

        threading.Thread(target=do_set, daemon=True).start()

    def _on_delete_single_quarter_mark(self, row: int, quarter_mark_id: str):
        """Delete a single student's quarter mark by long-pressing the quarter cell."""
        if not quarter_mark_id:
            self._show_snackbar("Нет четвертной оценки для удаления")
            return

        qdata = self._student_quarter_data.get(row)
        student_name = ""

        self._log_message(f"Удаление четвертной оценки (строка {row + 1})...")

        def do_delete():
            try:
                result = self.api.delete_quarter_mark(
                    quarter_mark_id=quarter_mark_id,
                    student_id=qdata.get("student_id") if qdata else None,
                    quarter_property_id=qdata.get("qprop_id") if qdata else None,
                    subject_id=qdata.get("subject_id") if qdata else None,
                    curriculum_property_id=qdata.get("curriculum_property_id") if qdata else None,
                )
                self._log_message(f"✅ Четвертная оценка удалена (строка {row + 1})")
                self._reload_journal()
            except Exception as ex:
                self._log_message(f"❌ Ошибка удаления четвертной: {ex}", "error")

        threading.Thread(target=do_delete, daemon=True).start()

    def _reload_journal(self):
        """Reload the journal using the stored params (after grade operations)."""
        params = self._current_journal_params
        if not params:
            return
        group_id = params["group_id"]
        subject_id = params["subject_id"]
        qprop_id = params["qprop_id"]

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
                self._display_journal_grid(students, dates_data)
            except Exception as e:
                self._log_message(f"Ошибка обновления журнала: {e}", "error")

        threading.Thread(target=load, daemon=True).start()

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
        self.analyze_btn.content.value = "Анализ..."
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
                self.page.run_thread(self._safe_update)

        threading.Thread(target=analyze, daemon=True).start()

    def _on_analyze_complete(self, plan: GradePlan):
        self.analyze_btn.disabled = False
        self.start_btn.disabled = False
        self.signature_btn.disabled = False

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

        if to_execute == 0 and plan.skipped > 0:
            lines.append(f"  ⚠ Все ячейки уже заполнены оценками!")
            lines.append(f"  Снимите галочку 'Только пустые ячейки',")
            lines.append(f"  чтобы перезаписать существующие оценки.")
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
        
        if to_execute == 0 and plan.skipped > 0:
            self.progress_label.value = f"Все ячейки заполнены ({plan.skipped} пропущено)"
            self.progress_bar.value = 1.0
            self.progress_pct.value = "100%"
            self.progress_pct.color = ft.Colors.ORANGE_600
            self.stats_label.value = f"Заполнено: {plan.skipped} | Снимите 'Только пустые' для перезаписи"
            self.start_btn.disabled = True
        else:
            self.progress_label.value = f"Анализ завершён: {to_execute} оценок будет добавлено"
            self.progress_bar.value = 0
            self.progress_pct.value = "0%"
            self.progress_pct.color = ft.Colors.BLUE_600
            self.stats_label.value = f"Будет добавлено: {to_execute}  |  Пропущено: {plan.skipped}"

        self.page.run_thread(self._safe_update)

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
                if self.signature_check.value:
                    self._log_message("Добавление подписей...")
                    signature_text = self.signature_field.value or "Подпись"
                    self.engine.execute_signatures(
                        groups=self._get_selected_groups(),
                        subjects=self._get_selected_subjects(),
                        quarters=self._get_selected_quarters(),
                        signature_text=signature_text,
                        fill_empty_only=self.fill_empty_check.value,
                    )

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
            pct = done / total if total > 0 else 1.0
            self.progress_label.value = f"Завершено: {done}/{total}"
            self.progress_pct.value = f"{pct * 100:.0f}%"
            self.progress_bar.value = pct
            self.stats_label.value = f"Успешно: {plan.completed}  |  Ошибки: {plan.failed}  |  Пропущено: {plan.skipped}"
        self.page.run_thread(self._safe_update)

    # ════════════════════════════════════════════════════════════════
    #  INTERACTIVE JOURNAL GRID
    # ════════════════════════════════════════════════════════════════

    def _on_load_journal(self):
        """Load journal data and build the interactive grade grid."""
        class_name = self.journal_class_dropdown.value
        subject_name = self.journal_subject_dropdown.value
        quarter_name = self.journal_quarter_dropdown.value

        if not class_name or class_name in ("", "Все классы"):
            self._show_snackbar("Выберите конкретный класс для загрузки журнала!")
            return

        if not subject_name or subject_name in ("", ):
            self._show_snackbar("Выберите предмет!")
            return

        group_id = None
        subject_id = None
        qprop_id = None

        for g in self.groups_data:
            if g["name"] == class_name:
                group_id = g["id"]
                break

        for s in self.teacher_subjects:
            if s["subjectName"] == subject_name:
                subject_id = s["subjectId"]
                break

        # Look up quarter ID from journal_options for this specific group
        # (different groups may have different quarter IDs)
        for g in (self.journal_options or {}).get("groups", []):
            gname = f"{g.get('number', '')}{g.get('name', '')}"
            if gname == class_name:
                for q in g.get("quarters", []):
                    if q.get("name") == quarter_name:
                        qprop_id = q["id"]
                        break
                break

        # Fallback to quarters_data if not found in journal_options
        if not qprop_id:
            for q in self.quarters_data:
                if q.get("name") == quarter_name:
                    qprop_id = q["qpropId"]
                    break

        if not all([group_id, subject_id, qprop_id]):
            self._show_snackbar("Выберите класс, предмет и четверть!")
            return

        # Store for later API calls from cells
        # Find curriculum_property_id for this subject
        curriculum_property_id = 0
        for ts in self.teacher_subjects:
            if ts.get("subjectId") == subject_id:
                curriculum_property_id = ts.get("curriculumPropertyId", 0)
                break

        self._current_journal_params = {
            "group_id": group_id,
            "subject_id": subject_id,
            "qprop_id": qprop_id,
            "curriculum_property_id": curriculum_property_id,
        }

        self._student_quarter_data = {}  # row_idx -> {student_id, qprop_id, subject_id, curriculum_property_id, quarter_mark_id, quarter_mark_value}

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
                self._display_journal_grid(students, dates_data)
            except Exception as e:
                self._log_message(f"Ошибка загрузки журнала: {e}", "error")

        threading.Thread(target=load, daemon=True).start()

    def _display_journal_grid(self, students, dates_data):
        """Build an interactive grade grid with editable cells, arrow-key nav, and Delete support."""
        # Reset grid state
        self._grade_cells = {}
        self._grade_data = {}
        self._selected_cell = None
        self._student_quarter_data = {}
        self._journal_dates = []  # Store dates for random grade and topic features

        if not students:
            self.journal_grid_container.content = Column(
                [Text("Нет данных", size=16, color=ft.Colors.GREY_600, text_align=TextAlign.CENTER)],
                horizontal_alignment=CrossAxisAlignment.CENTER,
            )
            self._journal_loaded = False
            self.journal_clear_btn.visible = False
            self.journal_insert_quarter_btn.visible = False
            self.journal_delete_quarter_btn.visible = False
            self.journal_save_btn.disabled = True
            self.journal_topic_field.visible = False
            self.journal_fill_topics_btn.visible = False
            self.page.update()
            return

        dates = []
        if dates_data and dates_data[0].get("days"):
            dates = dates_data[0]["days"]

        self._journal_dates = dates  # Store for random grade and topic features

        self.journal_student_count.value = f"{len(students)} учеников | {len(dates)} дат"
        self.journal_clear_btn.visible = True
        self.journal_insert_quarter_btn.visible = True
        self.journal_delete_quarter_btn.visible = True
        self.journal_save_btn.disabled = False
        self.journal_topic_field.visible = True
        self.journal_fill_topics_btn.visible = True
        self._journal_loaded = True

        self._grid_rows = len(students)
        self._grid_cols = len(dates)

        # Build header row
        header_cells = [
            Container(
                content=Text("#", size=12, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
                width=40,
                padding=4,
                bgcolor=ft.Colors.BLUE_50,
                border=Border(
                    right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    bottom=BorderSide(2, ft.Colors.BLUE_200),
                ),
            ),
            Container(
                content=Text("Ученик", size=12, weight=FontWeight.BOLD),
                width=180,
                padding=4,
                bgcolor=ft.Colors.BLUE_50,
                border=Border(
                    right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    bottom=BorderSide(2, ft.Colors.BLUE_200),
                ),
            ),
            Container(
                content=Text("🎲", size=14, text_align=TextAlign.CENTER),
                width=36,
                padding=2,
                bgcolor=ft.Colors.BLUE_50,
                border=Border(
                    right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    bottom=BorderSide(2, ft.Colors.BLUE_200),
                ),
                tooltip="Рандом оценки для ученика",
            ),
        ]
        for d in dates:
            date_str = d.get("assignmentDate", "")[5:]  # MM-DD
            assignment = d.get("assignment", "") or d.get("topic", "")
            # Show date + assignment topic below
            header_content = Column([
                Text(date_str, size=11, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
            ], spacing=0, alignment=CrossAxisAlignment.CENTER)
            if assignment:
                header_content.controls.append(
                    Text(assignment[:12], size=8, color=ft.Colors.GREY_600, text_align=TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                )
            header_cells.append(
                Container(
                    content=header_content,
                    width=48,
                    padding=2,
                    bgcolor=ft.Colors.BLUE_50,
                    border=Border(
                        right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                        bottom=BorderSide(2, ft.Colors.BLUE_200),
                    ),
                )
            )
        # Quarter/Semester/Year columns
        for label in ["Чтв", "Смст", "Год"]:
            header_cells.append(
                Container(
                    content=Text(label, size=11, weight=FontWeight.BOLD, text_align=TextAlign.CENTER),
                    width=44,
                    padding=2,
                    bgcolor=ft.Colors.BLUE_50,
                    border=Border(
                        right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                        bottom=BorderSide(2, ft.Colors.BLUE_200),
                    ),
                )
            )

        header_row = Row(header_cells, spacing=0, alignment=MainAxisAlignment.START)

        # Build student rows
        student_rows = [header_row]
        total_marks = 0
        empty_cells = 0

        for row_idx, s in enumerate(students):
            student_id = s["studentId"]
            student_name = f"{s.get('lastName', '')} {s.get('firstName', '')}"

            # Build marks_by_date map: date_id -> mark info
            marks_by_date = {}
            for m in (s.get("subjectMarks") or []):
                marks_by_date[m.get("assignmentDateId")] = m

            # Row number cell
            row_cells = [
                Container(
                    content=Text(str(row_idx + 1), size=13, text_align=TextAlign.CENTER, color=ft.Colors.GREY_600),
                    width=40,
                    padding=4,
                    bgcolor=ft.Colors.GREY_50 if row_idx % 2 == 0 else ft.Colors.SURFACE,
                    border=Border(
                        right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                        bottom=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    ),
                ),
                Container(
                    content=Text(student_name, size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    width=180,
                    padding=4,
                    bgcolor=ft.Colors.GREY_50 if row_idx % 2 == 0 else ft.Colors.SURFACE,
                    border=Border(
                        right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                        bottom=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    ),
                ),
                # 🎲 Random grade button for this student
                Container(
                    content=IconButton(
                        icon=Icons.CASINO,
                        icon_size=16,
                        icon_color=ft.Colors.TEAL_600,
                        tooltip=f"Рандом оценки: {student_name}",
                        on_click=lambda e, r=row_idx: self._on_random_grades_for_student(r),
                        style=ButtonStyle(padding=0),
                    ),
                    width=36,
                    padding=2,
                    bgcolor=ft.Colors.GREY_50 if row_idx % 2 == 0 else ft.Colors.SURFACE,
                    border=Border(
                        right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                        bottom=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    ),
                    alignment=ft.Alignment(0, 0),
                ),
            ]

            # Date/grade cells
            for col_idx, d in enumerate(dates):
                date_id = d["assignmentDateId"]
                mark_info = marks_by_date.get(date_id)
                mark_value = mark_info.get("shortName", "") if mark_info else ""
                mark_id = mark_info.get("assignmentMarkId", "") if mark_info else ""
                qprop_id = d.get("quarterPropertyId", self._current_journal_params.get("qprop_id", 0))

                if mark_value:
                    total_marks += 1
                else:
                    empty_cells += 1

                # Create editable grade cell
                cell = self._make_grade_cell(
                    row=row_idx, col=col_idx,
                    value=mark_value,
                    mark_id=mark_id,
                    student_id=student_id,
                    date_id=date_id,
                    qprop_id=qprop_id,
                )
                row_cells.append(cell)

            # Quarter mark cell: clickable to set ceil(average) as quarter grade
            params = self._current_journal_params
            quarter_mark_list = s.get("quarterMark", [])
            quarter_mark_val = ""
            quarter_mark_id = ""
            if quarter_mark_list and len(quarter_mark_list) > 0:
                quarter_mark_val = quarter_mark_list[0].get("shortName", "")
                quarter_mark_id = quarter_mark_list[0].get("quarterMarkId", "") or quarter_mark_list[0].get("assignmentMarkId", "")

            # Store quarter data for this student
            self._student_quarter_data[row_idx] = {
                "student_id": student_id,
                "qprop_id": params.get("qprop_id", 0),
                "subject_id": params.get("subject_id", 0),
                "curriculum_property_id": params.get("curriculum_property_id", 0),
                "quarter_mark_id": quarter_mark_id,
                "quarter_mark_value": quarter_mark_val,
            }

            # Calculate ceil(average) for tooltip
            grade_values = []
            for m in (s.get("subjectMarks") or []):
                sn = m.get("shortName", "")
                if sn and sn.isdigit():
                    v = int(sn)
                    if MIN_GRADE <= v <= MAX_GRADE:
                        grade_values.append(v)
            if grade_values:
                avg = sum(grade_values) / len(grade_values)
                ceil_grade = min(max(int(math.ceil(avg)), MIN_GRADE), MAX_GRADE)
                quarter_tooltip = f"Ср. балл: {avg:.2f} → Чтв: {ceil_grade} (кнопка 'Вставить Чтв')"
                if quarter_mark_val:
                    quarter_tooltip += " | долгое нажатие: удалить"
            else:
                ceil_grade = None
                quarter_tooltip = "Нет оценок для расчёта четвертной"

            # Quarter mark cell — display-only; insertion only via "Вставить Чтв" button
            quarter_bgcolor = ft.Colors.AMBER_50 if quarter_mark_val else (ft.Colors.GREY_50 if row_idx % 2 == 0 else ft.Colors.SURFACE)
            if not grade_values and not quarter_mark_val:
                # No grades and no quarter mark — dimmed to show "not applicable"
                quarter_bgcolor = ft.Colors.GREY_100
            quarter_cell = Container(
                content=Text(quarter_mark_val, size=14, weight=FontWeight.W_500, text_align=TextAlign.CENTER),
                width=44,
                padding=2,
                bgcolor=quarter_bgcolor,
                border=Border(
                    right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    bottom=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                    left=BorderSide(2, ft.Colors.AMBER_300) if quarter_mark_val else BorderSide(0, ft.Colors.TRANSPARENT),
                ),
                tooltip=quarter_tooltip,
                on_long_press=lambda e, r=row_idx, qmid=quarter_mark_id: self._on_delete_single_quarter_mark(r, qmid),
            )
            row_cells.append(quarter_cell)

            # Semester and Year mark cells (read-only display)
            for mark_key in ["semesterMark", "yearMark"]:
                mark_list = s.get(mark_key, [])
                mark_val = ""
                if mark_list and len(mark_list) > 0:
                    mark_val = mark_list[0].get("shortName", "")
                row_cells.append(
                    Container(
                        content=Text(mark_val, size=14, weight=FontWeight.W_500, text_align=TextAlign.CENTER),
                        width=44,
                        padding=2,
                        bgcolor=ft.Colors.GREY_50 if row_idx % 2 == 0 else ft.Colors.SURFACE,
                        border=Border(
                            right=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                            bottom=BorderSide(1, ft.Colors.OUTLINE_VARIANT),
                        ),
                    )
                )

            student_rows.append(Row(row_cells, spacing=0, alignment=MainAxisAlignment.START))

        # Stats row
        pct = (total_marks / (total_marks + empty_cells) * 100) if (total_marks + empty_cells) > 0 else 0
        stats_row = Row([
            Container(
                content=Text(
                    f"Заполнено: {total_marks} | Пустых: {empty_cells} | Заполненность: {pct:.0f}%",
                    size=12, color=ft.Colors.GREY_600,
                ),
                padding=8,
            ),
        ], spacing=0)
        student_rows.append(Container(height=8))
        student_rows.append(stats_row)

        # Help text
        student_rows.append(Container(height=4))
        student_rows.append(Text(
            "Стрелки: навигация | Цифра 3-10: поставить оценку | Delete: удалить | Кнопка 'Вставить Чтв': вставить четвертные | Долгое нажатие на Чтв: удалить",
            size=11, color=ft.Colors.GREY_400,
        ))

        # Set the grid
        self.journal_grid_container.content = Column(
            student_rows,
            scroll=ScrollMode.AUTO,
            expand=True,
            spacing=0,
        )

        self._log_message(f"Журнал загружен: {total_marks} оценок, {empty_cells} пустых")

        # Update dashboard keyboard handler to include grid navigation
        self.page.on_keyboard_event = self._on_dashboard_keyboard

        try:
            self.page.run_thread(self._safe_update)
        except Exception:
            pass

    def _make_grade_cell(self, row, col, value, mark_id, student_id, date_id, qprop_id):
        """Create a single editable grade cell (TextField)."""
        has_mark = bool(value and str(value).strip())
        cell_bgcolor = ft.Colors.GREEN_50 if has_mark else (
            ft.Colors.GREY_50 if row % 2 == 0 else ft.Colors.SURFACE
        )

        # Store data for this cell
        self._grade_data[(row, col)] = {
            "mark_id": mark_id,
            "student_id": student_id,
            "date_id": date_id,
            "qprop_id": qprop_id,
            "current_value": value,
            "original_value": value,
        }

        cell = TextField(
            value=str(value) if value else "",
            width=48,
            height=38,
            text_size=15,
            text_align=TextAlign.CENTER,
            text_vertical_align=ft.VerticalAlignment.CENTER,
            border_radius=4,
            border_color=ft.Colors.TRANSPARENT,
            focused_border_color=ft.Colors.BLUE_600,
            content_padding=ft.controls.padding.Padding(left=2, right=2, top=4, bottom=4),
            bgcolor=cell_bgcolor,
            input_filter=ft.NumbersOnlyInputFilter(),
            max_length=2,
            on_focus=lambda e, r=row, c=col: self._on_cell_focus(r, c),
            on_submit=lambda e, r=row, c=col: self._on_cell_submit(r, c, e),
            on_change=lambda e, r=row, c=col: self._on_cell_change(r, c, e),
        )

        self._grade_cells[(row, col)] = cell
        return cell

    def _on_cell_focus(self, row, col):
        """Handle cell focus — track selected cell for arrow navigation."""
        self._selected_cell = (row, col)

    def _on_cell_change(self, row, col, e):
        """Handle typing in a cell — auto-submit if valid grade digit entered."""
        val = e.control.value
        if not val or not val.strip():
            return
        digit = val.strip()
        if not digit.isdigit():
            e.control.value = self._grade_data.get((row, col), {}).get("current_value", "")
            try:
                self.page.update()
            except Exception:
                pass
            return
        grade = int(digit)
        if MIN_GRADE <= grade <= MAX_GRADE:
            # Valid grade — submit it after short delay to allow full number entry
            if grade == 1 and MAX_GRADE >= 10:
                # Could be "10" — wait for next digit
                return
            self._set_cell_grade(row, col, grade)
        elif grade > MAX_GRADE:
            # Too high — reject
            e.control.value = ""
            self._show_snackbar(f"Оценка должна быть от {MIN_GRADE} до {MAX_GRADE}")
            try:
                self.page.update()
            except Exception:
                pass
        elif grade < MIN_GRADE and digit == "1":
            # Could be start of "10" — wait
            pass
        elif grade < MIN_GRADE:
            e.control.value = ""
            self._show_snackbar(f"Оценка должна быть от {MIN_GRADE} до {MAX_GRADE}")
            try:
                self.page.update()
            except Exception:
                pass

    def _on_cell_submit(self, row, col, e):
        """Handle Enter key on a cell — submit the grade."""
        val = e.control.value
        if val and val.strip() and val.strip().isdigit():
            grade = int(val.strip())
            if MIN_GRADE <= grade <= MAX_GRADE:
                self._set_cell_grade(row, col, grade)
            else:
                self._show_snackbar(f"Оценка должна быть от {MIN_GRADE} до {MAX_GRADE}")
                e.control.value = self._grade_data[(row, col)].get("current_value", "")
                self.page.update()

    def _set_cell_grade(self, row, col, grade):
        """Set a grade for a cell via API call. Deletes existing mark first if present."""
        data = self._grade_data.get((row, col))
        if not data:
            return

        cell = self._grade_cells.get((row, col))
        if not cell:
            return

        cell.border_color = ft.Colors.ORANGE_400
        self.page.update()

        def do_set():
            try:
                # Delete existing mark before creating a new one
                existing_mark_id = data.get("mark_id", "")
                if existing_mark_id:
                    try:
                        self.api.delete_mark(mark_id=existing_mark_id)
                    except Exception:
                        pass  # Old mark may not exist or already deleted
                result = self.api.create_mark(
                    student_id=data["student_id"],
                    assignment_date_id=data["date_id"],
                    mark=grade,
                    quarter_property_id=data["qprop_id"],
                )
                if result and not (isinstance(result, dict) and result.get("error")):
                    data["current_value"] = str(grade)
                    data["mark_id"] = result.get("assignmentMarkId", "") if isinstance(result, dict) else ""
                    cell.value = str(grade)
                    cell.bgcolor = ft.Colors.GREEN_50
                    cell.border_color = ft.Colors.TRANSPARENT
                    self._log_message(f"Оценка {grade} поставлена (строка {row + 1})")
                    # Move to next cell
                    self._move_to_cell(row, col + 1)
                else:
                    cell.border_color = ft.Colors.RED_400
                    self._log_message(f"Ошибка установки оценки: {result}", "error")
            except Exception as ex:
                cell.border_color = ft.Colors.RED_400
                self._log_message(f"Ошибка: {ex}", "error")
            finally:
                self.page.run_thread(self._safe_update)

        threading.Thread(target=do_set, daemon=True).start()

    def _delete_cell_grade(self, row, col):
        """Delete the grade from a cell via API call."""
        data = self._grade_data.get((row, col))
        if not data:
            return

        cell = self._grade_cells.get((row, col))
        if not cell:
            return

        mark_id = data.get("mark_id", "")
        if not mark_id:
            # No grade to delete — just clear the cell visually
            cell.value = ""
            data["current_value"] = ""
            self.page.update()
            return

        cell.border_color = ft.Colors.RED_400
        self.page.update()

        def do_delete():
            try:
                result = self.api.delete_mark(mark_id=mark_id)
                cell.value = ""
                cell.bgcolor = ft.Colors.GREY_50 if row % 2 == 0 else ft.Colors.SURFACE
                cell.border_color = ft.Colors.TRANSPARENT
                data["current_value"] = ""
                data["mark_id"] = ""
                self._log_message(f"Оценка удалена (строка {row + 1}, столбец {col + 1})")
            except Exception as ex:
                cell.border_color = ft.Colors.RED_400
                self._log_message(f"Ошибка удаления: {ex}", "error")
            finally:
                self.page.run_thread(self._safe_update)

        threading.Thread(target=do_delete, daemon=True).start()

    def _move_to_cell(self, row, col):
        """Move focus to a specific cell in the grid."""
        # Wrap around
        if col >= self._grid_cols:
            col = 0
            row += 1
        if row >= self._grid_rows:
            row = 0
        if row < 0:
            row = self._grid_rows - 1
        if col < 0:
            col = self._grid_cols - 1

        target = self._grade_cells.get((row, col))
        if target:
            self._selected_cell = (row, col)
            # In Flet 0.85.2, focus() is async. We must not await it from
            # a sync context. Simply call it — the underlying Flet protocol
            # command is still dispatched even though the coroutine is not
            # awaited; suppress the RuntimeWarning.
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                target.focus()

    def _on_random_grades_for_student(self, row: int):
        """Fill all empty cells for a specific student with random grades."""
        if not self._journal_loaded:
            return

        min_grade = int(self.min_grade_field.value or MIN_GRADE)
        max_grade = int(self.max_grade_field.value or MAX_GRADE)
        dates = self._journal_dates

        # Collect empty cells for this student
        tasks = []  # list of (col_idx, date_id, qprop_id, grade)
        for col_idx in range(self._grid_cols):
            data = self._grade_data.get((row, col_idx))
            if not data:
                continue
            current_val = data.get("current_value", "")
            if current_val and str(current_val).strip():
                continue  # Skip non-empty cells

            # Generate random grade
            grade = random.randint(min_grade, max_grade)
            tasks.append((col_idx, data["date_id"], data["qprop_id"], grade))

        if not tasks:
            self._show_snackbar("Нет пустых ячеек для заполнения")
            return

        student_name = ""
        qdata = self._student_quarter_data.get(row, {})
        student_id = qdata.get("student_id", 0)

        # Find student name from first cell data
        for col_idx in range(self._grid_cols):
            data = self._grade_data.get((row, col_idx))
            if data:
                break

        self._log_message(f"🎲 Рандом оценок: строка {row + 1}, {len(tasks)} пустых ячеек")

        def do_random():
            completed = 0
            failed = 0
            for col_idx, date_id, qprop_id, grade in tasks:
                try:
                    # Delete existing mark if any
                    data = self._grade_data.get((row, col_idx))
                    existing_mark_id = data.get("mark_id", "") if data else ""
                    if existing_mark_id:
                        try:
                            self.api.delete_mark(mark_id=existing_mark_id)
                        except Exception:
                            pass

                    result = self.api.create_mark(
                        student_id=student_id,
                        assignment_date_id=date_id,
                        mark=grade,
                        quarter_property_id=qprop_id,
                    )
                    if result and not (isinstance(result, dict) and result.get("error")):
                        completed += 1
                        # Update cell visually
                        cell = self._grade_cells.get((row, col_idx))
                        if cell and data:
                            cell.value = str(grade)
                            cell.bgcolor = ft.Colors.GREEN_50
                            cell.border_color = ft.Colors.TRANSPARENT
                            data["current_value"] = str(grade)
                            data["mark_id"] = result.get("assignmentMarkId", "") if isinstance(result, dict) else ""
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    self._log_message(f"  ❌ Ошибка: {e}", "error")

                time.sleep(0.15)

            self._log_message(f"🎲 Рандом: ✅ {completed} оценок поставлено, ❌ {failed} ошибок (строка {row + 1})")
            self.page.run_thread(self._safe_update)

        threading.Thread(target=do_random, daemon=True).start()

    def _on_fill_topics(self):
        """Fill topic/assignment text for all dates in the current journal."""
        if not self._journal_loaded or not self._current_journal_params:
            self._show_snackbar("Сначала загрузите журнал!")
            return

        topic_text = self.journal_topic_field.value
        if not topic_text or not topic_text.strip():
            self._show_snackbar("Введите тему урока!")
            return

        topic_text = topic_text.strip()
        dates = self._journal_dates
        params = self._current_journal_params
        qprop_id = params.get("qprop_id", 0)

        self._log_message(f"📝 Заполнение тем: '{topic_text}' для {len(dates)} дат...")

        self.journal_fill_topics_btn.disabled = True
        self.page.update()

        def do_fill():
            completed = 0
            failed = 0
            for d in dates:
                date_id = d.get("assignmentDateId", "")
                if not date_id:
                    continue
                # Skip dates that already have a topic
                existing_topic = d.get("assignment", "") or d.get("topic", "")
                if existing_topic:
                    continue
                try:
                    result = self.api.update_assignment(
                        assignment_date_id=date_id,
                        assignment=topic_text,
                        quarter_property_id=qprop_id,
                    )
                    if result:
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    self._log_message(f"  ❌ Ошибка темы: {e}", "error")

                time.sleep(0.1)

            self._log_message(f"📝 Темы: ✅ {completed} заполнено, ❌ {failed} ошибок")
            self.journal_fill_topics_btn.disabled = False
            # Reload journal to show updated topics
            self._reload_journal()
            self.page.run_thread(self._safe_update)

        threading.Thread(target=do_fill, daemon=True).start()

    def _on_clear_all_grades(self):
        """Clear all grades in the current journal view with confirmation."""
        if not self._journal_loaded:
            self._show_snackbar("Сначала загрузите журнал!")
            return

        # Confirmation dialog
        self._clear_dialog = AlertDialog(
            modal=True,
            title=Text("Очистить все оценки", weight=FontWeight.W_700),
            content=Text(
                "Вы уверены, что хотите удалить ВСЕ оценки\n"
                "из загруженного журнала?\n\n"
                "Это действие нельзя отменить!",
                size=15,
            ),
            actions=[
                TextButton(
                    content=Text("Отмена", size=15),
                    on_click=lambda _: self._close_clear_dialog(),
                ),
                FilledButton(
                    content=ft.Text("Очистить все", size=15, weight=FontWeight.W_600),
                    style=ButtonStyle(bgcolor=ft.Colors.RED_600),
                    on_click=lambda _: self._confirm_clear_all(),
                ),
            ],
        )
        self.page.overlay.append(self._clear_dialog)
        self._clear_dialog.open = True
        self.page.update()

    def _close_clear_dialog(self):
        if hasattr(self, '_clear_dialog') and self._clear_dialog:
            self._clear_dialog.open = False
            self.page.update()

    def _confirm_clear_all(self):
        self._close_clear_dialog()
        # Delete all grades that have mark_ids
        marks_to_delete = []
        for (row, col), data in self._grade_data.items():
            if data.get("mark_id"):
                marks_to_delete.append(data["mark_id"])

        if not marks_to_delete:
            self._show_snackbar("Нет оценок для удаления")
            return

        self._log_message(f"Удаление {len(marks_to_delete)} оценок из журнала...")
        self.journal_clear_btn.disabled = True
        self.page.update()

        def run():
            deleted = 0
            failed = 0
            for mark_id in marks_to_delete:
                try:
                    self.api.delete_mark(mark_id=mark_id)
                    deleted += 1
                except Exception as e:
                    failed += 1
                    self._log_message(f"Ошибка удаления: {e}", "error")
                time.sleep(0.1)

            self._log_message(f"Удаление завершено: {deleted} удалено, {failed} ошибок")
            self.journal_clear_btn.disabled = False
            try:
                self.page.run_thread(self._safe_update)
            except Exception:
                pass
            # Reload journal to reflect changes
            self._on_load_journal()

        threading.Thread(target=run, daemon=True).start()

    def _on_journal_insert_quarter(self):
        """Insert quarter marks for the currently loaded journal."""
        if not self._journal_loaded or not self._current_journal_params:
            self._show_snackbar("Сначала загрузите журнал!")
            return

        # Confirmation dialog
        self._jq_ins_dialog = AlertDialog(
            modal=True,
            title=Text("Вставка четвертных оценок", weight=FontWeight.W_700),
            content=Text(
                "Вставить четвертные оценки\n"
                "для текущего журнала?\n\n"
                "Расчёт: ceil(среднее арифметическое)\n"
                "Ученики без оценок будут ПРОПУЩЕНЫ.",
                size=15,
            ),
            actions=[
                TextButton(
                    content=Text("Отмена", size=15),
                    on_click=lambda _: self._close_jq_ins_dialog(),
                ),
                FilledButton(
                    content=ft.Text("Вставить", size=15, weight=FontWeight.W_600),
                    style=ButtonStyle(bgcolor=ft.Colors.AMBER_600),
                    on_click=lambda _: self._confirm_journal_insert_quarter(),
                ),
            ],
        )
        self.page.overlay.append(self._jq_ins_dialog)
        self._jq_ins_dialog.open = True
        self.page.update()

    def _close_jq_ins_dialog(self):
        if hasattr(self, '_jq_ins_dialog') and self._jq_ins_dialog:
            self._jq_ins_dialog.open = False
            self.page.update()

    def _confirm_journal_insert_quarter(self):
        self._close_jq_ins_dialog()
        params = self._current_journal_params

        self.journal_insert_quarter_btn.disabled = True
        self.journal_delete_quarter_btn.disabled = True
        self.journal_clear_btn.disabled = True
        self._log_message("Вставка четвертных оценок в журнал...")
        self.page.update()

        def run():
            try:
                # Wait for API sync
                time.sleep(1)

                # Fetch fresh students data
                students = self.api.get_journal_students(
                    group_id=params["group_id"],
                    subject_id=params["subject_id"],
                    quarter_property_id=params["qprop_id"],
                )

                if not students:
                    self._log_message("Нет студентов в журнале")
                    return

                inserted = 0
                skipped = 0
                failed = 0

                for s in students:
                    student_id = s["studentId"]
                    student_name = f"{s.get('lastName', '')} {s.get('firstName', '')}"

                    # Check if quarter mark already exists
                    quarter_marks = s.get("quarterMark", [])
                    if quarter_marks and quarter_marks[0].get("shortName"):
                        skipped += 1
                        continue

                    # Calculate ceil(average)
                    grade_values = []
                    for m in (s.get("subjectMarks") or []):
                        sn = m.get("shortName", "")
                        if sn and sn.isdigit():
                            v = int(sn)
                            if MIN_GRADE <= v <= MAX_GRADE:
                                grade_values.append(v)

                    if not grade_values:
                        self._log_message(f"  ⏭️ {student_name}: нет оценок, пропущен")
                        skipped += 1
                        continue

                    avg = sum(grade_values) / len(grade_values)
                    grade = min(max(int(math.ceil(avg)), MIN_GRADE), MAX_GRADE)
                    self._log_message(f"  📊 {student_name}: ср.={avg:.2f} → Чтв={grade}")

                    try:
                        result = self.api.create_quarter_mark(
                            student_id=student_id,
                            quarter_property_id=params["qprop_id"],
                            mark=grade,
                            subject_id=params["subject_id"],
                            curriculum_property_id=params.get("curriculum_property_id", 0),
                        )
                        if result and not (isinstance(result, dict) and result.get("error")):
                            inserted += 1
                        else:
                            failed += 1
                            self._log_message(f"  ❌ {student_name}: {result}", "error")
                    except Exception as e:
                        failed += 1
                        self._log_message(f"  ❌ {student_name}: {e}", "error")

                    time.sleep(0.15)

                self._log_message(f"Четвертные: ✅ {inserted} вставлено, ⏭️ {skipped} пропущено, ❌ {failed} ошибок")
            except Exception as e:
                self._log_message(f"Ошибка вставки четвертных: {e}", "error")
            finally:
                self.journal_insert_quarter_btn.disabled = False
                self.journal_delete_quarter_btn.disabled = False
                self.journal_clear_btn.disabled = False
                # Reload journal to reflect changes
                self._reload_journal()
                try:
                    self.page.run_thread(self._safe_update)
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _on_journal_delete_quarter(self):
        """Delete ONLY quarter marks for the currently loaded journal."""
        if not self._journal_loaded or not self._current_journal_params:
            self._show_snackbar("Сначала загрузите журнал!")
            return

        # Confirmation dialog
        self._jq_del_dialog = AlertDialog(
            modal=True,
            title=Text("Удаление четвертных оценок", weight=FontWeight.W_700),
            content=Text(
                "Удалить ТОЛЬКО четвертные оценки\n"
                "из текущего журнала?\n\n"
                "Обычные оценки НЕ будут затронуты.",
                size=15,
            ),
            actions=[
                TextButton(
                    content=Text("Отмена", size=15),
                    on_click=lambda _: self._close_jq_del_dialog(),
                ),
                FilledButton(
                    content=ft.Text("Удалить четвертные", size=15, weight=FontWeight.W_600),
                    style=ButtonStyle(bgcolor=ft.Colors.ORANGE_600),
                    on_click=lambda _: self._confirm_journal_delete_quarter(),
                ),
            ],
        )
        self.page.overlay.append(self._jq_del_dialog)
        self._jq_del_dialog.open = True
        self.page.update()

    def _close_jq_del_dialog(self):
        if hasattr(self, '_jq_del_dialog') and self._jq_del_dialog:
            self._jq_del_dialog.open = False
            self.page.update()

    def _confirm_journal_delete_quarter(self):
        self._close_jq_del_dialog()
        params = self._current_journal_params

        self.journal_delete_quarter_btn.disabled = True
        self.journal_insert_quarter_btn.disabled = True
        self.journal_clear_btn.disabled = True
        self._log_message("Удаление четвертных оценок из журнала...")
        self.page.update()

        def run():
            try:
                # Fetch fresh students data
                students = self.api.get_journal_students(
                    group_id=params["group_id"],
                    subject_id=params["subject_id"],
                    quarter_property_id=params["qprop_id"],
                )

                if not students:
                    self._log_message("Нет студентов в журнале")
                    return

                deleted = 0
                failed = 0
                found = 0

                for s in students:
                    student_id = s["studentId"]
                    student_name = f"{s.get('lastName', '')} {s.get('firstName', '')}"
                    quarter_marks = s.get("quarterMark") or []
                    for qm in quarter_marks:
                        qm_id = qm.get("quarterMarkId") or qm.get("assignmentMarkId") or qm.get("id")
                        qm_val = qm.get("shortName", "")
                        if qm_id:
                            found += 1
                            try:
                                self.api.delete_quarter_mark(
                                    quarter_mark_id=qm_id,
                                    student_id=student_id,
                                    quarter_property_id=params.get("qprop_id"),
                                    subject_id=params.get("subject_id"),
                                    curriculum_property_id=params.get("curriculum_property_id", 0),
                                )
                                deleted += 1
                                self._log_message(f"  🗑️ {student_name}: четвертная {qm_val or '?'} удалена (id={qm_id})")
                            except Exception as e:
                                failed += 1
                                self._log_message(f"  ❌ {student_name}: {e}", "error")
                            time.sleep(0.15)

                if found == 0:
                    self._log_message("Четвертные оценки не найдены")
                else:
                    self._log_message(f"Удаление четвертных: ✅ {deleted} удалено, ❌ {failed} ошибок (найдено: {found})")
            except Exception as e:
                self._log_message(f"Ошибка удаления четвертных: {e}", "error")
            finally:
                self.journal_delete_quarter_btn.disabled = False
                self.journal_insert_quarter_btn.disabled = False
                self.journal_clear_btn.disabled = False
                # Reload journal to reflect changes
                self._reload_journal()
                try:
                    self.page.run_thread(self._safe_update)
                except Exception:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, plan: GradePlan):
        """Called from engine worker threads — update UI safely via Flet thread."""
        total = plan.total_tasks - plan.skipped
        if total > 0:
            done = plan.completed + plan.failed
            pct = done / total
            self.progress_bar.value = pct
            self.progress_pct.value = f"{pct * 100:.0f}%"
            self.progress_label.value = f"Прогресс: {done}/{total}"
            self.stats_label.value = f"Успешно: {plan.completed}  |  Ошибки: {plan.failed}  |  Пропущено: {plan.skipped}"
        else:
            self.progress_bar.value = 1.0
            self.progress_pct.value = "100%"
            self.progress_pct.color = ft.Colors.ORANGE_600
            self.progress_label.value = "Все ячейки уже заполнены"
            self.stats_label.value = f"Пропущено: {plan.skipped} — снимите 'Только пустые' для перезаписи"
        try:
            self.page.run_thread(self._safe_update)
        except Exception:
            pass

    def _on_log(self, message: str, level: str = "info"):
        """Called from engine worker threads — schedule log on Flet thread."""
        self.page.run_thread(lambda: self._log_message(message, level))

    # ════════════════════════════════════════════════════════════════
    #  DELETE GRADES
    # ════════════════════════════════════════════════════════════════

    def _on_delete_grades(self):
        """Delete all grades for selected group/subject/quarter with confirmation."""
        groups = self._get_selected_groups()
        subjects = self._get_selected_subjects()
        quarters = self._get_selected_quarters()

        if not groups or not subjects or not quarters:
            self._show_snackbar("Выберите класс, предмет и четверть!")
            return

        # Show confirmation dialog
        self._confirm_dialog = AlertDialog(
            modal=True,
            title=Text("⚠️ Удаление оценок", weight=FontWeight.W_700),
            content=Text(
                "Вы уверены, что хотите удалить ВСЕ оценки\n"
                "для выбранных класса, предмета и четверти?\n\n"
                "Это действие нельзя отменить!",
                size=15,
            ),
            actions=[
                TextButton(
                    content=Text("Отмена", size=15),
                    on_click=lambda _: self._close_confirm_dialog(),
                ),
                FilledButton(
                    content=ft.Text("Удалить", size=15, weight=FontWeight.W_600),
                    style=ButtonStyle(bgcolor=ft.Colors.RED_600),
                    on_click=lambda _: self._confirm_delete(),
                ),
            ],
        )
        self.page.overlay.append(self._confirm_dialog)
        self._confirm_dialog.open = True
        self.page.update()

    def _close_confirm_dialog(self):
        if hasattr(self, '_confirm_dialog') and self._confirm_dialog:
            self._confirm_dialog.open = False
            self.page.update()

    def _confirm_delete(self):
        self._close_confirm_dialog()
        groups = self._get_selected_groups()
        subjects = self._get_selected_subjects()
        quarters = self._get_selected_quarters()

        self.delete_btn.disabled = True
        self.start_btn.disabled = True
        self.analyze_btn.disabled = True
        self.signature_btn.disabled = True
        self.stop_btn.disabled = False
        self.progress_label.value = "Удаление оценок..."
        self.progress_pct.value = "0%"
        self.progress_pct.color = ft.Colors.RED_600
        self.page.update()

        def run():
            try:
                self.engine.execute_delete_marks(
                    groups=groups,
                    subjects=subjects,
                    quarters=quarters,
                )
            except Exception as e:
                self._log_message(f"Ошибка удаления: {e}", "error")
            finally:
                self._on_delete_complete()

        threading.Thread(target=run, daemon=True).start()

    def _on_delete_complete(self):
        self.delete_btn.disabled = False
        self.start_btn.disabled = False
        self.stop_btn.disabled = True
        self.analyze_btn.disabled = False
        self.signature_btn.disabled = False
        self.progress_pct.color = ft.Colors.BLUE_600
        self.progress_label.value = "Удаление завершено"
        self.page.run_thread(self._safe_update)

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

    def _safe_update(self):
        """Thread-safe page update helper — safe to call from any thread."""
        try:
            self.page.update()
        except Exception:
            pass

    def _on_save_journal(self):
        """Save all modified grades in the journal (Ctrl+S)."""
        if not self._journal_loaded:
            self._show_snackbar("Сначала загрузите журнал!")
            return

        # Find all cells that have been modified but not yet saved
        modified_cells = []
        for (row, col), data in self._grade_data.items():
            cell = self._grade_cells.get((row, col))
            if not cell:
                continue
            cell_value = cell.value or ""
            current_saved = data.get("current_value", "")
            # Check if the cell value differs from the saved value
            if cell_value.strip() and cell_value.strip().isdigit():
                grade = int(cell_value.strip())
                if MIN_GRADE <= grade <= MAX_GRADE and str(grade) != current_saved:
                    modified_cells.append((row, col, grade))

        if not modified_cells:
            # Also try the currently selected cell
            if self._selected_cell:
                row, col = self._selected_cell
                cell = self._grade_cells.get((row, col))
                if cell:
                    val = cell.value
                    if val and val.strip() and val.strip().isdigit():
                        grade = int(val.strip())
                        if MIN_GRADE <= grade <= MAX_GRADE:
                            self._set_cell_grade(row, col, grade)
                            self._show_snackbar(f"Оценка {grade} сохранена")
                            return
            self._show_snackbar("Нет изменений для сохранения")
            return

        # Save all modified cells
        self._show_snackbar(f"Сохранение {len(modified_cells)} оценок...")
        for row, col, grade in modified_cells:
            self._set_cell_grade(row, col, grade)
            time.sleep(0.15)  # Small delay between saves to avoid API rate limiting

    def _show_snackbar(self, message: str):
        try:
            snack = SnackBar(content=Text(message, size=15), open=True)
            self.page.overlay.append(snack)
            self.page.update()
            # Clean up old snackbars after a delay to avoid overlay accumulation
            def cleanup():
                time.sleep(3)
                try:
                    if snack in self.page.overlay:
                        self.page.overlay.remove(snack)
                        self.page.update()
                except Exception:
                    pass
            threading.Thread(target=cleanup, daemon=True).start()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def main(page: Page):
    EdonishAutoApp(page)


if __name__ == "__main__":
    ft.run(main)
