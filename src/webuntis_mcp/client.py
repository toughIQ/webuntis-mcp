"""WebUntis API client.

Standalone library for accessing WebUntis data via the 2017 mobile API.
Can be used independently of the MCP server:

    from webuntis_mcp.client import WebUntisClient

    client = WebUntisClient(
        server="yourschool.webuntis.com",
        school="yourschool",
        username="parent@example.com",
        secret="YOUR_QR_SECRET",
        student="ChildFirstName",
    )
    client.login()
    periods = client.get_timetable()
"""

from datetime import date, datetime, timedelta

import requests

from .auth import AuthError, make_auth, totp_login
from .config import WebUntisConfig
from .models import (
    Absence,
    Holiday,
    Homework,
    Klasse,
    Message,
    Period,
    SchoolInfo,
    TimeSlot,
    parse_absence,
    parse_holiday,
    parse_homework,
    parse_klasse,
    parse_message,
    parse_period,
    parse_timeslot,
)


class WebUntisClient:
    """Read-only client for the WebUntis API.

    Uses the 2017 mobile API (jsonrpc_intern.do) with per-request TOTP
    authentication. No session management needed.
    """

    def __init__(
        self,
        server: str | None = None,
        school: str | None = None,
        username: str | None = None,
        secret: str | None = None,
        student: str | None = None,
        config: WebUntisConfig | None = None,
    ):
        if config:
            self._server = config.server
            self._school = config.school
            self._username = config.username
            self._secret = config.secret
            self._student_name = config.student
        else:
            self._server = server or ""
            self._school = school or ""
            self._username = username or ""
            self._secret = secret or ""
            self._student_name = student or ""

        self._student_id: int | None = None
        self._school_display_name: str = ""

        self._master_data: dict | None = None
        self._lookups: dict | None = None

    @property
    def is_logged_in(self) -> bool:
        return self._student_id is not None

    @property
    def student_id(self) -> int | None:
        return self._student_id

    @property
    def school_name(self) -> str:
        return self._school_display_name or self._school

    def login(self) -> None:
        """Authenticate and resolve student ID."""
        session_info = totp_login(
            self._server, self._school, self._username, self._secret
        )
        self._school_display_name = session_info.school_name

        children = session_info.children
        if not children:
            raise AuthError("No children linked to this parent account")

        if len(children) == 1:
            child = children[0]
        else:
            child = None
            for c in children:
                if self._student_name.lower() in c.get("firstName", "").lower():
                    child = c
                    break
            if not child:
                names = [f"{c.get('firstName', '')} {c.get('lastName', '')}" for c in children]
                raise AuthError(
                    f"Student '{self._student_name}' not found. "
                    f"Available: {', '.join(names)}"
                )

        self._student_id = child["id"]

    def _ensure_login(self) -> None:
        if self._student_id is None:
            self.login()

    def _rpc_2017(self, method: str, params: dict) -> dict:
        """Call a 2017 method on jsonrpc_intern.do with per-request TOTP auth."""
        params["auth"] = make_auth(self._username, self._secret)

        url = f"https://{self._server}/WebUntis/jsonrpc_intern.do?school={self._school}"
        body = {
            "id": f"webuntis-mcp-{method}",
            "method": method,
            "params": [params],
            "jsonrpc": "2.0",
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "UntisMobileAndroid",
        }

        resp = requests.post(url, json=body, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            error = data["error"]
            code = error.get("code", 0) if isinstance(error, dict) else 0
            msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            raise RuntimeError(f"WebUntis API error ({code}): {msg}")

        return data.get("result", {})

    def _ensure_master_data(self) -> None:
        """Load masterData if not cached. Uses a minimal timetable call."""
        if self._master_data is not None:
            return
        self._ensure_login()
        today = date.today()
        result = self._rpc_2017("getTimetable2017", {
            "id": self._student_id,
            "type": "STUDENT",
            "startDate": int(today.strftime("%Y%m%d")),
            "endDate": int(today.strftime("%Y%m%d")),
            "masterDataTimestamp": 0,
            "timetableTimestamp": 0,
            "timetableTimestamps": [],
        })
        self._master_data = result.get("masterData", {})
        self._build_lookups()

    def _build_lookups(self) -> None:
        md = self._master_data or {}
        self._lookups = {
            "subjects": {s["id"]: s for s in md.get("subjects", [])},
            "teachers": {t["id"]: t for t in md.get("teachers", [])},
            "rooms": {r["id"]: r for r in md.get("rooms", [])},
            "klassen": {k["id"]: k for k in md.get("klassen", [])},
        }

    def _get_lookups(self) -> dict:
        self._ensure_master_data()
        return self._lookups or {}

    def _raw_timetable(
        self, element_id: int, element_type: str, start: date, end: date
    ) -> tuple[list[dict], dict]:
        """Fetch raw timetable + masterData via getTimetable2017."""
        self._ensure_login()
        result = self._rpc_2017("getTimetable2017", {
            "id": element_id,
            "type": element_type,
            "startDate": int(start.strftime("%Y%m%d")),
            "endDate": int(end.strftime("%Y%m%d")),
            "masterDataTimestamp": self._master_data.get("timeStamp", 0) if self._master_data else 0,
            "timetableTimestamp": 0,
            "timetableTimestamps": [],
        })

        md = result.get("masterData", {})
        if md and md.get("subjects"):
            self._master_data = md
            self._build_lookups()

        return result.get("timetable", {}).get("periods", []), self._get_lookups()

    def get_timetable(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Period]:
        """Fetch the student's timetable for a date range."""
        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = start_date + timedelta(days=4)

        raw_periods, lookups = self._raw_timetable(
            self._student_id, "STUDENT", start_date, end_date
        )
        periods = [parse_period(p, lookups) for p in raw_periods]
        return sorted(periods, key=lambda p: (p.date, p.start_time))

    def get_klassen(self) -> list[Klasse]:
        """Fetch all classes for the current school year from masterData."""
        self._ensure_master_data()
        md = self._master_data or {}
        return [parse_klasse(k) for k in md.get("klassen", [])]

    def _resolve_klasse_id_by_name(self, name: str) -> int:
        """Resolve a class name (e.g. '1g', '2a') to its WebUntis ID."""
        klassen = self.get_klassen()
        name_lower = name.lower().strip()
        for k in klassen:
            if k.name.lower() == name_lower:
                return k.id
        available = sorted(set(k.name for k in klassen))
        raise RuntimeError(
            f"Class '{name}' not found. Available: {', '.join(available)}"
        )

    def get_class_timetable(
        self,
        class_name: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Period]:
        """Fetch a class timetable. Any class, not just the student's own."""
        if class_name:
            klasse_id = self._resolve_klasse_id_by_name(class_name)
        else:
            self._ensure_master_data()
            today = date.today()
            raw_periods, lookups = self._raw_timetable(
                self._student_id, "STUDENT", today, today + timedelta(days=1)
            )
            klasse_id = None
            for p in raw_periods:
                for elem in p.get("elements", []):
                    if elem.get("type") == "CLASS":
                        klasse_id = elem.get("id")
                        break
                if klasse_id:
                    break
            if not klasse_id:
                raise RuntimeError("Could not determine class. Specify class_name.")

        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = start_date + timedelta(days=4)

        raw_periods, lookups = self._raw_timetable(
            klasse_id, "CLASS", start_date, end_date
        )
        periods = [parse_period(p, lookups) for p in raw_periods]
        return sorted(periods, key=lambda p: (p.date, p.start_time))

    def get_homework(self, days_ahead: int = 14) -> list[Homework]:
        """Fetch pending homework assignments."""
        self._ensure_login()
        self._ensure_master_data()
        start = date.today()
        end = start + timedelta(days=days_ahead)
        result = self._rpc_2017("getHomeWork2017", {
            "id": self._student_id,
            "type": "STUDENT",
            "startDate": int(start.strftime("%Y%m%d")),
            "endDate": int(end.strftime("%Y%m%d")),
        })
        lessons_by_id = result.get("lessonsById", {})
        lookups = self._get_lookups()
        return [parse_homework(h, lessons_by_id, lookups) for h in result.get("homeWorks", [])]

    def get_exams(self, days_ahead: int = 30) -> list[dict]:
        """Fetch upcoming exams."""
        self._ensure_login()
        start = date.today()
        end = start + timedelta(days=days_ahead)
        result = self._rpc_2017("getExams2017", {
            "id": self._student_id,
            "type": "STUDENT",
            "startDate": int(start.strftime("%Y%m%d")),
            "endDate": int(end.strftime("%Y%m%d")),
        })
        return result.get("exams", [])

    def get_absences(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Absence]:
        """Fetch registered absences for the student."""
        self._ensure_login()
        if start_date is None:
            self._ensure_master_data()
            sy = self._get_current_schoolyear()
            start_date = _parse_schoolyear_date(sy.get("startDate", ""))
        if end_date is None:
            self._ensure_master_data()
            sy = self._get_current_schoolyear()
            end_date = _parse_schoolyear_date(sy.get("endDate", ""))

        result = self._rpc_2017("getStudentAbsences2017", {
            "startDate": int(start_date.strftime("%Y%m%d")),
            "endDate": int(end_date.strftime("%Y%m%d")),
            "includeExcused": True,
            "includeUnExcused": True,
        })
        return [parse_absence(a) for a in result.get("absences", [])]

    def get_messages(self, target_date: date | None = None) -> list[Message]:
        """Fetch messages of the day."""
        self._ensure_login()
        if target_date is None:
            target_date = date.today()
        result = self._rpc_2017("getMessagesOfDay2017", {
            "date": int(target_date.strftime("%Y%m%d")),
        })
        return [parse_message(m) for m in result.get("messages", [])]

    def get_holidays(self) -> list[Holiday]:
        """Fetch holidays from cached masterData."""
        self._ensure_master_data()
        md = self._master_data or {}
        sy = self._get_current_schoolyear()
        sy_start = sy.get("startDate", "")
        sy_end = sy.get("endDate", "")
        holidays = []
        for h in md.get("holidays", []):
            holidays.append(parse_holiday(h))
        if sy_start and sy_end:
            sy_start_date = _parse_schoolyear_date(sy_start)
            sy_end_date = _parse_schoolyear_date(sy_end)
            holidays = [
                h for h in holidays
                if h.start_date >= sy_start_date and h.start_date <= sy_end_date
            ]
        return holidays

    def get_timegrid(self) -> list[TimeSlot]:
        """Fetch the school's period time grid from masterData."""
        self._ensure_master_data()
        md = self._master_data or {}
        tg = md.get("timeGrid", {})
        if not tg:
            return []
        days = tg.get("days", [])
        if not days:
            return []
        slots = [parse_timeslot(u) for u in days[0].get("units", [])]
        for i, slot in enumerate(slots, 1):
            if not slot.number:
                slot.number = str(i)
        return slots

    def _get_current_schoolyear(self) -> dict:
        """Get the current school year from cached masterData."""
        md = self._master_data or {}
        school_years = md.get("schoolyears", [])
        if not school_years:
            return {}
        today = date.today()
        for sy in school_years:
            sy_start = _parse_schoolyear_date(sy.get("startDate", ""))
            sy_end = _parse_schoolyear_date(sy.get("endDate", ""))
            if sy_start <= today <= sy_end:
                return sy
        return school_years[-1]

    def get_school_info(self) -> SchoolInfo:
        """Fetch aggregated school metadata from masterData."""
        self._ensure_master_data()
        md = self._master_data or {}

        sy = self._get_current_schoolyear()
        timegrid = self.get_timegrid()
        holidays = self.get_holidays()

        last_import = ""
        ts = md.get("timeStamp", 0)
        if ts:
            last_import = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M")

        return SchoolInfo(
            school_name=self.school_name,
            school_year=sy.get("name", ""),
            timegrid=timegrid,
            holidays=holidays,
            last_import=last_import,
        )


def _parse_schoolyear_date(s) -> date:
    """Parse a school year date (ISO string or integer)."""
    if not s:
        return date(2000, 1, 1)
    s = str(s)
    if "-" in s:
        return date.fromisoformat(s)
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
