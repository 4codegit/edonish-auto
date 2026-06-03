"""Edonish API Client - handles all API communication"""
import requests
import json
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from config import (
    API_BASE, API_LOGIN, API_REFRESH, API_HEADER_INFO,
    API_PREFIXES, JOURNAL_OPTIONS, JOURNAL_DATES, JOURNAL_STUDENTS,
    JOURNAL_MARK_CREATE, JOURNAL_MARK_DELETE, JOURNAL_QUARTER_DELETE,
    JOURNAL_QUARTER_CREATE, JOURNAL_SEMESTER_CREATE, JOURNAL_YEAR_CREATE,
    JOURNAL_DATES_FINAL, JOURNAL_STUDENTS_FINAL, GROUPS_LIST, PERIOD_QUARTERS,
    TEACHER_SUBJECT, SUBGROUPS, LANG_RU, MIN_GRADE, MAX_GRADE
)

logger = logging.getLogger("edonish_auto")


class EdonishAPI:
    """Client for the eDonish API - handles authentication and data operations."""

    def __init__(self):
        self.session = requests.Session()
        self.jwt_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_info: Optional[Dict] = None
        self.school_id: Optional[int] = None
        self.role: Optional[str] = None
        self.role_prefix: Optional[str] = None
        self.uid: Optional[str] = None

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json",
        }

    def _url(self, endpoint: str, use_role_prefix: bool = True) -> str:
        prefix = self.role_prefix if use_role_prefix else ""
        return f"{API_BASE}{prefix}{endpoint}"

    def login(self, login_id: str, password: str) -> Dict[str, Any]:
        """Authenticate with the eDonish API."""
        try:
            resp = self.session.post(
                API_LOGIN,
                json={"login": login_id, "password": password},
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status_code") != 0:
                raise AuthenticationError(
                    f"Login failed: status_code={data.get('status_code')}"
                )

            self.jwt_token = data["jwt_token"]
            self.refresh_token = data["refresh_token"]
            self.uid = data["uid"]

            # Get user roles and school info
            self.user_info = {
                "uid": data["uid"],
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
                "roles": data.get("roles", []),
            }

            # Determine role and get school_id
            self._resolve_role_and_school()

            logger.info(
                f"Logged in as {self.user_info['last_name']} {self.user_info['first_name']} "
                f"(role: {self.role}, school: {self.school_id})"
            )
            return self.user_info

        except requests.exceptions.RequestException as e:
            raise AuthenticationError(f"Network error during login: {e}")

    def _resolve_role_and_school(self):
        """Determine user role and school ID from header info."""
        try:
            resp = self.session.get(
                API_HEADER_INFO,
                params={"lang": LANG_RU},
                headers=self._headers,
                timeout=10,
            )
            resp.raise_for_status()
            roles_data = resp.json()

            if isinstance(roles_data, list) and len(roles_data) > 0:
                primary = roles_data[0]
                self.school_id = primary.get("schoolId")
                self.role = primary.get("name", "teacher")
                self.role_prefix = API_PREFIXES.get(self.role, "/teacher/v1")

                # If user has multiple roles, prefer teacher or classroom-teacher
                for r in roles_data:
                    if r.get("name") in ("teacher", "classroom-teacher"):
                        self.role = r.get("name")
                        self.role_prefix = API_PREFIXES.get(self.role, "/teacher/v1")
                        self.school_id = r.get("schoolId", self.school_id)
                        break
            else:
                self.role = "teacher"
                self.role_prefix = API_PREFIXES["teacher"]

        except Exception as e:
            logger.warning(f"Could not resolve role: {e}")
            self.role = "teacher"
            self.role_prefix = API_PREFIXES["teacher"]

    def _refresh_auth(self) -> bool:
        """Refresh the JWT token using the refresh token."""
        if not self.refresh_token:
            return False
        try:
            resp = self.session.get(
                API_REFRESH,
                headers={"Authorization": f"Bearer {self.refresh_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.jwt_token = data["jwt_token"]
                self.refresh_token = data["refresh_token"]
                return True
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
        return False

    def _request(self, method: str, url: str, **kwargs) -> Any:
        """Make an authenticated API request with auto-refresh."""
        kwargs.setdefault("headers", self._headers)
        kwargs.setdefault("timeout", 15)

        resp = self.session.request(method, url, **kwargs)

        if resp.status_code == 403:
            # Try refreshing token
            if self._refresh_auth():
                kwargs["headers"] = self._headers
                resp = self.session.request(method, url, **kwargs)

        if resp.status_code == 404:
            return None

        resp.raise_for_status()
        return resp.json()

    def get_journal_options(self, lang: int = LANG_RU) -> List[Dict]:
        """Get available classes, subjects, and subgroups for the teacher."""
        return self._request(
            "OPTIONS",
            self._url(JOURNAL_OPTIONS),
            params={"lang": lang, "school_id": self.school_id},
        )

    def get_groups(self, lang: int = LANG_RU) -> List[Dict]:
        """Get all groups/classes in the school."""
        return self._request(
            "GET",
            self._url(GROUPS_LIST, use_role_prefix=False),
            params={"school_id": self.school_id, "lang": lang},
        )

    def get_quarters(self, school_id: int = None, rank_id: int = 2, lang: int = LANG_RU) -> List[Dict]:
        """Get quarter periods for the school (uses school_admin prefix)."""
        result = self._request(
            "GET",
            f"{API_BASE}/school_admin/v1{PERIOD_QUARTERS}",
            params={
                "school_id": school_id or self.school_id,
                "rank_id": rank_id,
                "lang": lang,
            },
        )
        return result if result else []

    def get_journal_dates(
        self, group_id: int, subject_id: int, quarter_property_id: int, lang: int = LANG_RU
    ) -> List[Dict]:
        """Get dates for a specific group/subject/quarter."""
        return self._request(
            "GET",
            self._url(JOURNAL_DATES),
            params={
                "group_id": group_id,
                "subject_id": subject_id,
                "quarter_property_id": quarter_property_id,
                "school_id": self.school_id,
                "lang": lang,
            },
        )

    def get_journal_students(
        self, group_id: int, subject_id: int, quarter_property_id: int, lang: int = LANG_RU
    ) -> List[Dict]:
        """Get students with their marks for a specific group/subject/quarter."""
        result = self._request(
            "GET",
            self._url(JOURNAL_STUDENTS),
            params={
                "group_id": group_id,
                "subject_id": subject_id,
                "quarter_property_id": quarter_property_id,
                "school_id": self.school_id,
                "lang": lang,
            },
        )
        # Debug: log what keys the first student has (for diagnosing mark detection)
        if result and isinstance(result, list) and len(result) > 0:
            first = result[0]
            mark_keys = [k for k in first.keys() if 'mark' in k.lower() or 'Mark' in k]
            total_marks = sum(len(first.get(k, []) or []) for k in mark_keys)
            logger.debug(f"get_journal_students: {len(result)} students, mark_keys={mark_keys}, first_student_marks={total_marks}")
        return result

    def get_journal_dates_final(
        self, group_id: int, curriculum_property_id: int, lang: int = LANG_RU
    ) -> List[Dict]:
        """Get final dates for a group."""
        return self._request(
            "GET",
            self._url(JOURNAL_DATES_FINAL),
            params={
                "group_id": group_id,
                "curriculum_property_id": curriculum_property_id,
                "school_id": self.school_id,
                "lang": lang,
            },
        )

    def create_mark(
        self,
        student_id: int,
        assignment_date_id: str,
        mark: int,
        mark_type_id: int = 8,
        quarter_property_id: int = None,
    ) -> Optional[Dict]:
        """Create a mark for a student on a specific date."""
        body = {
            "mark_type_id": mark_type_id,
            "group_subgroup_student_id": student_id,
            "schedule_date_id": assignment_date_id,
            "quarter_property_id": quarter_property_id or 0,
            "mark": mark,
        }
        return self._request(
            "POST",
            self._url(JOURNAL_MARK_CREATE),
            params={"school_id": self.school_id, "lang": LANG_RU},
            json=body,
        )

    def delete_mark(self, mark_id: str) -> Optional[Dict]:
        """Delete a mark by its ID."""
        # Try with JSON body first (some API versions require it)
        try:
            return self._request(
                "POST",
                self._url(JOURNAL_MARK_DELETE),
                params={"school_id": self.school_id},
                json={"mark_id": mark_id},
            )
        except Exception:
            # Fallback to query params
            return self._request(
                "POST",
                self._url(JOURNAL_MARK_DELETE),
                params={"mark_id": mark_id, "school_id": self.school_id},
            )

    def delete_quarter_mark(
        self,
        quarter_mark_id,
        student_id: int = None,
        quarter_property_id: int = None,
        subject_id: int = None,
        curriculum_property_id: int = None,
    ) -> Optional[Dict]:
        """Delete a quarter (четвертная) mark.

        The edonish.tj API requires full context (student_id, quarter_property_id,
        subject_id, curriculum_property_id) for deleting quarter marks, not just
        the mark_id. We try the dedicated quarter-mark endpoint first, then
        fall back to the generic mark-delete endpoint.
        """
        # Ensure string type
        qmid = str(quarter_mark_id) if quarter_mark_id else ""

        # Build the full body matching the create format (but with quarter_mark_id)
        full_body = {}
        if student_id is not None:
            full_body["group_subgroup_student_id"] = student_id
        if quarter_property_id is not None:
            full_body["quarter_property_id"] = quarter_property_id
        if subject_id is not None:
            full_body["subject_id"] = subject_id
        if curriculum_property_id is not None:
            full_body["curriculum_property_id"] = curriculum_property_id

        # ── Attempt 1: dedicated quarter-mark endpoint with full body + quarter_mark_id ──
        if full_body:
            body1 = {**full_body, "quarter_mark_id": qmid}
            try:
                result = self._request(
                    "POST",
                    self._url(JOURNAL_QUARTER_DELETE),
                    params={"school_id": self.school_id},
                    json=body1,
                )
                if result is not None:
                    logger.info(f"delete_quarter_mark: succeeded via attempt 1 (full body + quarter_mark_id)")
                    return result
            except Exception as e:
                logger.debug(f"delete_quarter_mark: attempt 1 failed: {e}")

        # ── Attempt 2: dedicated endpoint with full body + mark_id key ──
        if full_body:
            body2 = {**full_body, "mark_id": qmid}
            try:
                result = self._request(
                    "POST",
                    self._url(JOURNAL_QUARTER_DELETE),
                    params={"school_id": self.school_id},
                    json=body2,
                )
                if result is not None:
                    logger.info(f"delete_quarter_mark: succeeded via attempt 2 (full body + mark_id)")
                    return result
            except Exception as e:
                logger.debug(f"delete_quarter_mark: attempt 2 failed: {e}")

        # ── Attempt 3: dedicated endpoint, only quarter_mark_id in body ──
        try:
            result = self._request(
                "POST",
                self._url(JOURNAL_QUARTER_DELETE),
                params={"school_id": self.school_id},
                json={"quarter_mark_id": qmid},
            )
            if result is not None:
                logger.info(f"delete_quarter_mark: succeeded via attempt 3 (quarter_mark_id only)")
                return result
        except Exception as e:
            logger.debug(f"delete_quarter_mark: attempt 3 failed: {e}")

        # ── Attempt 4: dedicated endpoint with mark_id key in body ──
        try:
            result = self._request(
                "POST",
                self._url(JOURNAL_QUARTER_DELETE),
                params={"school_id": self.school_id},
                json={"mark_id": qmid},
            )
            if result is not None:
                logger.info(f"delete_quarter_mark: succeeded via attempt 4 (mark_id only)")
                return result
        except Exception as e:
            logger.debug(f"delete_quarter_mark: attempt 4 failed: {e}")

        # ── Attempt 5: generic mark delete with full body ──
        if full_body:
            body5 = {**full_body, "mark_id": qmid}
            try:
                result = self._request(
                    "POST",
                    self._url(JOURNAL_MARK_DELETE),
                    params={"school_id": self.school_id},
                    json=body5,
                )
                if result is not None:
                    logger.info(f"delete_quarter_mark: succeeded via attempt 5 (generic + full body)")
                    return result
            except Exception as e:
                logger.debug(f"delete_quarter_mark: attempt 5 failed: {e}")

        # ── Attempt 6: generic mark delete with mark_id in JSON body ──
        try:
            result = self._request(
                "POST",
                self._url(JOURNAL_MARK_DELETE),
                params={"school_id": self.school_id},
                json={"mark_id": qmid},
            )
            if result is not None:
                logger.info(f"delete_quarter_mark: succeeded via attempt 6 (generic + mark_id body)")
                return result
        except Exception as e:
            logger.debug(f"delete_quarter_mark: attempt 6 failed: {e}")

        # ── Attempt 7: generic endpoint via query params ──
        try:
            result = self._request(
                "POST",
                self._url(JOURNAL_MARK_DELETE),
                params={"mark_id": qmid, "school_id": self.school_id},
            )
            if result is not None:
                logger.info(f"delete_quarter_mark: succeeded via attempt 7 (generic + query params)")
                return result
        except Exception as e:
            logger.warning(f"delete_quarter_mark: all attempts failed for quarter_mark_id={qmid}: {e}")
            raise

    def create_quarter_mark(
        self, student_id: int, quarter_property_id: int, mark: int,
        subject_id: int = 0, curriculum_property_id: int = 0,
    ) -> Optional[Dict]:
        """Create a quarter (четвертная) mark."""
        # mark_id is the ID from marks_ten_point matching the mark value
        mark_id = mark  # For 10-point system, mark_id equals the mark value
        body = {
            "group_subgroup_student_id": student_id,
            "quarter_property_id": quarter_property_id,
            "mark": mark,
            "mark_id": mark_id,
            "subject_id": subject_id,
            "curriculum_property_id": curriculum_property_id,
        }
        return self._request(
            "POST",
            self._url(JOURNAL_QUARTER_CREATE),
            params={"school_id": self.school_id},
            json=body,
        )

    def create_semester_mark(
        self, student_id: int, semester_property_id: int, mark: int
    ) -> Optional[Dict]:
        """Create a semester (полугодовая) mark."""
        body = {
            "group_subgroup_student_id": student_id,
            "semester_property_id": semester_property_id,
            "mark": mark,
        }
        return self._request(
            "POST",
            self._url(JOURNAL_SEMESTER_CREATE),
            params={"school_id": self.school_id},
            json=body,
        )

    def create_year_mark(
        self, student_id: int, year_property_id: int, mark: int
    ) -> Optional[Dict]:
        """Create a year (годовая) mark."""
        body = {
            "group_subgroup_student_id": student_id,
            "year_property_id": year_property_id,
            "mark": mark,
        }
        return self._request(
            "POST",
            self._url(JOURNAL_YEAR_CREATE),
            params={"school_id": self.school_id},
            json=body,
        )

    def get_teacher_subjects(self, lang: int = LANG_RU) -> List[Dict]:
        """Get all subjects for teachers in the school."""
        return self._request(
            "GET",
            self._url(TEACHER_SUBJECT, use_role_prefix=False),
            params={"school_id": self.school_id, "lang": lang},
        )

    def create_comment(
        self,
        student_id: int,
        assignment_date_id: str,
        comment: str,
        quarter_property_id: int = None,
    ) -> Optional[Dict]:
        """Create a comment/signature for a student on a specific date."""
        body = {
            "group_subgroup_student_id": student_id,
            "schedule_date_id": assignment_date_id,
            "quarter_property_id": quarter_property_id or 0,
            "comment": comment,
        }
        return self._request(
            "POST",
            self._url(JOURNAL_COMMENT),
            params={"school_id": self.school_id},
            json=body,
        )

    def get_subgroups(self, group_id: int, lang: int = LANG_RU) -> List[Dict]:
        """Get subgroups for a specific group."""
        return self._request(
            "GET",
            self._url(SUBGROUPS, use_role_prefix=False),
            params={"school_id": self.school_id, "group_id": group_id, "lang": lang},
        )


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class APIError(Exception):
    """Raised when an API call fails."""
    pass
