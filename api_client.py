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
    TEACHER_SUBJECT, SUBGROUPS, JOURNAL_ASSIGNMENT_UPDATE,
    LANG_RU, MIN_GRADE, MAX_GRADE
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
        mark_type_id: int = None,
        quarter_property_id: int = None,
    ) -> Optional[Dict]:
        """Create a mark for a student on a specific date.

        In the edonish 10-point system, mark_type_id is the ID from the
        marks_ten_point reference table where ID equals the mark value.
        So mark_type_id MUST match the grade value (3-10).
        """
        # In 10-point system, mark_type_id = mark value (not a fixed type code)
        if mark_type_id is None:
            mark_type_id = mark
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
        """Delete a regular journal mark by its ID."""
        mid = str(mark_id) if mark_id else ""
        attempts = [
            ("POST", {"mark_id": mid}, {"school_id": self.school_id}, "POST body mark_id"),
            ("DELETE", {"mark_id": mid}, {"school_id": self.school_id}, "DELETE body mark_id"),
            ("POST", {"id": mid}, {"school_id": self.school_id}, "POST body id"),
            ("DELETE", {"id": mid}, {"school_id": self.school_id}, "DELETE body id"),
            ("POST", None, {"mark_id": mid, "school_id": self.school_id}, "POST query mark_id"),
            ("DELETE", None, {"mark_id": mid, "school_id": self.school_id}, "DELETE query mark_id"),
        ]
        first_conflict = None
        last_error = None

        for method, json_body, params, desc in attempts:
            try:
                kwargs = {"params": params}
                if json_body is not None:
                    kwargs["json"] = json_body
                result = self._request(method, self._url(JOURNAL_MARK_DELETE), **kwargs)
                logger.info(f"delete_mark: succeeded via {desc}")
                return result
            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code if e.response is not None else None
                if status_code == 409:
                    first_conflict = first_conflict or e
                    logger.info(f"delete_mark: conflict via {desc} for mark_id={mid}")
                    continue
                logger.info(f"delete_mark: attempt {desc} failed: {e}")
            except Exception as e:
                last_error = e
                logger.info(f"delete_mark: attempt {desc} failed: {e}")

        if first_conflict is not None:
            raise MarkDeleteConflict(
                f"Оценку нельзя удалить через API сейчас (409 Conflict, id={mid})"
            ) from first_conflict
        if last_error is not None:
            raise last_error
        return None

    def delete_quarter_mark(
        self,
        quarter_mark_id,
        student_id: int = None,
        quarter_property_id: int = None,
        subject_id: int = None,
        curriculum_property_id: int = None,
    ) -> Optional[Dict]:
        """Delete a quarter (четвертная) mark.

        The edonish.tj API may require full context for deleting quarter marks.
        We try multiple HTTP methods, endpoints, and body formats.
        Each attempt is logged so we can identify which one works.
        """
        qmid = str(quarter_mark_id) if quarter_mark_id else ""

        # Build the full body matching the create format
        full_body = {}
        if student_id is not None:
            full_body["group_subgroup_student_id"] = student_id
        if quarter_property_id is not None:
            full_body["quarter_property_id"] = quarter_property_id
        if subject_id is not None:
            full_body["subject_id"] = subject_id
        if curriculum_property_id is not None:
            full_body["curriculum_property_id"] = curriculum_property_id

        attempts = []

        # ── Dedicated quarter-mark endpoint (/journal/10_point_quarter_mark/delete) ──
        if full_body:
            attempts.append(("POST", JOURNAL_QUARTER_DELETE, {**full_body, "quarter_mark_id": qmid}, None,
                             "1: POST quarter-delete + full body + quarter_mark_id"))
            attempts.append(("POST", JOURNAL_QUARTER_DELETE, {**full_body, "mark_id": qmid}, None,
                             "2: POST quarter-delete + full body + mark_id"))
            attempts.append(("DELETE", JOURNAL_QUARTER_DELETE, {**full_body, "quarter_mark_id": qmid}, None,
                             "3: DELETE quarter-delete + full body + quarter_mark_id"))
            attempts.append(("DELETE", JOURNAL_QUARTER_DELETE, {**full_body, "mark_id": qmid}, None,
                             "4: DELETE quarter-delete + full body + mark_id"))
        attempts.append(("POST", JOURNAL_QUARTER_DELETE, {"quarter_mark_id": qmid}, None,
                         "5: POST quarter-delete + quarter_mark_id only"))
        attempts.append(("POST", JOURNAL_QUARTER_DELETE, {"mark_id": qmid}, None,
                         "6: POST quarter-delete + mark_id only"))
        attempts.append(("DELETE", JOURNAL_QUARTER_DELETE, {"quarter_mark_id": qmid}, None,
                         "7: DELETE quarter-delete + quarter_mark_id only"))
        attempts.append(("DELETE", JOURNAL_QUARTER_DELETE, {"mark_id": qmid}, None,
                         "8: DELETE quarter-delete + mark_id only"))
        # With query params
        attempts.append(("POST", JOURNAL_QUARTER_DELETE, None, {"quarter_mark_id": qmid, "school_id": self.school_id},
                         "9: POST quarter-delete + query params"))
        attempts.append(("DELETE", JOURNAL_QUARTER_DELETE, None, {"quarter_mark_id": qmid, "school_id": self.school_id},
                         "10: DELETE quarter-delete + query params"))

        # ── Generic mark-delete endpoint (/journal/mark/delete) ──
        if full_body:
            attempts.append(("POST", JOURNAL_MARK_DELETE, {**full_body, "mark_id": qmid}, None,
                             "11: POST mark-delete + full body + mark_id"))
            attempts.append(("DELETE", JOURNAL_MARK_DELETE, {**full_body, "mark_id": qmid}, None,
                             "12: DELETE mark-delete + full body + mark_id"))
        attempts.append(("POST", JOURNAL_MARK_DELETE, {"mark_id": qmid}, None,
                         "13: POST mark-delete + mark_id body"))
        attempts.append(("DELETE", JOURNAL_MARK_DELETE, {"mark_id": qmid}, None,
                         "14: DELETE mark-delete + mark_id body"))
        attempts.append(("POST", JOURNAL_MARK_DELETE, None, {"mark_id": qmid, "school_id": self.school_id},
                         "15: POST mark-delete + query params"))
        attempts.append(("DELETE", JOURNAL_MARK_DELETE, None, {"mark_id": qmid, "school_id": self.school_id},
                         "16: DELETE mark-delete + query params"))

        for method, endpoint, json_body, query_params, desc in attempts:
            try:
                kwargs = {"params": {"school_id": self.school_id}}
                if query_params:
                    kwargs["params"].update(query_params)
                if json_body:
                    kwargs["json"] = json_body
                result = self._request(method, self._url(endpoint), **kwargs)
                if result is not None:
                    logger.info(f"delete_quarter_mark: ✅ succeeded via attempt {desc}")
                    return result
            except Exception as e:
                logger.info(f"delete_quarter_mark: attempt {desc} → {e}")

        logger.warning(f"delete_quarter_mark: ❌ ALL 16 attempts failed for qmid={qmid}")
        raise Exception(f"Не удалось удалить четвертную оценку (все 16 попыток неуспешны, id={qmid})")

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

    def update_assignment(
        self,
        assignment_date_id: str,
        assignment: str,
        quarter_property_id: int = None,
    ) -> Optional[Dict]:
        """Update the topic/assignment text for a date column in the journal."""
        body = {
            "schedule_date_id": assignment_date_id,
            "assignment": assignment,
            "quarter_property_id": quarter_property_id or 0,
        }
        return self._request(
            "POST",
            self._url(JOURNAL_ASSIGNMENT_UPDATE),
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


class MarkDeleteConflict(APIError):
    """Raised when the API refuses to delete a mark with HTTP 409."""
    pass
