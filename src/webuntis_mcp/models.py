"""Data models for WebUntis API responses."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone


@dataclass
class Period:
    id: int
    date: date
    start_time: time
    end_time: time
    subject: str
    subject_long: str
    room: str
    room_long: str
    teacher: str
    teacher_long: str
    klasse: str
    code: str = ""
    subst_text: str = ""
    ls_text: str = ""
    info: str = ""
    activity_type: str = ""
    student_group: str = ""
    original_room: str = ""
    original_teacher: str = ""


@dataclass
class Homework:
    id: int
    lesson_id: int
    subject: str
    teacher: str
    text: str
    date_assigned: date
    date_due: date
    completed: bool = False


@dataclass
class Exam:
    id: int
    subject: str
    date: date
    start_time: time
    end_time: time
    text: str = ""


@dataclass
class Absence:
    id: int
    student_name: str
    start_date: date
    end_date: date
    start_time: time
    end_time: time
    reason: str
    reason_id: int
    text: str
    excuse_status: str
    is_excused: bool
    can_edit: bool = False


@dataclass
class Message:
    id: int
    subject: str
    body: str
    attachments: list[str] = field(default_factory=list)


@dataclass
class Holiday:
    name: str
    long_name: str
    start_date: date
    end_date: date


@dataclass
class TimeSlot:
    number: str
    start_time: time
    end_time: time


@dataclass
class Klasse:
    id: int
    name: str
    long_name: str
    active: bool = True


@dataclass
class SchoolInfo:
    school_name: str
    school_year: str
    timegrid: list[TimeSlot] = field(default_factory=list)
    holidays: list[Holiday] = field(default_factory=list)
    last_import: str = ""


def _parse_iso_datetime(s: str) -> datetime:
    """Parse ISO datetime like '2026-09-11T08:55Z'."""
    if not s:
        return datetime(2000, 1, 1, tzinfo=timezone.utc)
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _parse_iso_date(s: str) -> date:
    """Parse ISO date like '2026-09-11' or integer like 20260911."""
    if not s:
        return date(2000, 1, 1)
    if isinstance(s, int):
        s = str(s)
    s = str(s)
    if "-" in s:
        return date.fromisoformat(s)
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _parse_time_str(s: str) -> time:
    """Parse time like 'T08:00' or '08:00'."""
    if not s:
        return time(0, 0)
    s = s.lstrip("T")
    parts = s.split(":")
    return time(int(parts[0]), int(parts[1]))


def _first(items: list, key: str, default: str = "") -> str:
    if items:
        return items[0].get(key, default)
    return default


def _lookup(lookup: dict, elem_id: int, field: str, default: str = "") -> str:
    entry = lookup.get(elem_id)
    if entry:
        return entry.get(field, default)
    return default


def parse_period(raw: dict, lookups: dict) -> Period:
    """Parse a period from getTimetable2017 response.

    lookups is {"subjects": {id: {...}}, "teachers": {id: {...}},
                "rooms": {id: {...}}, "klassen": {id: {...}}}
    """
    subjects = lookups.get("subjects", {})
    teachers = lookups.get("teachers", {})
    rooms = lookups.get("rooms", {})
    klassen = lookups.get("klassen", {})

    start_dt = _parse_iso_datetime(raw.get("startDateTime", ""))
    end_dt = _parse_iso_datetime(raw.get("endDateTime", ""))

    subject_id = 0
    subject_org_id = 0
    teacher_id = 0
    teacher_org_id = 0
    room_id = 0
    room_org_id = 0
    klasse_id = 0

    for elem in raw.get("elements", []):
        etype = elem.get("type", "")
        eid = elem.get("id", 0)
        org_id = elem.get("orgId", eid)
        if etype == "SUBJECT":
            subject_id = eid
            subject_org_id = org_id
        elif etype == "TEACHER":
            teacher_id = eid
            teacher_org_id = org_id
        elif etype == "ROOM":
            room_id = eid
            room_org_id = org_id
        elif etype == "CLASS":
            klasse_id = eid

    flags = raw.get("is", [])
    code = ""
    if "CANCELLED" in flags:
        code = "cancelled"
    elif "IRREGULAR" in flags:
        code = "irregular"

    text = raw.get("text", {})
    original_teacher = ""
    if teacher_org_id and teacher_org_id != teacher_id:
        original_teacher = _lookup(teachers, teacher_org_id, "name")
    original_room = ""
    if room_org_id and room_org_id != room_id:
        original_room = _lookup(rooms, room_org_id, "name")

    return Period(
        id=raw.get("id", 0),
        date=start_dt.date(),
        start_time=start_dt.time(),
        end_time=end_dt.time(),
        subject=_lookup(subjects, subject_id, "name"),
        subject_long=_lookup(subjects, subject_id, "longName"),
        room=_lookup(rooms, room_id, "name"),
        room_long=_lookup(rooms, room_id, "longName"),
        teacher=_lookup(teachers, teacher_id, "name"),
        teacher_long=_lookup(teachers, teacher_id, "longName"),
        klasse=_lookup(klassen, klasse_id, "name"),
        code=code,
        subst_text=text.get("substitution", "") if isinstance(text, dict) else "",
        ls_text=text.get("lesson", "") if isinstance(text, dict) else "",
        info=text.get("info", "") if isinstance(text, dict) else "",
        student_group=raw.get("sg", ""),
        original_room=original_room,
        original_teacher=original_teacher,
    )


def parse_homework(raw_homework: dict, lessons_by_id: dict, lookups: dict | None = None) -> Homework:
    """Parse homework from getHomeWork2017 response."""
    lesson_id = raw_homework.get("lessonId", 0)
    lesson = lessons_by_id.get(str(lesson_id), lessons_by_id.get(lesson_id, {}))

    subjects = (lookups or {}).get("subjects", {})
    teachers = (lookups or {}).get("teachers", {})

    subject_id = lesson.get("subjectId", 0)
    subject = _lookup(subjects, subject_id, "name") if subjects else ""
    if not subject:
        subject = lesson.get("subject", str(subject_id) if subject_id else "")

    teacher = ""
    teacher_ids = lesson.get("teacherIds", [])
    if teacher_ids and teachers:
        teacher = _lookup(teachers, teacher_ids[0], "name")

    return Homework(
        id=raw_homework.get("id", 0),
        lesson_id=lesson_id,
        subject=subject,
        teacher=teacher,
        text=raw_homework.get("text", ""),
        date_assigned=_parse_iso_date(raw_homework.get("startDate", "")),
        date_due=_parse_iso_date(raw_homework.get("endDate", "")),
        completed=raw_homework.get("completed", False),
    )


def parse_absence(raw: dict) -> Absence:
    """Parse absence from getStudentAbsences2017 response."""
    start_dt = _parse_iso_datetime(raw.get("startDateTime", ""))
    end_dt = _parse_iso_datetime(raw.get("endDateTime", ""))

    excused = raw.get("excused", False)
    excuse = raw.get("excuse", {}) or {}
    excuse_status = "excused" if excused else excuse.get("text", "not excused")

    return Absence(
        id=raw.get("id", 0),
        student_name=raw.get("studentName", ""),
        start_date=start_dt.date(),
        end_date=end_dt.date(),
        start_time=start_dt.time(),
        end_time=end_dt.time(),
        reason=raw.get("absenceReason", ""),
        reason_id=raw.get("absenceReasonId", 0),
        text=raw.get("text", ""),
        excuse_status=excuse_status,
        is_excused=excused,
        can_edit=raw.get("owner", False),
    )


def parse_message(raw: dict) -> Message:
    attachments = []
    for a in raw.get("attachments", []):
        if isinstance(a, dict):
            attachments.append(a.get("name", a.get("url", str(a))))
        else:
            attachments.append(str(a))

    return Message(
        id=raw.get("id", 0),
        subject=raw.get("subject", ""),
        body=raw.get("body", ""),
        attachments=attachments,
    )


def parse_holiday(raw: dict) -> Holiday:
    return Holiday(
        name=raw.get("name", ""),
        long_name=raw.get("longName", ""),
        start_date=_parse_iso_date(raw.get("startDate", "")),
        end_date=_parse_iso_date(raw.get("endDate", "")),
    )


def parse_timeslot(raw: dict) -> TimeSlot:
    """Parse a timeslot from masterData timeGrid unit."""
    start = raw.get("startTime", "")
    end = raw.get("endTime", "")
    if isinstance(start, str):
        start_time = _parse_time_str(start)
        end_time = _parse_time_str(end)
    else:
        s = str(start).zfill(4)
        start_time = time(int(s[:2]), int(s[2:4]))
        s = str(end).zfill(4)
        end_time = time(int(s[:2]), int(s[2:4]))

    return TimeSlot(
        number=raw.get("label", raw.get("name", "")),
        start_time=start_time,
        end_time=end_time,
    )


def parse_klasse(raw: dict) -> Klasse:
    return Klasse(
        id=raw.get("id", 0),
        name=raw.get("name", ""),
        long_name=raw.get("longName", ""),
        active=raw.get("active", True),
    )
