#!/usr/bin/env python3
"""
School Calendar Sync - MVP
==========================
Extracts school events from a Google Doc and generates an .ics calendar file.

Usage:
    python main.py
"""

import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dateutil import parser as date_parser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from icalendar import Calendar, Event
import pytz


# Google API scopes - read-only access to Google Docs
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

# Timezone for events (adjust as needed)
TIMEZONE = pytz.timezone('America/Los_Angeles')


def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def extract_doc_id(url: str) -> str:
    """Extract the Google Doc ID from a URL."""
    # Pattern matches the document ID in various Google Docs URL formats
    patterns = [
        r'/document/d/([a-zA-Z0-9-_]+)',
        r'id=([a-zA-Z0-9-_]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract document ID from URL: {url}")


def get_google_docs_service():
    """Authenticate and return Google Docs API service."""
    creds = None
    token_path = 'token.json'
    credentials_path = 'credentials.json'

    # Check if credentials.json exists
    if not os.path.exists(credentials_path):
        print("ERROR: credentials.json not found!")
        print("\nTo set up Google Docs API access:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing one")
        print("3. Enable the Google Docs API")
        print("4. Create OAuth 2.0 credentials (Desktop application)")
        print("5. Download the credentials and save as 'credentials.json'")
        sys.exit(1)

    # Load existing token if available
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or get new credentials if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('docs', 'v1', credentials=creds)


def read_document(service, doc_id: str) -> str:
    """Read the content of a Google Doc and return as plain text."""
    try:
        document = service.documents().get(documentId=doc_id).execute()

        # Extract text from document content
        content = document.get('body', {}).get('content', [])
        text_parts = []

        for element in content:
            if 'paragraph' in element:
                for para_element in element['paragraph'].get('elements', []):
                    if 'textRun' in para_element:
                        text_parts.append(para_element['textRun'].get('content', ''))

        return ''.join(text_parts)

    except HttpError as error:
        print(f"Error reading document: {error}")
        sys.exit(1)


def get_school_year(month_name: str, default_year: int) -> int:
    """
    Determine the year based on month for a school calendar.
    School year runs August-December (first year) and January-June (next year).
    """
    fall_months = ['august', 'september', 'october', 'november', 'december']
    spring_months = ['january', 'february', 'march', 'april', 'may', 'june', 'july']

    month_lower = month_name.lower()[:3]  # Handle both full and abbreviated

    if any(month_lower == m[:3] for m in fall_months):
        return default_year  # 2025
    elif any(month_lower == m[:3] for m in spring_months):
        return default_year + 1  # 2026
    return default_year


def parse_events(text: str, default_year: int) -> list:
    """
    Parse events from document text.
    Returns a list of event dictionaries with: title, date, time, description
    """
    events = []

    # Normalize special characters - Google Docs uses vertical tabs (\x0b) as line breaks
    text = text.replace('\x0b', '\n')
    text = text.replace('\t', ' ')

    lines = text.split('\n')

    MONTHS = r'(January|February|March|April|May|June|July|August|September|October|November|December)'
    MONTHS_SHORT = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'

    # Track the current section header
    current_section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip document title and informational lines
        if 'Burlington School Calendar' in line:
            continue
        if 'Report Card' in line or 'Published' in line or 'go home' in line:
            continue
        if 'Quarter' in line and 'Report' in line:
            continue
        if 'Approved by' in line:
            continue

        # Detect section headers (lines starting with _____)
        if line.startswith('_____'):
            section_text = line.replace('_____', '').strip()
            if section_text:
                current_section = section_text
            continue

        # Detect descriptive headers for groups of dates
        # e.g., "Elementary Early Release Days - *FH, PG, & MEM :12:45 Dismissal"
        if 'Early Release' in line or 'First Day of School' in line or 'Last Day of School' in line:
            current_section = line
            # Don't continue - this line might also have dates
            if not re.search(MONTHS, line, re.IGNORECASE):
                continue

        # Skip lines that are just day names with dates (the date will be on this line)
        # e.g., "Wednesday, September 24, 2025"
        day_name_date = re.match(rf'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+{MONTHS}\s+(\d{{1,2}}),?\s*(\d{{4}})?', line, re.IGNORECASE)
        if day_name_date:
            month = day_name_date.group(2)
            day = int(day_name_date.group(3))
            year = int(day_name_date.group(4)) if day_name_date.group(4) else get_school_year(month, default_year)
            try:
                event_date = date_parser.parse(f"{month} {day}, {year}")
                if current_section:
                    event = create_event_dict(current_section, event_date, line)
                    if event:
                        events.append(event)
            except:
                pass
            continue

        # Pattern: "Month Day & Day, Year – Description" (date range in same month)
        range_same_month = re.match(rf'^{MONTHS}\s+(\d{{1,2}})\s*[&]\s*(\d{{1,2}}),?\s*(\d{{4}})?\s*[–\-]\s*(.+)$', line, re.IGNORECASE)
        if range_same_month:
            month = range_same_month.group(1)
            start_day = int(range_same_month.group(2))
            end_day = int(range_same_month.group(3))
            year = int(range_same_month.group(4)) if range_same_month.group(4) else get_school_year(month, default_year)
            description = range_same_month.group(5).strip()
            for d in range(start_day, end_day + 1):
                try:
                    event_date = date_parser.parse(f"{month} {d}, {year}")
                    event = create_event_dict(description, event_date, line)
                    if event:
                        events.append(event)
                except:
                    pass
            continue

        # Pattern: "Month Day – Day, Year – Description" (date range with dash)
        range_dash = re.match(rf'^{MONTHS}\s+(\d{{1,2}})\s*[–\-]\s*(\d{{1,2}}),?\s*(\d{{4}})?\s*[–\-]\s*(.+)$', line, re.IGNORECASE)
        if range_dash:
            month = range_dash.group(1)
            start_day = int(range_dash.group(2))
            end_day = int(range_dash.group(3))
            year = int(range_dash.group(4)) if range_dash.group(4) else get_school_year(month, default_year)
            description = range_dash.group(5).strip()
            for d in range(start_day, end_day + 1):
                try:
                    event_date = date_parser.parse(f"{month} {d}, {year}")
                    event = create_event_dict(description, event_date, line)
                    if event:
                        events.append(event)
                except:
                    pass
            continue

        # Pattern: "Month Day – Month Day, Year – Description" (cross-month range)
        # Supports both full month names and abbreviations like "Dec."
        MONTHS_CROSS = r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        cross_month = re.match(rf'^{MONTHS}\s+(\d{{1,2}})\s*[–\-]\s*{MONTHS_CROSS}\.?\s*(\d{{1,2}}),?\s*(\d{{4}})?\s*[–\-]\s*(.+)$', line, re.IGNORECASE)
        if cross_month:
            start_month = cross_month.group(1)
            start_day = int(cross_month.group(2))
            end_month = cross_month.group(3)
            end_day = int(cross_month.group(4))
            year = int(cross_month.group(5)) if cross_month.group(5) else get_school_year(start_month, default_year)
            description = cross_month.group(6).strip()
            try:
                start_date = date_parser.parse(f"{start_month} {start_day}, {year}")
                end_date = date_parser.parse(f"{end_month} {end_day}, {year}")
                current = start_date
                while current <= end_date:
                    event = create_event_dict(description, current, line)
                    if event:
                        events.append(event)
                    current += timedelta(days=1)
            except:
                pass
            continue

        # Pattern: "Month Day, Year – Description" (single date with description)
        single_date = re.match(rf'^{MONTHS}\s+(\d{{1,2}}),?\s*(\d{{4}})?\s*[–\-]\s*(.+)$', line, re.IGNORECASE)
        if single_date:
            month = single_date.group(1)
            day = int(single_date.group(2))
            year = int(single_date.group(3)) if single_date.group(3) else get_school_year(month, default_year)
            description = single_date.group(4).strip()
            # Skip if description looks like another date (partial parsing issue)
            if re.match(rf'^{MONTHS}', description, re.IGNORECASE) or re.match(r'^\d+,?$', description):
                continue
            try:
                event_date = date_parser.parse(f"{month} {day}, {year}")
                event = create_event_dict(description, event_date, line)
                if event:
                    events.append(event)
            except:
                pass
            continue

        # Pattern: "Month Day, Year" alone (use section header as title)
        standalone_date = re.match(rf'^{MONTHS}\s+(\d{{1,2}}),?\s*(\d{{4}})?$', line, re.IGNORECASE)
        if standalone_date and current_section:
            month = standalone_date.group(1)
            day = int(standalone_date.group(2))
            year = int(standalone_date.group(3)) if standalone_date.group(3) else get_school_year(month, default_year)
            try:
                event_date = date_parser.parse(f"{month} {day}, {year}")
                event = create_event_dict(current_section, event_date, line)
                if event:
                    events.append(event)
            except:
                pass
            continue

    return events


def expand_abbreviations(text: str) -> str:
    """Expand school name abbreviations."""
    # Order matters - replace longer patterns first to avoid partial matches
    replacements = [
        (r'\*FH\b', 'Fox Hill'),
        (r'\bFH\b', 'Fox Hill'),
        (r'\*PG\b', 'Pine Glen'),
        (r'\bPG\b', 'Pine Glen'),
        (r'\*MEM\b', 'Memorial'),
        (r'\bMEM\b', 'Memorial'),
        (r'\*FW\b', 'Francis Wyman'),
        (r'\bFW\b', 'Francis Wyman'),
    ]
    for pattern, full in replacements:
        text = re.sub(pattern, full, text)
    return text


def create_event_dict(title: str, date: datetime, original_line: str) -> dict:
    """Create an event dictionary from parsed data."""
    if not title or len(title) < 3:
        return None

    # Clean up the title
    title = title.strip()
    title = re.sub(r'^[-–:,]\s*', '', title)
    title = re.sub(r'\s+', ' ', title)

    # Expand school abbreviations
    title = expand_abbreviations(title)

    # Remove trailing year if present
    title = re.sub(r'\s*-?\s*\d{4}\s*$', '', title)

    # Skip if title is just a day name or too short after cleanup
    skip_exact = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    if title.lower() in skip_exact:
        return None

    if len(title) < 3:
        return None

    return {
        'title': title,
        'date': date,
        'start_time': None,  # All-day events for school calendar
        'end_time': None,
        'description': '',
        'original': original_line
    }


def generate_ics(events: list, calendar_name: str, output_path: str) -> str:
    """Generate an ICS file from the list of events."""
    cal = Calendar()

    # Add calendar metadata
    cal.add('prodid', '-//School Calendar Sync//MVP//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', calendar_name)
    cal.add('x-wr-timezone', str(TIMEZONE))

    for i, event_data in enumerate(events):
        event = Event()

        # Generate unique ID
        uid = f"school-event-{i}-{event_data['date'].strftime('%Y%m%d')}@schoolcalendar.local"
        event.add('uid', uid)

        # Add event title
        event.add('summary', event_data['title'])

        # Add date/time
        if event_data['start_time']:
            # Event with specific time
            start_dt = TIMEZONE.localize(event_data['start_time'])
            event.add('dtstart', start_dt)
            if event_data['end_time']:
                end_dt = TIMEZONE.localize(event_data['end_time'])
                event.add('dtend', end_dt)
        else:
            # All-day event
            event.add('dtstart', event_data['date'].date())
            event.add('dtend', (event_data['date'] + timedelta(days=1)).date())

        # Add description if available
        if event_data['description']:
            event.add('description', event_data['description'])

        # Add timestamp
        event.add('dtstamp', datetime.now(pytz.UTC))

        cal.add_component(event)

    # Create output directory if needed
    output_dir = os.path.dirname(output_path)
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Write the ICS file
    with open(output_path, 'wb') as f:
        f.write(cal.to_ical())

    return output_path


def main():
    """Main entry point."""
    # Check for debug mode
    debug_mode = '--debug' in sys.argv

    print("=" * 50)
    print("School Calendar Sync - MVP")
    print("=" * 50)
    print()

    # Load configuration
    print("Loading configuration...")
    config = load_config()

    doc_url = config['google_doc_url']
    output_file = config['output_file']
    calendar_name = config['calendar_name']
    default_year = config.get('school_year_start', config.get('default_year', 2025))

    # Extract document ID
    doc_id = extract_doc_id(doc_url)
    print(f"Document ID: {doc_id}")

    # Authenticate with Google
    print("\nAuthenticating with Google Docs API...")
    service = get_google_docs_service()
    print("✓ Authentication successful")

    # Read the document
    print("\nReading document...")
    doc_text = read_document(service, doc_id)
    print(f"✓ Read {len(doc_text)} characters from document")

    # Debug mode: save raw content and exit
    if debug_mode:
        debug_file = 'output/raw_document.txt'
        Path('output').mkdir(parents=True, exist_ok=True)
        with open(debug_file, 'w') as f:
            f.write(doc_text)
        print(f"\n✓ DEBUG: Saved raw document to {debug_file}")
        print("\nFirst 2000 characters of document:")
        print("-" * 50)
        print(doc_text[:2000])
        print("-" * 50)

        # Show each line with repr to see hidden characters
        print("\nLines with repr (showing hidden chars):")
        print("-" * 50)
        for i, line in enumerate(doc_text.split('\n')[:30]):
            if line.strip():
                print(f"{i}: {repr(line.strip())}")
        print("-" * 50)
        return

    # Parse events
    print("\nParsing events...")
    events = parse_events(doc_text, default_year)
    print(f"✓ Found {len(events)} events")

    if events:
        # Show all events grouped by month for verification
        print("\n" + "=" * 60)
        print("PARSED EVENTS - PLEASE VERIFY")
        print("=" * 60)

        # Group events by month
        from collections import defaultdict
        by_month = defaultdict(list)
        for event in events:
            month_key = event['date'].strftime('%B %Y')
            by_month[month_key].append(event)

        # Sort months chronologically
        sorted_months = sorted(by_month.keys(), key=lambda x: datetime.strptime(x, '%B %Y'))

        for month in sorted_months:
            month_events = sorted(by_month[month], key=lambda x: x['date'])
            print(f"\n--- {month} ({len(month_events)} events) ---")
            for event in month_events:
                date_str = event['date'].strftime('%a, %b %d')
                title = event['title'][:70] + '...' if len(event['title']) > 70 else event['title']
                print(f"  {date_str}: {title}")

        print("\n" + "=" * 60)
        print(f"TOTAL: {len(events)} events")
        print("=" * 60)

    # Ask for confirmation before generating
    print("\nDoes this look correct? (y/n): ", end='')
    response = input().strip().lower()
    if response != 'y':
        print("Aborted. Please check the parser or document format.")
        return

    # Generate ICS file
    print(f"\nGenerating calendar file...")
    output_path = generate_ics(events, calendar_name, output_file)
    print(f"✓ Generated {output_path}")

    # Summary
    print("\n" + "=" * 50)
    print("SUCCESS!")
    print("=" * 50)
    print(f"\n✓ Generated {output_file} with {len(events)} events")
    print("\nNext steps:")
    print("1. Open Google Calendar (calendar.google.com)")
    print("2. Click the gear icon → Settings")
    print("3. Click 'Import & export' on the left")
    print("4. Click 'Select file from your computer'")
    print(f"5. Select: {os.path.abspath(output_file)}")
    print("6. Click 'Import'")
    print("\nYour school events are now in your calendar!")


if __name__ == '__main__':
    main()
