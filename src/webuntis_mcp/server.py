"""WebUntis MCP server.

Exposes WebUntis data as MCP tools for AI agents.
All tools are read-only and use TOTP authentication.
"""

from datetime import date, timedelta

from mcp.server import MCPServer

from .client import WebUntisClient
from .config import load_config
from .formatters import (
    format_absences,
    format_changes,
    format_classes,
    format_homework,
    format_messages,
    format_school_info,
    format_timetable,
)

mcp = MCPServer("webuntis-mcp")
_client: WebUntisClient | None = None


def _get_client() -> WebUntisClient:
    global _client
    if _client is None:
        config = load_config()
        errors = config.validate()
        if errors:
            raise RuntimeError(
                "WebUntis MCP configuration incomplete:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        _client = WebUntisClient(config=config)
    if not _client.is_logged_in:
        _client.login()
    return _client


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


@mcp.tool()
def get_timetable(start_date: str = "", end_date: str = "") -> str:
    """Fetch the student's timetable for a date range.

    Returns lessons with subject, room, teacher, and any changes
    (cancellations, substitutions, room swaps).

    Args:
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: start + 4 days)
    """
    client = _get_client()
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    periods = client.get_timetable(start, end)
    return format_timetable(periods)


@mcp.tool()
def get_today() -> str:
    """Fetch today's schedule with all details.

    Shows all lessons for today including any cancellations,
    substitutions, room changes, and teacher changes.
    """
    client = _get_client()
    today = date.today()
    periods = client.get_timetable(today, today)
    if not periods:
        return "No lessons today."
    return format_timetable(periods, title=f"Today ({today.strftime('%A %d.%m.%Y')})")


@mcp.tool()
def get_tomorrow() -> str:
    """Fetch tomorrow's schedule.

    Shows all lessons for the next school day. If tomorrow is a weekend,
    returns the next Monday's schedule.
    """
    client = _get_client()
    tomorrow = date.today() + timedelta(days=1)
    if tomorrow.weekday() == 5:
        tomorrow += timedelta(days=2)
    elif tomorrow.weekday() == 6:
        tomorrow += timedelta(days=1)
    periods = client.get_timetable(tomorrow, tomorrow)
    if not periods:
        return f"No lessons on {tomorrow.strftime('%A %d.%m.%Y')}."
    return format_timetable(periods, title=f"Tomorrow ({tomorrow.strftime('%A %d.%m.%Y')})")


@mcp.tool()
def get_class_timetable(class_name: str = "", start_date: str = "", end_date: str = "") -> str:
    """Fetch a class timetable. Can show any class at the school, not just the student's own.

    Useful for seeing religious instruction, split groups, comparing
    schedules between classes, or checking a friend's class.
    Use list_classes to discover available class names.

    Args:
        class_name: Class name like '1a', '2b', '3c' (default: student's own class)
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: start + 4 days)
    """
    client = _get_client()
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    name = class_name.strip() if class_name else None
    periods = client.get_class_timetable(class_name=name, start_date=start, end_date=end)
    title = f"Class {class_name.strip()} Timetable" if class_name.strip() else "Class Timetable"
    return format_timetable(periods, title=title)


@mcp.tool()
def list_classes() -> str:
    """List all classes at the school for the current school year.

    Returns class names that can be used with the get_class_timetable tool
    to fetch any class's schedule.
    """
    client = _get_client()
    klassen = client.get_klassen()
    return format_classes(klassen)


@mcp.tool()
def get_homework(days_ahead: int = 14) -> str:
    """Fetch pending homework assignments.

    Returns homework with subject, teacher, description text, and due date.

    Args:
        days_ahead: Number of days to look ahead (default: 14)
    """
    client = _get_client()
    homework = client.get_homework(days_ahead)
    return format_homework(homework)


@mcp.tool()
def get_exams(days_ahead: int = 30) -> str:
    """Fetch upcoming exams and tests.

    Args:
        days_ahead: Number of days to look ahead (default: 30)
    """
    client = _get_client()
    exams = client.get_exams(days_ahead)
    if not exams:
        return "No upcoming exams."
    lines = ["Upcoming Exams", "==============", ""]
    for e in exams:
        lines.append(str(e))
    return "\n".join(lines)


@mcp.tool()
def get_absences(start_date: str = "", end_date: str = "") -> str:
    """Fetch registered absences for the student.

    Shows absence records with dates, times, reasons, excuse status,
    and any notes attached.

    Args:
        start_date: Start date in YYYY-MM-DD format (default: school year start)
        end_date: End date in YYYY-MM-DD format (default: school year end)
    """
    client = _get_client()
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    absences = client.get_absences(start, end)
    return format_absences(absences)


@mcp.tool()
def get_changes(start_date: str = "", end_date: str = "") -> str:
    """Detect timetable changes like cancellations, substitutions, and room swaps.

    Filters the timetable for lessons that have been modified from
    the original schedule.

    Args:
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: start + 4 days)
    """
    client = _get_client()
    start = _parse_date(start_date) or date.today()
    end = _parse_date(end_date) or start + timedelta(days=4)
    periods = client.get_timetable(start, end)
    return format_changes(periods)


@mcp.tool()
def get_messages(target_date: str = "") -> str:
    """Fetch messages of the day from the school.

    Returns announcements, notices, and information messages
    published by the school for a specific date.

    Args:
        target_date: Date in YYYY-MM-DD format (default: today)
    """
    client = _get_client()
    d = _parse_date(target_date)
    messages = client.get_messages(d)
    return format_messages(messages)


@mcp.tool()
def get_school_info() -> str:
    """Fetch school metadata including period times, holidays, and last data import.

    Useful for understanding the school's schedule structure and
    upcoming free days.
    """
    client = _get_client()
    info = client.get_school_info()
    return format_school_info(info)


def main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        from .setup import run_setup

        run_setup(sys.argv[2:])
        return
    mcp.run()


if __name__ == "__main__":
    main()
