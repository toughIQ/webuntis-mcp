"""Configuration loading for webuntis-mcp.

Credentials are loaded from environment variables or a config file.
Never hardcoded, never stored in the repository.
"""

import os
from dataclasses import dataclass
from pathlib import Path


CONFIG_FILE = Path.home() / ".config" / "webuntis-mcp" / "config.env"


@dataclass
class WebUntisConfig:
    server: str
    school: str
    username: str
    secret: str
    student: str
    password: str | None = None

    def validate(self) -> list[str]:
        errors = []
        if not self.server:
            errors.append("WEBUNTIS_SERVER is required (e.g. yourschool.webuntis.com)")
        if not self.school:
            errors.append("WEBUNTIS_SCHOOL is required (e.g. yourschool)")
        if not self.username:
            errors.append("WEBUNTIS_USERNAME is required (your login email)")
        if not self.secret:
            errors.append("WEBUNTIS_SECRET is required (QR code key from WebUntis profile)")
        if not self.student:
            errors.append("WEBUNTIS_STUDENT is required (child's first name)")
        return errors


def _load_config_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def load_config() -> WebUntisConfig:
    file_values = _load_config_file(CONFIG_FILE)

    def get(key: str) -> str:
        return os.environ.get(key, file_values.get(key, ""))

    return WebUntisConfig(
        server=get("WEBUNTIS_SERVER"),
        school=get("WEBUNTIS_SCHOOL"),
        username=get("WEBUNTIS_USERNAME"),
        secret=get("WEBUNTIS_SECRET"),
        student=get("WEBUNTIS_STUDENT"),
        password=get("WEBUNTIS_PASSWORD") or None,
    )
