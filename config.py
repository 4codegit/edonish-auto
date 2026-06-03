"""Configuration for Edonish Auto"""
import os

# API Configuration
API_BASE = "https://api.edonish.tj"
API_LOGIN = f"{API_BASE}/auth/v1/login"
API_REFRESH = f"{API_BASE}/auth/v1/refresh_token"
API_HEADER_INFO = f"{API_BASE}/auth/v1/header/info"

# Role-based API prefixes
API_PREFIXES = {
    "teacher": "/teacher/v1",
    "classroom-teacher": "/teacher/v1",
    "school_admin": "/school_admin/v1",
    "director": "/director/v1",
    "headteacher": "/headteacher/v1",
    "chief_curator": "/chief_curator/v1",
    "regional_curator": "/regional_curator/v1",
    "parent": "/parent/v1",
    "student": "/student/v1",
}

# Journal API endpoints (relative to role prefix)
JOURNAL_OPTIONS = "/journal"
JOURNAL_DATES = "/journal/dates"
JOURNAL_STUDENTS = "/journal/students"
JOURNAL_STUDENTS_FINAL = "/journal/students/final"
JOURNAL_DATES_FINAL = "/journal/dates/final"
JOURNAL_MARK_CREATE = "/journal/10_point_mark/create"
JOURNAL_MARK_DELETE = "/journal/mark/delete"
JOURNAL_QUARTER_DELETE = "/journal/10_point_quarter_mark/delete"
JOURNAL_QUARTER_CREATE = "/journal/10_point_quarter_mark/create"
JOURNAL_SEMESTER_CREATE = "/journal/10_point_semester/create"
JOURNAL_YEAR_CREATE = "/journal/10_point_year/create"
JOURNAL_COMMENT = "/journal/comment"
JOURNAL_ASSIGNMENT_UPDATE = "/journal/assignment/update"

# Other endpoints
GROUPS_LIST = "/groups/list"
PERIOD_QUARTERS = "/period/quaters"
TEACHER_SUBJECT = "/teacher/subject"
SCHOOL_SUBJECTS = "/school/subjects"
SUBGROUPS = "/subgroups"

# Language codes
LANG_TJ = 1  # Тоҷикӣ
LANG_RU = 2  # Русский
LANG_EN = 3  # English

# Grade settings
MIN_GRADE = 3
MAX_GRADE = 10
DEFAULT_GRADE_RANGE = (3, 10)

# Worker settings
DEFAULT_WORKERS = 4
DEFAULT_BATCH_SIZE = 4

# App settings
APP_NAME = "eDonish Auto"
APP_VERSION = "3.21.0"
APP_AUTHOR = "Edonish Auto Team"

# Session file
SESSION_FILE = os.path.join(os.path.expanduser("~"), ".edonish_session.json")

# Colors
COLOR_PRIMARY = "#1a73e8"
COLOR_SUCCESS = "#34a853"
COLOR_WARNING = "#fbbc04"
COLOR_ERROR = "#ea4335"
COLOR_BG = "#ffffff"
COLOR_BG_DARK = "#1a1a2e"
COLOR_TEXT = "#333333"
COLOR_TEXT_LIGHT = "#ffffff"
