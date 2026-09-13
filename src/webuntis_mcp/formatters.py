"""Human-readable formatters for WebUntis data.

These produce text output that AI agents can interpret naturally.
"""

from datetime import date

from .models import Absence, Holiday, Homework, Klasse, Message, Period, SchoolInfo, TimeSlot

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def format_period(p: Period) -> str:
    day = WEEKDAYS[p.date.weekday()]
    time_range = f"{p.start_time.strftime('%H:%M')}-{p.end_time.strftime('%H:%M')}"
    line = f"{day} {p.date.strftime('%d.%m.')} {time_range}  {p.subject:<8} {p.room:<12} {p.teacher}"

    tags = []
    if p.code == "cancelled":
        tags.append("CANCELLED")
    if p.code == "irregular":
        tags.append("IRREGULAR")
    if p.subst_text:
        tags.append(p.subst_text)
    if p.original_room and p.original_room != p.room:
        tags.append(f"was {p.original_room}")
    if p.original_teacher and p.original_teacher != p.teacher:
        tags.append(f"was {p.original_teacher}")

    if tags:
        line += f"  [{', '.join(tags)}]"

    return line


def format_timetable(periods: list[Period], title: str = "Timetable") -> str:
    if not periods:
        return f"{title}: No lessons found."

    lines = [title, "=" * len(title), ""]
    current_date = None

    for p in periods:
        if p.date != current_date:
            if current_date is not None:
                lines.append("")
            day = WEEKDAYS[p.date.weekday()]
            lines.append(f"--- {day} {p.date.strftime('%d.%m.%Y')} ---")
            current_date = p.date
        lines.append(format_period(p))

    return "\n".join(lines)


def format_homework(homework: list[Homework]) -> str:
    if not homework:
        return "No homework assignments found."

    lines = ["Homework", "========", ""]
    for hw in sorted(homework, key=lambda h: h.date_due):
        status = "DONE" if hw.completed else "open"
        text = hw.text.replace("\n", " | ")[:120]
        lines.append(
            f"Due {hw.date_due.strftime('%d.%m.')} [{hw.subject}] ({status}): {text}"
        )
        if hw.teacher:
            lines.append(f"  Teacher: {hw.teacher}")

    return "\n".join(lines)


def format_absences(absences: list[Absence]) -> str:
    if not absences:
        return "No absences registered."

    lines = ["Absences", "========", ""]
    for a in sorted(absences, key=lambda x: (x.start_date, x.start_time)):
        date_str = a.start_date.strftime("%d.%m.%Y")
        time_str = f"{a.start_time.strftime('%H:%M')}-{a.end_time.strftime('%H:%M')}"
        excuse = "excused" if a.is_excused else a.excuse_status
        lines.append(f"{date_str} {time_str}: {a.reason} ({excuse})")
        if a.text:
            lines.append(f"  Note: {a.text}")

    return "\n".join(lines)


def format_school_info(info: SchoolInfo) -> str:
    lines = []
    if info.student_name:
        student_line = info.student_name
        if info.student_class:
            student_line += f", {info.student_class}"
        lines.append(f"Student: {student_line}")
    lines.extend([
        f"School: {info.school_name}",
        f"School year: {info.school_year}",
        f"Last data import: {info.last_import}",
        "",
        "Period times:",
    ])

    for slot in info.timegrid:
        lines.append(
            f"  Period {slot.number}: {slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}"
        )

    if info.holidays:
        lines.append("")
        lines.append("Holidays and free days:")
        for h in sorted(info.holidays, key=lambda x: x.start_date):
            if h.start_date == h.end_date:
                lines.append(f"  {h.start_date.strftime('%d.%m.%Y')}: {h.long_name}")
            else:
                lines.append(
                    f"  {h.start_date.strftime('%d.%m.')} - {h.end_date.strftime('%d.%m.%Y')}: {h.long_name}"
                )

    return "\n".join(lines)


def format_classes(klassen: list[Klasse]) -> str:
    if not klassen:
        return "No classes found."
    active = [k for k in klassen if k.active]
    lines = [f"Classes ({len(active)})", "=" * 20, ""]
    for k in sorted(active, key=lambda x: x.name):
        line = k.name
        if k.long_name:
            line += f" ({k.long_name})"
        lines.append(line)
    return "\n".join(lines)


def format_messages(messages: list[Message]) -> str:
    if not messages:
        return "No messages for this day."

    lines = ["Messages", "========", ""]
    for m in messages:
        lines.append(f"[{m.subject}]")
        if m.body:
            lines.append(m.body.strip())
        if m.attachments:
            lines.append(f"  Attachments: {', '.join(m.attachments)}")
        lines.append("")

    return "\n".join(lines)


def format_changes(periods: list[Period]) -> str:
    changes = [p for p in periods if p.code or p.subst_text or p.original_room or p.original_teacher]
    if not changes:
        return "No timetable changes detected."

    lines = ["Timetable Changes", "=================", ""]
    for p in changes:
        day = WEEKDAYS[p.date.weekday()]
        time_range = f"{p.start_time.strftime('%H:%M')}-{p.end_time.strftime('%H:%M')}"
        line = f"{day} {p.date.strftime('%d.%m.')} {time_range} {p.subject}"

        if p.code == "cancelled":
            line += " -> CANCELLED"
        elif p.code == "irregular":
            line += " -> IRREGULAR"

        if p.subst_text:
            line += f" ({p.subst_text})"
        if p.original_room and p.original_room != p.room:
            line += f" | Room: {p.original_room} -> {p.room}"
        if p.original_teacher and p.original_teacher != p.teacher:
            line += f" | Teacher: {p.original_teacher} -> {p.teacher}"

        lines.append(line)

    return "\n".join(lines)
