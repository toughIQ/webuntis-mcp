"""Setup wizard for webuntis-mcp configuration.

Interactive and non-interactive modes for discovering your school,
testing credentials, and generating the MCP config block.
"""

import argparse
import json
import sys
from pathlib import Path

import requests

from .auth import AuthError, totp_login
from .config import CONFIG_FILE

SCHOOL_SEARCH_URL = "https://schoolsearch.webuntis.com/schoolquery2"


def search_schools(query: str) -> list[dict]:
    """Search for schools via the public WebUntis school search API."""
    body = {
        "id": "webuntis-mcp-setup",
        "method": "searchSchool",
        "params": [{"search": query}],
        "jsonrpc": "2.0",
    }
    resp = requests.post(
        SCHOOL_SEARCH_URL,
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})
    return result.get("schools", [])


def _extract_server(school_data: dict) -> str:
    """Extract the server hostname from a school search result."""
    server = school_data.get("server", "")
    if server:
        return server
    server_url = school_data.get("serverUrl", "")
    if server_url:
        hostname = server_url.replace("https://", "").replace("http://", "").split("/")[0]
        return hostname
    return ""


def _test_login(server: str, school: str, username: str, secret: str) -> dict:
    """Test login and return session info."""
    session = totp_login(server, school, username, secret)
    return {
        "school_name": session.school_name,
        "children": session.children,
    }


def _format_mcp_config(server: str, school: str, username: str, secret: str, student: str) -> str:
    """Format the MCP client configuration as JSON."""
    config = {
        "mcpServers": {
            "webuntis-mcp": {
                "command": "webuntis-mcp",
                "env": {
                    "WEBUNTIS_SERVER": server,
                    "WEBUNTIS_SCHOOL": school,
                    "WEBUNTIS_USERNAME": username,
                    "WEBUNTIS_SECRET": secret,
                    "WEBUNTIS_STUDENT": student,
                },
            }
        }
    }
    return json.dumps(config, indent=2)


def _format_config_env(server: str, school: str, username: str, secret: str, student: str) -> str:
    """Format config as env file content."""
    return (
        f"WEBUNTIS_SERVER={server}\n"
        f"WEBUNTIS_SCHOOL={school}\n"
        f"WEBUNTIS_USERNAME={username}\n"
        f"WEBUNTIS_SECRET={secret}\n"
        f"WEBUNTIS_STUDENT={student}\n"
    )


def _interactive_setup() -> None:
    """Walk the user through setup interactively."""
    print("webuntis-mcp setup")
    print("=" * 40)
    print()

    while True:
        query = input("Search for your school (name or city): ").strip()
        if not query:
            continue

        try:
            schools = search_schools(query)
        except Exception as e:
            print(f"Search failed: {e}")
            continue

        if not schools:
            print("No schools found. Try a different search term.")
            continue

        print()
        limit = min(len(schools), 20)
        for i, s in enumerate(schools[:limit], 1):
            name = s.get("displayName", "Unknown")
            address = s.get("address", "")
            print(f"  {i:2}. {name}")
            if address:
                print(f"      {address}")

        if len(schools) > 20:
            print(f"  ... and {len(schools) - 20} more. Try a more specific search.")

        print()
        choice = input("Select your school [number, or 's' to search again]: ").strip()
        if choice.lower() == "s":
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < limit:
                school_data = schools[idx]
                break
        except ValueError:
            pass
        print("Invalid choice.")

    server = _extract_server(school_data)
    school = school_data.get("loginName", "")
    display_name = school_data.get("displayName", school)

    print(f"\nSelected: {display_name}")
    print(f"  Server: {server}")
    print(f"  School ID: {school}")
    print()

    username = input("Your WebUntis username (email): ").strip()
    secret = input("Your QR code secret (Profile > Freigaben > Untis Mobile): ").strip()

    print("\nTesting login...")
    try:
        result = _test_login(server, school, username, secret)
    except AuthError as e:
        print(f"\nLogin failed: {e}")
        print("Check your credentials and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"\nConnection error: {e}")
        sys.exit(1)

    print(f"Login successful! School: {result['school_name']}")

    children = result.get("children", [])
    if not children:
        print("No children linked to this account.")
        sys.exit(1)

    if len(children) == 1:
        child = children[0]
        student = child.get("firstName", "")
        print(f"Child: {child.get('firstName', '')} {child.get('lastName', '')}")
    else:
        print("\nChildren linked to your account:")
        for i, c in enumerate(children, 1):
            print(f"  {i}. {c.get('firstName', '')} {c.get('lastName', '')}")

        while True:
            choice = input("Select child [number]: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(children):
                    child = children[idx]
                    student = child.get("firstName", "")
                    break
            except ValueError:
                pass
            print("Invalid choice.")

    print()
    print("=" * 50)
    print("Setup complete!")
    print("=" * 50)

    _offer_save(server, school, username, secret, student)


def _save_config(server: str, school: str, username: str, secret: str, student: str, quiet: bool = False) -> None:
    """Write config to the standard config file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(_format_config_env(server, school, username, secret, student))
    CONFIG_FILE.chmod(0o600)
    if quiet:
        return
    print(f"\nConfig saved to: {CONFIG_FILE}")
    print(f"Permissions set to 600 (owner-only read/write).")
    print()
    print("Next step: add webuntis-mcp to your AI client.")
    print()
    print("Claude Code:")
    print('  claude mcp add webuntis-mcp webuntis-mcp')
    print()
    print("Or add this to your MCP client settings:")
    print()
    print('  {"mcpServers": {"webuntis-mcp": {"command": "webuntis-mcp"}}}')


def _offer_save(server: str, school: str, username: str, secret: str, student: str) -> None:
    """Ask the user whether to save the config file."""
    print()
    print(f"Save config to {CONFIG_FILE}? [Y/n] ", end="", flush=True)
    choice = input().strip().lower()

    if choice in ("", "y", "yes", "j", "ja"):
        _save_config(server, school, username, secret, student)
    else:
        print()
        print("Config not saved. You can configure manually:")
        print()
        print("Option 1: Create the config file yourself:")
        print(f"  mkdir -p {CONFIG_FILE.parent}")
        print(f"  cat > {CONFIG_FILE} << 'EOF'")
        print(_format_config_env(server, school, username, secret, student), end="")
        print("EOF")
        print(f"  chmod 600 {CONFIG_FILE}")
        print()
        print("Option 2: Pass credentials as env vars in your MCP client settings:")
        print()
        print(_format_mcp_config(server, school, username, secret, student))


def _non_interactive_setup(args: argparse.Namespace) -> None:
    """Run setup with provided arguments, no prompts."""
    try:
        schools = search_schools(args.school)
    except Exception as e:
        _error(f"School search failed: {e}", args.json)

    if not schools:
        _error(f"No school found for '{args.school}'", args.json)

    school_data = None
    for s in schools:
        if s.get("loginName", "").lower() == args.school.lower():
            school_data = s
            break
        if s.get("displayName", "").lower() == args.school.lower():
            school_data = s
            break

    if not school_data:
        school_data = schools[0]

    server = _extract_server(school_data)
    school = school_data.get("loginName", "")

    try:
        result = _test_login(server, school, args.username, args.secret)
    except AuthError as e:
        _error(f"Login failed: {e}", args.json)
    except Exception as e:
        _error(f"Connection error: {e}", args.json)

    children = result.get("children", [])
    if not children:
        _error("No children linked to this account", args.json)

    student = args.student
    if not student:
        student = children[0].get("firstName", "")
    else:
        found = False
        for c in children:
            if student.lower() in c.get("firstName", "").lower():
                student = c.get("firstName", "")
                found = True
                break
        if not found:
            names = [f"{c.get('firstName', '')} {c.get('lastName', '')}" for c in children]
            _error(f"Student '{student}' not found. Available: {', '.join(names)}", args.json)

    if args.json:
        _save_config(server, school, args.username, args.secret, student, quiet=True)
        output = {
            "status": "ok",
            "school_display_name": school_data.get("displayName", ""),
            "config_file": str(CONFIG_FILE),
            "server": server,
            "school": school,
            "username": args.username,
            "student": student,
            "mcp_config": {
                "mcpServers": {
                    "webuntis-mcp": {
                        "command": "webuntis-mcp",
                    }
                }
            },
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"School: {school_data.get('displayName', school)}")
        print(f"Server: {server}")
        print(f"Student: {student}")
        _save_config(server, school, args.username, args.secret, student)


def _error(message: str, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps({"status": "error", "error": message}))
    else:
        print(f"Error: {message}")
    sys.exit(1)


def run_setup(argv: list[str]) -> None:
    """Entry point for 'webuntis-mcp setup'."""
    parser = argparse.ArgumentParser(
        prog="webuntis-mcp setup",
        description="Configure webuntis-mcp with your school and credentials.",
    )
    parser.add_argument("--school", help="School name or city to search for")
    parser.add_argument("--username", help="WebUntis username (email)")
    parser.add_argument("--secret", help="QR code TOTP secret")
    parser.add_argument("--student", help="Child's first name (optional if only one child)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON only (for AI agents and scripts)",
    )

    args = parser.parse_args(argv)

    if args.school and args.username and args.secret:
        _non_interactive_setup(args)
    else:
        try:
            _interactive_setup()
        except KeyboardInterrupt:
            print("\n\nSetup cancelled.")
            sys.exit(1)
        except EOFError:
            print("\n\nNo input available (non-interactive terminal).")
            print("Use: webuntis-mcp setup --school '...' --username '...' --secret '...'")
            sys.exit(1)
