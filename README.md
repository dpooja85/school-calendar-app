# School Calendar Sync - MVP

A simple Python script that extracts school events from a Google Doc and creates a downloadable `.ics` calendar file that can be imported into Google Calendar.

## Quick Start

### Prerequisites

- macOS with [Homebrew](https://brew.sh/) installed
- A Google account
- Access to the school calendar Google Doc

### Step 1: Run Setup Script

```bash
# Make executable and run (one-time setup)
chmod +x setup.sh && ./setup.sh
```

This automatically:
- Installs Python (if needed)
- Creates virtual environment
- Installs all Python dependencies
- Installs Ollama (for email parsing)
- Downloads the LLM model (~4.7GB)
- Starts the Ollama service

> **Note:** You'll need to run `source venv/bin/activate` each time you open a new terminal before running the script.

### Manual Setup (Alternative)

<details>
<summary>Click to expand manual steps</summary>

```bash
# Install Python via Homebrew (if not already installed)
brew install python

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install project dependencies
pip install -r requirements.txt

# Install and start Ollama
brew install ollama
brew services start ollama
ollama pull llama3.1:8b
```
</details>

### Step 2: Set Up Google Docs API Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)

2. Create a new project (or select an existing one):
   - Click the project dropdown at the top
   - Click "New Project"
   - Name it something like "School Calendar Sync"
   - Click "Create"

3. Enable the Google Docs API:
   - Go to "APIs & Services" → "Library"
   - Search for "Google Docs API"
   - Click on it and click "Enable"

4. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - If prompted, configure the OAuth consent screen:
     - Choose "External" user type
     - Fill in required fields (App name, User support email, Developer email)
     - Click "Save and Continue" through the remaining steps
   - Back in Credentials, click "Create Credentials" → "OAuth client ID"
   - Select "Desktop app" as the application type
   - Name it "School Calendar Sync"
   - Click "Create"

5. Download the credentials:
   - Click the download button (↓) next to your new credential
   - Save the file as `credentials.json` in this project folder

### Step 3: Configure (Optional)

Edit `config.yaml` if you need to change settings:

```yaml
google_doc_url: "https://docs.google.com/document/d/YOUR_DOC_ID/edit"
output_file: "output/school_events.ics"
calendar_name: "School Events Calendar"
default_year: 2025
```

### Step 4: Run the Script

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# Run the script
python main.py
```

On first run, a browser window will open asking you to authorize the app. Sign in and allow access.

### Step 5: Import to Google Calendar

1. Open [Google Calendar](https://calendar.google.com)
2. Click the gear icon (⚙️) → "Settings"
3. Click "Import & export" in the left sidebar
4. Click "Select file from your computer"
5. Select `output/school_events.ics`
6. Choose which calendar to add events to
7. Click "Import"

Done! Your school events are now in your calendar.

## Email Parsing with Ollama (Optional)

Extract calendar events from school emails using a local LLM. **Privacy-first**: no cloud APIs, all processing happens on your machine.

### Setup Ollama

```bash
# Install Ollama (macOS)
brew install ollama

# Or via curl
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama (runs in background)
ollama serve

# Download the model (~4.7GB, one-time)
ollama pull llama3.1:8b

# Verify it works
ollama run llama3.1:8b "Say hello"
```

### How to Add Email Events

**Step 1:** Save school emails as text files in `input_emails/`:

```bash
# Example: input_emails/mcas_dates.txt
Subject: MCAS Testing Dates
Date: January 23, 2025

MCAS testing dates for grades 3, 4, and 5:
* March 30, 31 - ELA
* May 12, 13 - MATH
* May 19, 20 - Science (Grade 5 only)
```

You can include Subject/Date headers, or just paste the email body.

**Step 2:** Run the script:

```bash
python main.py
```

**Step 3:** Import `output/school_events.ics` to your calendar

**Step 4:** (Optional) Delete email files after processing

### Configuration

Edit `config.yaml` to enable/disable email parsing:

```yaml
email:
  enabled: true
  input_folder: "input_emails/"
  ollama:
    model: "llama3.1:8b"
    temperature: 0.1
```

### Performance

- ~3-8 seconds per email on M2 MacBook Air
- All processing is local (no data sent to cloud)
- Email files are gitignored for privacy

## Project Structure

```
school-calendar-app/
├── main.py              # Main script
├── src/
│   └── email_parser.py  # Local email + Ollama integration
├── input_emails/        # Put school email .txt files here
│   └── .gitkeep
├── config.yaml          # Configuration
├── credentials.json     # Google OAuth credentials (you create this)
├── token.json           # Auth token (auto-generated)
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── venv/                # Python virtual environment (auto-generated)
└── output/
    └── school_events.ics  # Generated calendar file
```

## Troubleshooting

### "credentials.json not found"

You need to download OAuth credentials from Google Cloud Console. See Step 2 above.

### "Access blocked: This app's request is invalid"

Your OAuth consent screen may not be configured. Go to Google Cloud Console → APIs & Services → OAuth consent screen and complete the setup.

### "Error reading document"

- Make sure the Google Doc URL in `config.yaml` is correct
- Ensure you have access to view the document
- The document ID should be extracted automatically from the URL

### Events not parsing correctly

The parser handles common date formats. If your document uses unusual formatting, the events might not be extracted. Check the script output to see which events were found.

## How It Works

1. **Authentication**: Uses OAuth 2.0 to securely access Google Docs with read-only permissions
2. **Document Reading**: Fetches the content of the specified Google Doc
3. **Event Parsing**: Extracts events by finding dates and associated text
4. **ICS Generation**: Creates a standard iCalendar file that works with Google Calendar, Apple Calendar, Outlook, etc.

## Supported Date Formats

- `January 15, 2025`
- `January 15`
- `1/15/2025`
- `1/15/25`
- `1/15`
- `2025-01-15`
- Day numbers under month headers (e.g., `15 - School Event`)

## Future Enhancements

- [x] Email parsing with local LLM (Ollama)
- [ ] Grade-level filtering
- [ ] Automatic updates
- [ ] Multiple calendar outputs
- [ ] Direct Google Calendar API sync

## License

MIT
