"""WebUntis MCP server.

Exposes WebUntis data as MCP tools for AI agents.
All tools are read-only and use TOTP authentication.
Supports multiple children across different schools.
"""

from datetime import date, timedelta

from mcp.server import MCPServer

from .client import WebUntisClient
from .config import load_all_configs
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
_clients: dict[str, WebUntisClient] = {}


def _init_clients() -> None:
    if _clients:
        return
    configs = load_all_configs()
    if not configs:
        raise RuntimeError(
            "No webuntis-mcp configuration found.\n"
            "Run: webuntis-mcp setup"
        )
    for name, config in configs.items():
        errors = config.validate()
        if errors:
            raise RuntimeError(
                f"Config for '{name}' incomplete:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        _clients[name] = WebUntisClient(config=config)


def _get_client(child: str = "") -> WebUntisClient:
    _init_clients()
    if not child:
        client = next(iter(_clients.values()))
    else:
        key = child.lower().strip()
        client = _clients.get(key)
        if not client:
            available = ", ".join(_clients.keys())
            raise RuntimeError(f"Child '{child}' not found. Available: {available}")
    if not client.is_logged_in:
        client.login()
    return client


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _child_doc() -> str:
    return "child: Child's first name (only needed with multiple children configured)"


@mcp.tool()
def list_children() -> str:
    """List all configured children.

    Shows the name, school, and class for each child that has
    been set up with webuntis-mcp. Use the child's first name
    with any other tool to select which child's data to query.
    """
    _init_clients()
    lines = []
    for name, client in _clients.items():
        if not client.is_logged_in:
            try:
                client.login()
            except Exception:
                lines.append(f"{name}: login failed")
                continue
        info = client.get_school_info()
        student_line = info.student_name or name
        if info.student_class:
            student_line += f", {info.student_class}"
        lines.append(f"{student_line} ({info.school_name})")
    if not lines:
        return "No children configured. Run: webuntis-mcp setup"
    return "\n".join(lines)


@mcp.tool()
def get_timetable(child: str = "", start_date: str = "", end_date: str = "") -> str:
    """Fetch the student's timetable for a date range.

    Returns lessons with subject, room, teacher, and any changes
    (cancellations, substitutions, room swaps).

    Args:
        child: Child's first name (only needed with multiple children)
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: start + 4 days)
    """
    client = _get_client(child)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    periods = client.get_timetable(start, end)
    return format_timetable(periods)


@mcp.tool()
def get_today(child: str = "") -> str:
    """Fetch today's schedule with all details.

    Shows all lessons for today including any cancellations,
    substitutions, room changes, and teacher changes.

    Args:
        child: Child's first name (only needed with multiple children)
    """
    client = _get_client(child)
    today = date.today()
    periods = client.get_timetable(today, today)
    if not periods:
        return "No lessons today."
    return format_timetable(periods, title=f"Today ({today.strftime('%A %d.%m.%Y')})")


@mcp.tool()
def get_tomorrow(child: str = "") -> str:
    """Fetch tomorrow's schedule.

    Shows all lessons for the next school day. If tomorrow is a weekend,
    returns the next Monday's schedule.

    Args:
        child: Child's first name (only needed with multiple children)
    """
    client = _get_client(child)
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
def get_class_timetable(class_name: str = "", child: str = "", start_date: str = "", end_date: str = "") -> str:
    """Fetch a class timetable. Can show any class at the school, not just the student's own.

    Useful for seeing religious instruction, split groups, comparing
    schedules between classes, or checking a friend's class.
    Use list_classes to discover available class names.

    Args:
        class_name: Class name like '1a', '2b', '3c' (default: student's own class)
        child: Child's first name (only needed with multiple children)
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: start + 4 days)
    """
    client = _get_client(child)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    name = class_name.strip() if class_name else None
    periods = client.get_class_timetable(class_name=name, start_date=start, end_date=end)
    title = f"Class {class_name.strip()} Timetable" if class_name.strip() else "Class Timetable"
    return format_timetable(periods, title=title)


@mcp.tool()
def list_classes(child: str = "") -> str:
    """List all classes at the school for the current school year.

    Returns class names that can be used with the get_class_timetable tool
    to fetch any class's schedule.

    Args:
        child: Child's first name (only needed with multiple children)
    """
    client = _get_client(child)
    klassen = client.get_klassen()
    return format_classes(klassen)


@mcp.tool()
def get_homework(child: str = "", days_ahead: int = 14) -> str:
    """Fetch pending homework assignments.

    Returns homework with subject, teacher, description text, and due date.

    Args:
        child: Child's first name (only needed with multiple children)
        days_ahead: Number of days to look ahead (default: 14)
    """
    client = _get_client(child)
    homework = client.get_homework(days_ahead)
    return format_homework(homework)


@mcp.tool()
def get_exams(child: str = "", days_ahead: int = 30) -> str:
    """Fetch upcoming exams and tests.

    Args:
        child: Child's first name (only needed with multiple children)
        days_ahead: Number of days to look ahead (default: 30)
    """
    client = _get_client(child)
    exams = client.get_exams(days_ahead)
    if not exams:
        return "No upcoming exams."
    lines = ["Upcoming Exams", "==============", ""]
    for e in exams:
        lines.append(str(e))
    return "\n".join(lines)


@mcp.tool()
def get_absences(child: str = "", start_date: str = "", end_date: str = "") -> str:
    """Fetch registered absences for the student.

    Shows absence records with dates, times, reasons, excuse status,
    and any notes attached.

    Args:
        child: Child's first name (only needed with multiple children)
        start_date: Start date in YYYY-MM-DD format (default: school year start)
        end_date: End date in YYYY-MM-DD format (default: school year end)
    """
    client = _get_client(child)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    absences = client.get_absences(start, end)
    return format_absences(absences)


@mcp.tool()
def get_changes(child: str = "", start_date: str = "", end_date: str = "") -> str:
    """Detect timetable changes like cancellations, substitutions, and room swaps.

    Filters the timetable for lessons that have been modified from
    the original schedule.

    Args:
        child: Child's first name (only needed with multiple children)
        start_date: Start date in YYYY-MM-DD format (default: today)
        end_date: End date in YYYY-MM-DD format (default: start + 4 days)
    """
    client = _get_client(child)
    start = _parse_date(start_date) or date.today()
    end = _parse_date(end_date) or start + timedelta(days=4)
    periods = client.get_timetable(start, end)
    return format_changes(periods)


@mcp.tool()
def get_messages(child: str = "", target_date: str = "") -> str:
    """Fetch messages of the day from the school.

    Returns announcements, notices, and information messages
    published by the school for a specific date.

    Args:
        child: Child's first name (only needed with multiple children)
        target_date: Date in YYYY-MM-DD format (default: today)
    """
    client = _get_client(child)
    d = _parse_date(target_date)
    messages = client.get_messages(d)
    return format_messages(messages)


@mcp.tool()
def get_school_info(child: str = "") -> str:
    """Fetch school metadata including student, class, period times, holidays, and last data import.

    Useful for understanding the school's schedule structure and
    upcoming free days.

    Args:
        child: Child's first name (only needed with multiple children)
    """
    client = _get_client(child)
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
