"""Configuration loading for webuntis-mcp.

Credentials are loaded from environment variables or config files.
Never hardcoded, never stored in the repository.

Supports multiple children via separate .env files in the config directory:
  ~/.config/webuntis-mcp/kid1.env
  ~/.config/webuntis-mcp/kid2.env

A single config.env is also supported for backwards compatibility.
"""

import os
from dataclasses import dataclass
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "webuntis-mcp"
CONFIG_FILE = CONFIG_DIR / "config.env"


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


def _config_from_values(values: dict[str, str]) -> WebUntisConfig:
    return WebUntisConfig(
        server=values.get("WEBUNTIS_SERVER", ""),
        school=values.get("WEBUNTIS_SCHOOL", ""),
        username=values.get("WEBUNTIS_USERNAME", ""),
        secret=values.get("WEBUNTIS_SECRET", ""),
        student=values.get("WEBUNTIS_STUDENT", ""),
        password=values.get("WEBUNTIS_PASSWORD") or None,
    )


def load_config() -> WebUntisConfig:
    """Load a single config (env vars take precedence over config file)."""
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


def load_all_configs() -> dict[str, WebUntisConfig]:
    """Load all child configs from env vars and config directory.

    Returns a dict keyed by child name (lowercase first name).
    """
    configs: dict[str, WebUntisConfig] = {}

    env_config = _config_from_env()
    if env_config:
        key = env_config.student.lower() or "default"
        configs[key] = env_config

    if not configs:
        named_files = sorted(
            f for f in CONFIG_DIR.glob("*.env")
            if f.name != "config.env" and f.is_file()
        )

        if named_files:
            for f in named_files:
                values = _load_config_file(f)
                config = _config_from_values(values)
                if config.server and config.student:
                    configs[config.student.lower()] = config
        else:
            config = _config_from_values(_load_config_file(CONFIG_FILE))
            if config.server:
                key = config.student.lower() or "default"
                configs[key] = config

    return configs


def _config_from_env() -> WebUntisConfig | None:
    """Load config from environment variables only."""
    server = os.environ.get("WEBUNTIS_SERVER", "")
    if not server:
        return None
    return WebUntisConfig(
        server=server,
        school=os.environ.get("WEBUNTIS_SCHOOL", ""),
        username=os.environ.get("WEBUNTIS_USERNAME", ""),
        secret=os.environ.get("WEBUNTIS_SECRET", ""),
        student=os.environ.get("WEBUNTIS_STUDENT", ""),
        password=os.environ.get("WEBUNTIS_PASSWORD") or None,
    )
