# webuntis-mcp Installation Guide for AI Agents

This file helps AI assistants install and configure the webuntis-mcp server.
If a user points you here, follow these steps to get them set up.

## What This Is

webuntis-mcp is an MCP server that provides read-only access to school data
from the WebUntis platform. It supports timetables, homework, exams, absences,
and school metadata. It works with any school that uses WebUntis.

## Prerequisites

- Python 3.11 or later
- A WebUntis parent (legal guardian) account
- The QR code secret from the user's WebUntis profile

## Step 1: Install

Install with uv (preferred) or pip:

```bash
uv tool install git+https://github.com/toughIQ/webuntis-mcp.git
```

Or:

```bash
pip install git+https://github.com/toughIQ/webuntis-mcp.git
```

Verify the command is available:

```bash
webuntis-mcp --help
```

## Step 2: Setup (recommended)

The fastest way to configure is the built-in setup command. It searches for the
school, tests credentials, and outputs the config block.

Non-interactive mode (for AI agents):

```bash
webuntis-mcp setup \
  --school "School Name or City" \
  --username "parent@example.com" \
  --secret "ABCDEF1234567890" \
  --student "kid1" \
  --json
```

The setup command saves credentials to ~/.config/webuntis-mcp/config.env
automatically (chmod 600). On success, the JSON output contains a
`mcp_config` object with just `{"command": "webuntis-mcp"}` (no env vars
needed since the config file handles credentials).
On error, it returns `{"status": "error", "error": "..."}`.

Ask the user for: their school name (or city), their WebUntis login email,
their QR code secret (from WebUntis profile, Freigaben tab, Untis Mobile),
and their child's first name.

If setup succeeds, skip to Step 4.

## Step 2 (alternative): Gather Credentials Manually

Only needed if the setup command is not available. The user provides 5 values
from the WebUntis QR code dialog:

1. Log in to WebUntis in a browser
2. Go to Profile (bottom left corner)
3. Click the "Freigaben" tab (or "Shares" in English)
4. Click "Zugriff ueber Untis Mobile" (or "Access via Untis Mobile")
5. A dialog shows a QR code and these fields:

| Field | Config Variable | Example |
|-------|----------------|---------|
| Url | WEBUNTIS_SERVER | yourschool.webuntis.com |
| Schule | WEBUNTIS_SCHOOL | yourschool |
| Benutzer | WEBUNTIS_USERNAME | parent@example.com |
| Schluessel | WEBUNTIS_SECRET | ABCDEF1234567890 |
| (child's first name) | WEBUNTIS_STUDENT | kid1 |

The user must provide all 5 values. Do not guess or fabricate any of them.

## Step 3: Configure the MCP Client

If you ran `webuntis-mcp setup` in Step 2, credentials are stored in the
config file. The MCP entry only needs the command, no env vars.

### After setup (recommended)

Claude Code:

```bash
claude mcp add webuntis-mcp webuntis-mcp
```

Cursor (.cursor/mcp.json), Windsurf, or any MCP client:

```json
{"mcpServers": {"webuntis-mcp": {"command": "webuntis-mcp"}}}
```

### Manual configuration (without setup)

If you skipped setup and gathered credentials manually in Step 2,
pass them as env vars in the MCP config:

```json
{
  "mcpServers": {
    "webuntis-mcp": {
      "command": "webuntis-mcp",
      "env": {
        "WEBUNTIS_SERVER": "<from step 2>",
        "WEBUNTIS_SCHOOL": "<from step 2>",
        "WEBUNTIS_USERNAME": "<from step 2>",
        "WEBUNTIS_SECRET": "<from step 2>",
        "WEBUNTIS_STUDENT": "<child's first name>"
      }
    }
  }
}
```

## Step 4: Verify

After configuring, test the connection by calling the get_today tool.
It should return the student's timetable for the current day, or a
"No lessons today" message on weekends and holidays.

If it works, all other tools will work too since they use the same
authentication.

## Troubleshooting

### "Login failed: bad credentials"
The WEBUNTIS_SECRET is incorrect. The user should regenerate the QR code
in their WebUntis profile and use the new key value.

### "Connection to ... failed"
The WEBUNTIS_SERVER value is wrong. It should be the hostname only
(e.g. yourschool.webuntis.com), not a full URL.

### "No children linked to this parent account"
The account is not a parent account or no children are registered.
The user should verify they can see their child's data when logging
in to WebUntis in a browser.

### "Student 'X' not found"
WEBUNTIS_STUDENT does not match any child's first name. The error
message shows the available names. Use one of those.

### "WebUntis API error (-8509): no right for ..."
This is expected for certain queries. Parent accounts have restricted
access. The main tools (timetable, homework, exams, absences) all work
within these restrictions.

## Available Tools

- get_timetable: Student timetable for a date range
- get_today: Today's schedule
- get_tomorrow: Tomorrow's schedule
- get_class_timetable: Timetable for any class (pass class_name, e.g. "1a", "2b")
- list_classes: List all classes at the school (use to discover valid class names)
- get_homework: Pending homework with due dates
- get_exams: Upcoming exams
- get_absences: Registered absences with status
- get_changes: Timetable changes (cancellations, substitutions)
- get_messages: School messages and announcements for a date
- get_school_info: Period times, holidays, last data import

All tools are read-only. No tool modifies any data on WebUntis.

## Security Notes

- Credentials are stored in ~/.config/webuntis-mcp/config.env (chmod 600)
  or passed as environment variables, and used only to authenticate with
  the school's WebUntis server
- No data is sent anywhere except to the configured WebUntis server
- No telemetry or analytics
- The TOTP secret should be treated like a password. Do not log it,
  display it, or include it in any output shown to the user
