# School Calendar Sync - Project Documentation

## Product Requirements Document (PRD)

### Overview
A simple Python script that extracts school events from a Google Doc and creates a downloadable `.ics` calendar file that parents can import into Google Calendar.

### Problem Statement
Parents need an easy way to get school events into their personal calendars. The school publishes events in a Google Doc, but manually copying events is tedious and error-prone.

### MVP Goal
Parse the existing Google Doc calendar and generate ONE downloadable `.ics` file with all school events.

### Target Users
- Parents of students at the school
- Anyone with access to the school calendar Google Doc

### MVP Features

#### 1. Google Docs Parser
- Read the Google Doc: https://docs.google.com/document/d/1TUukMCnAUy4e09vFZn7YTfTTtaXDovsGbAEIzqxLVHA/edit
- Extract event information:
  - Event name/title
  - Date
  - Time (if available)
  - Basic description
- Handle common date formats in the document

#### 2. Calendar File Generator
- Create a single `.ics` file with all extracted events
- Ensure the `.ics` file can be imported into Google Calendar
- Save to an `output/` folder

#### 3. Simple Configuration
- Basic config file with:
  - Google Doc URL
  - Output file name
  - Calendar name
  - Default year for ambiguous dates

### Out of Scope (Post-MVP)
- ❌ Gmail integration (emails can come later)
- ❌ Grade-level filtering
- ❌ Duplicate detection
- ❌ Automatic scheduling/updates
- ❌ Direct Google Calendar API integration
- ❌ Multiple calendar files
- ❌ Web interface
- ❌ Database storage

### Success Criteria
- ✅ Successfully reads the Google Doc
- ✅ Extracts events with dates
- ✅ Generates valid `.ics` file
- ✅ `.ics` file imports successfully into Google Calendar
- ✅ Has basic README with setup instructions
- ✅ Runs without errors on fresh setup

### User Flow
1. **Setup (One-time)**
   - Clone/download the code
   - Install dependencies: `pip install -r requirements.txt`
   - Set up Google OAuth credentials
   - Edit `config.yaml` with the Google Doc URL

2. **Usage**
   - Run: `python main.py`
   - Script outputs: `✓ Generated school_events.ics with N events`
   - User imports `output/school_events.ics` into their Google Calendar

---

## Architecture Decisions

### Decision 1: Single-File Architecture
**Choice:** All functionality in `main.py` instead of multiple modules.

**Why:**
- MVP scope is small enough that separation adds complexity without benefit
- Easier for users to understand and modify
- Simpler deployment (just one script to run)
- Can refactor into modules later if the project grows

**Trade-offs:**
- Less modular, but acceptable for ~300 lines of code
- All functions are still well-separated within the file

### Decision 2: OAuth 2.0 for Google Docs API
**Choice:** Use OAuth 2.0 Desktop flow with `credentials.json` and `token.json`.

**Why:**
- Google Docs API requires authentication for reading documents
- OAuth 2.0 is the standard secure method
- Desktop flow works without a web server
- Token refresh is automatic after initial auth
- Read-only scope (`documents.readonly`) follows principle of least privilege

**Alternatives Considered:**
- Service Account: Requires sharing doc with service account email, more setup
- API Key: Not supported for Google Docs API
- Published/Public Doc: Would require different parsing approach, less reliable

### Decision 3: Date Parsing Strategy
**Choice:** Multiple regex patterns + python-dateutil for flexible parsing.

**Why:**
- School documents use inconsistent date formats
- Need to handle: "January 15, 2025", "1/15/25", "2025-01-15", etc.
- Month headers with day numbers (e.g., "JANUARY" followed by "15 - Event")
- `python-dateutil` handles edge cases well

**Patterns Supported:**
```python
# Full dates
"January 15, 2025"
"1/15/2025" or "1/15/25" or "1/15"
"2025-01-15"

# Day under month header
"JANUARY 2025"
"15 - School Event"
```

**Trade-offs:**
- May miss unusual formats, but covers 90%+ of cases
- Can add patterns as needed based on real document structure

### Decision 4: All-Day Events as Default
**Choice:** Events without explicit times become all-day events.

**Why:**
- Most school events (holidays, early dismissal days, etc.) are all-day
- Better UX in calendar apps - shows at top of day view
- Time parsing is attempted but optional

**Implementation:**
```python
if event_data['start_time']:
    # Event with specific time
    event.add('dtstart', start_dt)
else:
    # All-day event (date only, no time)
    event.add('dtstart', event_data['date'].date())
```

### Decision 5: Timezone Handling
**Choice:** Default to `America/Los_Angeles` (Pacific Time).

**Why:**
- School is likely in a specific timezone
- ICS files need timezone info for proper display
- Using pytz for reliable timezone handling
- Can be changed in config if needed

**Future Enhancement:** Add timezone to config.yaml

### Decision 6: YAML for Configuration
**Choice:** Use YAML instead of JSON, .env, or Python config.

**Why:**
- Human-readable and easy to edit
- Supports comments for documentation
- No quotes needed for simple strings
- Standard for configuration files
- `pyyaml` is lightweight and reliable

### Decision 7: ICS File Format
**Choice:** Generate standard iCalendar (.ics) file instead of direct Google Calendar API.

**Why:**
- Universal format - works with Google, Apple, Outlook, etc.
- No additional API permissions needed
- User has full control over import
- Simpler implementation
- No risk of modifying user's calendar unexpectedly

**ICS Properties Set:**
- `PRODID`: Identifies the generating application
- `VERSION`: iCalendar version 2.0
- `CALSCALE`: Gregorian calendar
- `X-WR-CALNAME`: Calendar display name
- `X-WR-TIMEZONE`: Timezone for display
- Per-event: `UID`, `SUMMARY`, `DTSTART`, `DTEND`, `DTSTAMP`

### Decision 8: Error Handling Philosophy
**Choice:** Fail fast with clear error messages, don't silently skip.

**Why:**
- Users should know if something went wrong
- Missing credentials → clear setup instructions
- API errors → show the actual error
- Better to generate fewer correct events than many incorrect ones

**Example:**
```python
if not os.path.exists(credentials_path):
    print("ERROR: credentials.json not found!")
    print("\nTo set up Google Docs API access:")
    # ... detailed instructions ...
    sys.exit(1)
```

### Decision 9: No Database
**Choice:** Stateless script, no persistence between runs.

**Why:**
- MVP doesn't need duplicate detection
- Simpler deployment
- User can just re-run and re-import
- Google Calendar handles duplicate UIDs gracefully

### Decision 10: Output Directory Structure
**Choice:** Output to `output/` subdirectory, not project root.

**Why:**
- Keeps generated files separate from source
- Easy to gitignore
- Clear separation of concerns
- User knows where to find the output

### Decision 11: Homebrew + Virtual Environment for Python
**Choice:** Use Homebrew (`brew install python`) with a project-local virtual environment.

**Why:**
- macOS system Python is outdated and Apple discourages using it
- Homebrew is the de facto standard package manager for macOS
- **PEP 668 compliance**: Modern Homebrew Python (3.12+) marks itself as "externally managed" and blocks global pip installs to prevent breaking system packages
- Virtual environments isolate project dependencies cleanly
- Standard Python practice that works everywhere

**Setup commands:**
```bash
brew install python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Why not other approaches:**
- `pip3 install --break-system-packages`: Works but risky, can break Homebrew
- `pip3 install --user`: Clutters user site-packages, version conflicts
- `pipx`: Great for CLI tools, but this is a script with multiple dependencies
- `conda`: Heavier than needed for this project

**Alternatives Considered:**
- pyenv: More control over Python versions, but adds complexity
- System Python: Outdated, Apple recommends against using it
- Conda: Overkill for this project, larger footprint
- Docker: Too heavy for a simple script

---

## Technical Specifications

### Development Environment
- **Platform:** macOS
- **Package Manager:** Homebrew
- **Python:** Installed via `brew install python` (provides `python3`)
- **Virtual Environment:** `python3 -m venv venv` (required due to PEP 668)
- **Dependencies:** Installed via `pip install -r requirements.txt` (inside venv)

### Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| google-api-python-client | >=2.100.0 | Google Docs API client |
| google-auth-oauthlib | >=1.1.0 | OAuth 2.0 authentication |
| google-auth-httplib2 | >=0.1.1 | HTTP transport for auth |
| icalendar | >=5.0.0 | ICS file generation |
| python-dateutil | >=2.8.2 | Flexible date parsing |
| pytz | >=2024.1 | Timezone handling |
| pyyaml | >=6.0 | Configuration file parsing |
| ollama | >=0.1.0 | Local LLM for email parsing |

### File Structure
```
school-calendar-app/
├── main.py              # All application logic
├── config.yaml          # User configuration
├── credentials.json     # Google OAuth (user provides, gitignored)
├── token.json           # Auth token (auto-generated, gitignored)
├── requirements.txt     # Python dependencies
├── README.md            # User documentation
├── claude.md            # This file - project documentation
├── .gitignore           # Git ignore rules
└── output/
    └── school_events.ics  # Generated calendar
```

### API Scopes
- `https://www.googleapis.com/auth/documents.readonly` - Read-only access to Google Docs

### Decision 12: Local Email Files + Ollama (Privacy-First)
**Choice:** Use local text files + Ollama LLM instead of Gmail API for email parsing.

**Why:**
- **Privacy**: No cloud API reads user's emails - all processing is local
- **Control**: User manually saves only the emails they want processed
- **No OAuth complexity**: Doesn't require Gmail API scope or additional permissions
- **Offline capable**: Works without internet once Ollama model is downloaded
- **Cost-free**: Ollama runs locally, no API costs

**How it works:**
1. User saves school emails as `.txt` files in `input_emails/` folder
2. Script reads all `.txt` files from folder
3. Ollama LLM extracts calendar events from unstructured text
4. Events are merged with Google Doc events

**Why Ollama (llama3.1:8b):**
- Runs locally on M2 MacBook Air (3-8 sec/email)
- Good balance of quality and speed
- 8B parameter model fits in memory
- JSON output mode for structured responses

**Alternatives Rejected:**
- Gmail API: Privacy concerns, complex OAuth, reads all emails
- Cloud LLMs (OpenAI, Claude): Sends email content to cloud, API costs
- Regex parsing: Too brittle for unstructured emails

---

## Future Enhancements

### Phase 2
1. ~~Gmail Integration~~ → **Implemented as local files + Ollama**
2. **Grade-Level Filtering** - Generate separate calendars per grade
3. **Duplicate Detection** - Track previously imported events
4. **Configurable Timezone** - Add to config.yaml

### Phase 3
1. **Direct Google Calendar API** - Push events directly
2. **Automatic Updates** - Cron job or scheduled task
3. **Web Interface** - Simple UI for non-technical users
4. **Multiple Document Sources** - Support multiple Google Docs

---

## Changelog

### v1.1.0 - 2025-01-29
- Added email parsing with local files + Ollama LLM
- Privacy-first approach: no Gmail API, all local processing
- Created `src/email_parser.py` module
- Added `input_emails/` folder for email text files
- Updated config.yaml with email settings
- Added test file for email parser validation

### v1.0.0 (MVP) - 2025-01-28
- Initial implementation
- Google Docs API integration with OAuth 2.0
- Multi-format date parsing
- ICS file generation
- Basic configuration via YAML
- README with setup instructions
- Homebrew + virtual environment setup for macOS (PEP 668 compliant)
