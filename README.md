# 🏫 webuntis-mcp

> MCP server for the WebUntis school platform. Timetables, homework, exams, and absences for parents.

## 💡 What Is This?

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that gives AI assistants read-only access to your child's school data on [WebUntis](https://www.untis.at/). Works with any school that uses WebUntis, anywhere in Europe.

Ask your AI assistant things like:

- *"What's on the schedule tomorrow?"*
- *"Are there any cancellations this week?"*
- *"Does my child have homework due?"*
- *"When is the next school holiday?"*

All data stays on your machine. No cloud service, no telemetry, no account needed beyond your existing WebUntis parent login.

## 🚀 Quick Start

### 1️⃣ Install

```bash
# With uv (recommended)
uv tool install git+https://github.com/toughIQ/webuntis-mcp.git

# With pip
pip install git+https://github.com/toughIQ/webuntis-mcp.git
```

### Guided Setup (recommended)

Run the setup wizard to find your school, test your credentials, and generate the config:

```bash
# Interactive (walks you through each step)
webuntis-mcp setup

# Non-interactive (for scripts and AI agents)
webuntis-mcp setup --school "My School" --username "parent@example.com" --secret "ABCDEF1234567890" --json
```

The setup command searches the public WebUntis school directory, tests your login, resolves your child's name and class, and saves the credentials to `~/.config/webuntis-mcp/config.env` (chmod 600).

### 2️⃣ Get Your QR Code Secret

You'll need this during setup. To find it:

1. Log in to WebUntis in your browser (e.g. `yourschool.webuntis.com`)
2. Go to **Profile** (bottom left)
3. Click the **"Freigaben"** tab (or "Shares" in English)
4. Click **"Zugriff über Untis Mobile"** (or "Access via Untis Mobile")
5. Copy the **Schlüssel / Key** value (a 16-character code like `ABCDEF1234567890`)

### 3️⃣ Add to Your AI Client

After running `webuntis-mcp setup`, your credentials are stored in the config file. The MCP entry only needs the command, no env vars:

**Claude Code / Claude CLI:**

```bash
claude mcp add webuntis-mcp webuntis-mcp
```

**Cursor / Windsurf / Other MCP Clients:**

Add to your MCP settings:

```json
{"mcpServers": {"webuntis-mcp": {"command": "webuntis-mcp"}}}
```

See [AGENTS.md](AGENTS.md) for detailed instructions per client.

<details>
<summary>Manual configuration (without setup command)</summary>

If you prefer not to use the setup wizard, pass credentials as env vars:

```json
{
  "mcpServers": {
    "webuntis-mcp": {
      "command": "webuntis-mcp",
      "env": {
        "WEBUNTIS_SERVER": "yourschool.webuntis.com",
        "WEBUNTIS_SCHOOL": "yourschool",
        "WEBUNTIS_USERNAME": "parent@example.com",
        "WEBUNTIS_SECRET": "ABCDEF1234567890",
        "WEBUNTIS_STUDENT": "kid1"
      }
    }
  }
}
```

You can find all values in the WebUntis QR code dialog (Profile > Freigaben > Untis Mobile).
</details>

### 4️⃣ Verify

Ask your AI assistant: *"What's on the school schedule today?"*

If it returns a timetable, you're set.

## 🛠️ Tools

| Tool | Description |
|------|-------------|
| `get_timetable` | Student timetable for a date range (default: current week) |
| `get_today` | Today's schedule with all details |
| `get_tomorrow` | Tomorrow's schedule (skips weekends) |
| `get_class_timetable` | Timetable for any class at the school (default: student's own class) |
| `list_classes` | List all classes at the school (use with `get_class_timetable`) |
| `get_homework` | Pending homework assignments with due dates |
| `get_exams` | Upcoming exams and tests |
| `get_absences` | Registered absences with reason, status, and notes |
| `get_changes` | Timetable changes: cancellations, substitutions, room and teacher swaps |
| `get_messages` | School messages and announcements for a specific date |
| `get_school_info` | School metadata: period times, holidays, last data import |

All tools are **read-only**. No data is modified on WebUntis.

## 🔑 Authentication

This server uses the **2017 mobile API with per-request TOTP authentication**, the same mechanism the official Untis Mobile app uses. Each API call generates a fresh one-time password from your QR code secret.

**What this means:**

- No browser login, no SSO flow, no session management
- No password stored (unless you choose to provide one)
- Works even if your school uses external SSO (Microsoft, Google, Bildungsportal)
- The secret is a static key that doesn't expire until you regenerate it

**What you need:**

| Config Variable | Where to Find It | Example |
|----------------|-------------------|---------|
| `WEBUNTIS_SERVER` | QR code dialog: "Url" field | `yourschool.webuntis.com` |
| `WEBUNTIS_SCHOOL` | QR code dialog: "Schule" field | `yourschool` |
| `WEBUNTIS_USERNAME` | QR code dialog: "Benutzer" field | `parent@example.com` |
| `WEBUNTIS_SECRET` | QR code dialog: "Schlüssel" field | `ABCDEF1234567890` |
| `WEBUNTIS_STUDENT` | Your child's first name | `kid1` |

If you have multiple children at the same school, `WEBUNTIS_STUDENT` selects which child's data to show. It matches against the first name.

## 🔒 Security and Privacy

- **Credentials never leave your machine.** They are passed as environment variables to the MCP process and used only to authenticate with your school's WebUntis server.
- **No telemetry, no analytics, no cloud.** This is a local tool.
- **Read-only.** This server cannot modify any data on WebUntis.
- **No credentials in the code.** Ever. The repository contains zero secrets.
- **MIT licensed.** You can read every line of code.

> **Store your credentials securely.** Environment variables in your MCP client config are readable by the MCP process only. Do not commit them to version control. Do not share your QR code secret.

## 🐍 Using as a Python Library

The `WebUntisClient` class works standalone, without MCP. Use it to build your own scripts, notification services, or integrations.

```python
from webuntis_mcp.client import WebUntisClient

client = WebUntisClient(
    server="yourschool.webuntis.com",
    school="yourschool",
    username="parent@example.com",
    secret="ABCDEF1234567890",
    student="kid1",
)
client.login()

# Get tomorrow's timetable
from datetime import date, timedelta
tomorrow = date.today() + timedelta(days=1)
periods = client.get_timetable(tomorrow, tomorrow)
for p in periods:
    print(f"{p.start_time} {p.subject} in {p.room} ({p.teacher})")

# Check for homework
homework = client.get_homework(days_ahead=7)
for hw in homework:
    print(f"Due {hw.date_due}: [{hw.subject}] {hw.text[:80]}")

# Check absences
absences = client.get_absences()
for a in absences:
    print(f"{a.start_date}: {a.reason} ({a.excuse_status})")

# List all classes and get another class's timetable
klassen = client.get_klassen()
for k in klassen:
    print(f"{k.name} ({k.long_name})")

other_class = client.get_class_timetable(class_name="2a", start_date=tomorrow, end_date=tomorrow)
for p in other_class:
    print(f"{p.start_time} {p.subject} in {p.room}")

# School info
info = client.get_school_info()
print(f"School: {info.school_name}, Year: {info.school_year}")
print(f"Last data import: {info.last_import}")
```

**Use cases for the library:**

- Build a Telegram or Signal bot that alerts you about schedule changes
- Create a dashboard showing the week's timetable
- Write a cron job that emails you when homework is assigned
- Integrate school data into Home Assistant or other automation platforms

## 🏗️ Architecture

### How It Works

1. The server authenticates with your school's WebUntis instance using TOTP
2. It resolves your child's internal student ID from the parent account
3. Each tool call uses per-request TOTP authentication (same as the official mobile app)
4. The first call fetches master data (subjects, teachers, rooms, classes) and caches it
5. Subsequent calls are fast since only timetable data needs to be fetched

### API Endpoints Used

All calls go through the **2017 mobile API** (`/WebUntis/jsonrpc_intern.do`), the same endpoint the official Untis Mobile app uses:

`getUserData2017`, `getTimetable2017`, `getHomeWork2017`, `getExams2017`, `getStudentAbsences2017`, `getMessagesOfDay2017`

### Parent Account Limitations

WebUntis uses role-based access control. Parent accounts (type 12, "Legal Guardian") have restricted access compared to student or teacher accounts:

| Feature | Status | Notes |
|---------|--------|-------|
| Own child's timetable | ✅ Works | Via student ID from login response |
| Own child's class timetable | ✅ Works | Includes all groups and subjects |
| Any class's timetable | ✅ Works | Use `list_classes` + `get_class_timetable` with a class name |
| Homework | ✅ Works | Via 2017 mobile API |
| Exams | ✅ Works | Via 2017 mobile API |
| Absences | ✅ Works | Read-only via 2017 mobile API |
| Teacher list | ❌ Blocked | Teacher names come from timetable data instead |
| Student list | ❌ Blocked | Student ID comes from login response instead |
| Substitution list | ❌ Blocked | Changes are visible in timetable period data |
| Messages/Announcements | ✅ Works | Via `get_messages` tool |

### What This Server Does NOT Do

- **No write operations.** It cannot create absences, send messages, or modify any data.
- **No notifications.** It provides data on request. Your AI agent or a separate tool handles delivery (Telegram, email, calendar, etc.).
- **No calendar integration.** The agent can read schedule data and use other tools to create calendar events.

## 🔧 Setup Command

The `webuntis-mcp setup` command helps you configure the server without editing JSON files manually.

### Interactive Mode

```bash
webuntis-mcp setup
```

Walks you through:
1. Searching for your school by name or city
2. Entering your credentials (username + QR code secret)
3. Testing the login
4. Selecting your child (if multiple, shows name and class)
5. Saving credentials to `~/.config/webuntis-mcp/config.env` (asks Y/n, default: save)

### Non-Interactive Mode

For scripts and AI agents:

```bash
webuntis-mcp setup \
  --school "Example School" \
  --username "parent@example.com" \
  --secret "ABCDEF1234567890" \
  --student "kid1" \
  --json
```

Saves the config file automatically and returns a JSON status object:

```json
{
  "status": "ok",
  "server": "example.webuntis.com",
  "school": "example",
  "student": "kid1",
  "class": "1A",
  "config_file": "~/.config/webuntis-mcp/config.env",
  "mcp_config": {
    "mcpServers": {
      "webuntis-mcp": {
        "command": "webuntis-mcp"
      }
    }
  }
}
```

On error, returns `{"status": "error", "error": "..."}` with a non-zero exit code.

AI agents can run the setup command and then add the simple `mcp_config` entry to the user's settings. No env vars needed since credentials are in the config file.

## ❓ FAQ

**Q: Does this work with any school?**
A: Yes, any school that uses WebUntis. The server and school name differ per institution, but the API is the same everywhere.

**Q: Do I need a student account?**
A: No. A parent (legal guardian) account is sufficient for all features this server provides.

**Q: Does my school use SSO? Will this still work?**
A: Yes. The TOTP authentication bypasses SSO entirely. It uses the same mechanism as the official Untis Mobile app.

**Q: What if I have multiple children at the same school?**
A: Set `WEBUNTIS_STUDENT` to the first name of the child you want data for. Currently, each MCP instance supports one child. For multiple children, run multiple instances with different configs.

**Q: Is my password needed?**
A: No. The QR code secret (TOTP key) is sufficient for all read operations. Your password is never required.

**Q: How often can I query the API?**
A: WebUntis has rate limiting. Normal usage (a few queries per hour) is fine. Avoid polling more frequently than every 10 minutes.

**Q: Can the school see that I'm using this?**
A: WebUntis logs API access. Your queries appear as Untis Mobile app requests. This is the same as using the official app.

## 📋 Configuration Reference

The recommended way to configure is `webuntis-mcp setup`, which creates the config file automatically.

**Config file** (created by setup): `~/.config/webuntis-mcp/config.env`

```
WEBUNTIS_SERVER=yourschool.webuntis.com
WEBUNTIS_SCHOOL=yourschool
WEBUNTIS_USERNAME=parent@example.com
WEBUNTIS_SECRET=ABCDEF1234567890
WEBUNTIS_STUDENT=kid1
```

**All configuration variables:**

| Variable | Required | Description |
|----------|----------|-------------|
| `WEBUNTIS_SERVER` | Yes | WebUntis server hostname (e.g. `yourschool.webuntis.com`) |
| `WEBUNTIS_SCHOOL` | Yes | School short name as shown in QR code dialog |
| `WEBUNTIS_USERNAME` | Yes | Your login (usually email address) |
| `WEBUNTIS_SECRET` | Yes | 16-character TOTP key from QR code dialog |
| `WEBUNTIS_STUDENT` | Yes | Child's first name (for student resolution) |
| `WEBUNTIS_PASSWORD` | No | Login password (not needed for read-only, reserved for future write support) |

Environment variables take precedence over the config file. This allows overriding individual values without editing the file.

## 🙏 Acknowledgments

This project was inspired by and learned from:

- **[BetterUntis](https://github.com/SapuSeven/BetterUntis)** by SapuSeven (MIT License). His clean implementation of the 2017 mobile API, per-request TOTP authentication, and masterData caching taught us the modern way to talk to WebUntis. The API patterns, method signatures, and response parsing in our code are directly informed by studying his Kotlin source. No code was copied.
- **[homeassistant-WebUntis](https://github.com/JonasJoKuJonas/homeassistant-WebUntis)** by Jonas (MIT License). His work on TOTP authentication for parent accounts and timetable change detection was invaluable during early API exploration.
- **[python-webuntis](https://github.com/python-webuntis/python-webuntis)** (BSD License). The original Python WebUntis library, useful as an API reference.

## ⚖️ Disclaimer

This project is **not affiliated with, endorsed by, or connected to Untis GmbH** or the WebUntis platform in any way. WebUntis is a registered trademark of Untis GmbH.

This tool accesses the WebUntis API as an end user, using the same authentication mechanism as the official Untis Mobile application. It performs read-only operations with the user's own credentials. Use responsibly and in accordance with your school's acceptable use policies.
