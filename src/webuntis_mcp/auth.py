"""WebUntis authentication via TOTP (QR code secret).

Implements the mobile app login flow using the jsonrpc_intern.do endpoint.
No password required for read-only operations.
"""

import time
from dataclasses import dataclass

import pyotp
import requests

API_VERSION = "i3.2"
USER_AGENT = "UntisMobileAndroid"


class AuthError(Exception):
    pass


@dataclass
class SessionInfo:
    jsessionid: str
    person_type: int
    person_id: int
    children: list[dict]
    school_name: str


def make_auth(username: str, secret: str) -> dict:
    """Generate auth dict for per-request 2017 API calls."""
    return {
        "user": username,
        "otp": int(pyotp.TOTP(secret).now()),
        "clientTime": int(time.time() * 1000),
    }


def totp_login(server: str, school: str, username: str, secret: str) -> SessionInfo:
    """Authenticate via TOTP and return session info with JSESSIONID.

    Uses the getUserData2017 method on the internal JSON-RPC endpoint,
    which is the same flow the official Untis Mobile app uses.
    """
    totp = pyotp.TOTP(secret)
    otp_value = totp.now()

    url = (
        f"https://{server}/WebUntis/jsonrpc_intern.do"
        f"?m=getUserData2017&school={school}&v={API_VERSION}"
    )

    body = {
        "id": "webuntis-mcp",
        "method": "getUserData2017",
        "params": [
            {
                "auth": {
                    "user": username,
                    "otp": int(otp_value),
                    "clientTime": int(time.time() * 1000),
                },
                "deviceOs": "AND",
                "deviceOsVersion": "14",
            }
        ],
        "jsonrpc": "2.0",
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise AuthError(f"Connection to {server} failed: {e}") from e

    data = resp.json()

    if "error" in data:
        error = data["error"]
        msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        raise AuthError(f"Login failed: {msg}")

    jsessionid = None
    for cookie in resp.cookies:
        if cookie.name == "JSESSIONID":
            jsessionid = cookie.value
            break

    if not jsessionid:
        set_cookie = resp.headers.get("Set-Cookie", "")
        if "JSESSIONID=" in set_cookie:
            jsessionid = set_cookie.split("JSESSIONID=")[1].split(";")[0]

    result = data.get("result", {})
    user_data = result.get("userData", {})

    if not jsessionid:
        jsessionid = result.get("sessionId") or user_data.get("sessionId")

    if not jsessionid:
        raise AuthError("No JSESSIONID received from server")

    type_map = {
        "KLASSE": 1,
        "TEACHER": 2,
        "SUBJECT": 3,
        "ROOM": 4,
        "STUDENT": 5,
        "LEGAL_GUARDIAN": 12,
    }
    elem_type = user_data.get("elemType", "")
    if isinstance(elem_type, str):
        person_type = type_map.get(elem_type.upper(), 12)
    else:
        person_type = elem_type or 12

    return SessionInfo(
        jsessionid=jsessionid,
        person_type=person_type,
        person_id=user_data.get("elemId", 0),
        children=user_data.get("children", []),
        school_name=user_data.get("schoolName", ""),
    )


def password_login(server: str, school: str, username: str, password: str) -> str:
    """Authenticate via username/password and return JSESSIONID.

    Creates a web session needed for some REST endpoints.
    """
    url = f"https://{server}/WebUntis/jsonrpc.do?school={school}"

    body = {
        "id": "webuntis-mcp",
        "method": "authenticate",
        "params": {
            "user": username,
            "password": password,
            "client": "webuntis-mcp",
        },
        "jsonrpc": "2.0",
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise AuthError(f"Connection to {server} failed: {e}") from e

    data = resp.json()

    if "error" in data:
        error = data["error"]
        msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        raise AuthError(f"Password login failed: {msg}")

    for cookie in resp.cookies:
        if cookie.name == "JSESSIONID":
            return cookie.value

    raise AuthError("No JSESSIONID received from password login")
