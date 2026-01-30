"""
Email Parser Module (Local Files + Ollama)
==========================================
Privacy-first email parsing: reads local .txt files and uses Ollama LLM
to extract calendar events. No cloud APIs, all processing happens locally.

Usage:
1. Save school emails as .txt files in input_emails/ folder
2. Run the script
3. Events are extracted and merged with Google Doc events
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


def read_email_files(folder_path: str) -> list:
    """
    Read all .txt email files from the specified folder.

    Supports two formats:
    1. With headers: "Subject: ...\nDate: ...\n\n[body]"
    2. Plain body text (uses filename as identifier)

    Returns list of dicts: [{'filename': str, 'subject': str, 'date': str, 'body': str}]
    """
    emails = []
    folder = Path(folder_path)

    if not folder.exists():
        print(f"Warning: Email folder '{folder_path}' does not exist")
        return emails

    # Find all .txt files
    txt_files = list(folder.glob('*.txt'))

    if not txt_files:
        print(f"No .txt files found in '{folder_path}'")
        return emails

    print(f"Found {len(txt_files)} email file(s) to process")

    for filepath in sorted(txt_files):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                continue

            # Parse the email content
            email_data = parse_email_content(content, filepath.name)
            emails.append(email_data)

        except Exception as e:
            print(f"Error reading {filepath.name}: {e}")
            continue

    return emails


def parse_email_content(content: str, filename: str) -> dict:
    """
    Parse email content, extracting subject and date if present.

    Handles formats:
    - "Subject: ...\nDate: ...\n\n[body]"
    - Just body text
    """
    subject = None
    date = None
    body = content

    lines = content.split('\n')

    # Check for metadata headers at the start
    header_lines = 0
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Check for Subject header
        if line_stripped.lower().startswith('subject:'):
            subject = line_stripped[8:].strip()
            header_lines = i + 1

        # Check for Date header
        elif line_stripped.lower().startswith('date:'):
            date = line_stripped[5:].strip()
            header_lines = i + 1

        # Empty line after headers marks start of body
        elif line_stripped == '' and header_lines > 0:
            body = '\n'.join(lines[i+1:]).strip()
            break

        # If we hit non-header content, treat everything as body
        elif not line_stripped.lower().startswith(('subject:', 'date:', 'from:', 'to:')):
            if header_lines == 0:
                # No headers found, entire content is body
                body = content
                break

    # Use filename as fallback identifier
    if not subject:
        subject = filename.replace('.txt', '').replace('_', ' ')

    return {
        'filename': filename,
        'subject': subject,
        'date': date,
        'body': body
    }


def check_ollama_available(config: dict) -> bool:
    """Check if Ollama is installed and the model is available."""
    if not OLLAMA_AVAILABLE:
        print("Error: ollama package not installed. Run: pip install ollama")
        return False

    model = config.get('email', {}).get('ollama', {}).get('model', 'llama3.1:8b')

    try:
        # Try to list models to check connection
        response = ollama.list()

        # Handle different API response formats
        model_names = []
        models_list = response.get('models', []) if isinstance(response, dict) else getattr(response, 'models', [])

        for m in models_list:
            # Try different attribute/key names used by different ollama versions
            if isinstance(m, dict):
                name = m.get('name') or m.get('model') or ''
            else:
                name = getattr(m, 'name', None) or getattr(m, 'model', '') or ''
            if name:
                model_names.append(name)

        # Check if our model is available (handle version tags)
        model_base = model.split(':')[0]
        available = any(model_base in name for name in model_names)

        if not available:
            print(f"Error: Model '{model}' not found. Run: ollama pull {model}")
            if model_names:
                print(f"Available models: {model_names}")
            return False

        return True

    except ConnectionError:
        print("Error: Cannot connect to Ollama.")
        print("Start Ollama with: brew services start ollama")
        return False
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        print("Make sure Ollama is running: brew services start ollama")
        return False


def extract_dates_with_regex(text: str, school_year_start: int) -> list:
    """
    Extract all dates from text using regex patterns.
    Returns list of dicts with: date_str, time_str, context (surrounding text)
    """
    import calendar

    found_dates = []

    # Month name mapping
    month_map = {name.lower(): num for num, name in enumerate(calendar.month_name) if num}
    month_map.update({name.lower(): num for num, name in enumerate(calendar.month_abbr) if num})

    # Time pattern - must have AM/PM or be in HH:MM format
    time_pattern = r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)'

    def parse_time(line: str) -> str:
        """Extract time from line, return HH:MM or None."""
        time_match = re.search(time_pattern, line)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            ampm = time_match.group(3).lower()
            if ampm == 'pm' and hour < 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            return f"{hour:02d}:{minute:02d}"
        return None

    def get_year(month: int) -> int:
        """Determine year based on school calendar."""
        if month >= 8:  # Aug-Dec
            return school_year_start
        else:  # Jan-Jul
            return school_year_start + 1

    def add_date(month: int, day: int, year: int, time_str: str, context: str):
        """Add a date to found_dates if valid."""
        if not month or month < 1 or month > 12:
            return
        if day < 1 or day > 31:
            return
        if year is None:
            year = get_year(month)
        date_str = f"{year}-{month:02d}-{day:02d}"
        found_dates.append({
            'date': date_str,
            'time': time_str,
            'context': context
        })

    lines = text.split('\n')

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        time_str = parse_time(line)

        # Pattern 1: "Month Day, Day" or "Month Day, Day, Day" (date ranges)
        # e.g., "March 30, 31" or "May 12, 13"
        range_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,\s*(\d{1,2}))?(?:\s*,\s*(\d{1,2}))?'
        for match in re.finditer(range_pattern, line, re.IGNORECASE):
            month_name = match.group(1).lower()
            month = month_map.get(month_name[:3], 0)
            if month:
                # First day
                day1 = int(match.group(2))
                add_date(month, day1, None, time_str, line_stripped)
                # Second day (if present)
                if match.group(3):
                    day2 = int(match.group(3))
                    if day2 <= 31:  # Make sure it's a day, not a year
                        add_date(month, day2, None, time_str, line_stripped)
                # Third day (if present)
                if match.group(4):
                    day3 = int(match.group(4))
                    if day3 <= 31:
                        add_date(month, day3, None, time_str, line_stripped)

        # Pattern 2: Numeric dates "2/27" or "2/27/26"
        numeric_pattern = r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?'
        for match in re.finditer(numeric_pattern, line):
            month = int(match.group(1))
            day = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else None
            if year and year < 100:
                year += 2000
            add_date(month, day, year, time_str, line_stripped)

    # Remove duplicates (same date)
    seen = set()
    unique_dates = []
    for d in found_dates:
        key = d['date']
        if key not in seen:
            seen.add(key)
            unique_dates.append(d)

    return unique_dates


def extract_events_with_ollama(
    email_text: str,
    email_subject: str,
    config: dict
) -> list:
    """
    Hybrid approach: Use regex to find dates (reliable), then LLM for titles (smart).
    Regex dates are source of truth - we never lose events.

    Returns list of event dicts with: title, date, time, description, grade_level
    """
    ollama_config = config.get('email', {}).get('ollama', {})
    model = ollama_config.get('model', 'llama3.1:8b')
    temperature = ollama_config.get('temperature', 0.1)
    school_year_start = config.get('school_year_start', 2025)

    # Step 1: Extract dates using regex (deterministic - this is our source of truth)
    found_dates = extract_dates_with_regex(email_text, school_year_start)

    if not found_dates:
        return []

    # Step 2: Use LLM to create descriptive titles for each date
    dates_info = "\n".join([
        f"- Date: {d['date']}, Time: {d['time'] or 'all-day'}, Context: \"{d['context'][:100]}\""
        for d in found_dates
    ])

    prompt = f"""Create a short descriptive calendar title for each event below.

Email Subject: {email_subject or 'Unknown'}

Events found:
{dates_info}

Return a JSON object mapping each date to a title:
{{{", ".join([f'"{d["date"]}": "Event title"' for d in found_dates])}}}

Rules:
- Include context (e.g., "MCAS", "Art Show", school name)
- Be concise (under 50 chars)
- Examples: "MCAS ELA Testing", "Art Show Kit Pickup", "Early Release Day"
"""

    # Try to get titles from LLM
    titles_map = {}
    try:
        response = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': temperature},
            format='json'
        )

        # Extract content from response
        content = None
        if hasattr(response, 'message'):
            msg = response.message
            if hasattr(msg, 'content'):
                content = msg.content
            elif isinstance(msg, dict):
                content = msg.get('content')
        if content is None and isinstance(response, dict):
            content = response.get('message', {}).get('content')

        if content:
            titles_map = json.loads(content)
            # Handle nested structure
            if isinstance(titles_map, dict) and 'titles' in titles_map:
                titles_map = titles_map['titles']

    except Exception as e:
        # LLM failed - that's okay, we'll use fallback titles
        pass

    # Step 3: Build events using regex dates (source of truth) + LLM titles (nice to have)
    events = []
    for d in found_dates:
        date_str = d['date']
        time_str = d['time']
        context = d['context']

        # Try to get title from LLM, fall back to extracting from context
        title = titles_map.get(date_str) if isinstance(titles_map, dict) else None

        if not title or not isinstance(title, str):
            # Fallback: extract title from context
            # Remove date/time patterns and clean up
            title = context
            title = re.sub(r'\d{1,2}/\d{1,2}(/\d{2,4})?', '', title)
            title = re.sub(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2}', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\d{1,2}:\d{2}\s*(am|pm)?', '', title, flags=re.IGNORECASE)
            title = re.sub(r'at\s+\d{1,2}\s*(am|pm)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'^[\s\-–:*•]+', '', title)
            title = re.sub(r'[\s\-–:]+$', '', title)
            title = title.strip()

            # Add subject context if title is too short
            if len(title) < 5 and email_subject:
                title = f"{email_subject}: {title}" if title else email_subject

        events.append({
            'title': title[:80] if title else 'Event',
            'date': date_str,
            'time': time_str,
            'description': context,
            'grade_level': None
        })

    return events


def _process_single_email(email: dict, config: dict) -> tuple:
    """Process a single email and return (filename, events)."""
    events = extract_events_with_ollama(
        email_text=email['body'],
        email_subject=email['subject'],
        config=config
    )

    # Add source info to each event
    for event in events:
        event['source'] = 'email'
        event['source_file'] = email['filename']

    return (email['filename'], email['subject'], events)


def extract_events_from_email_files(config: dict) -> list:
    """
    Main orchestration function: read local email files and extract events.
    Uses parallel processing for faster extraction with multiple emails.

    Returns list of event dicts ready for calendar generation.
    """
    print("\n" + "=" * 50)
    print("EMAIL PARSING (Local Files + Ollama)")
    print("=" * 50)

    email_config = config.get('email', {})
    input_folder = email_config.get('input_folder', 'input_emails/')

    # Number of parallel workers (default: 4, configurable)
    max_workers = email_config.get('parallel_workers', 4)

    # Check Ollama availability
    if not check_ollama_available(config):
        print("Skipping email parsing due to Ollama error")
        return []

    # Read email files
    print(f"\nReading emails from '{input_folder}'...")
    emails = read_email_files(input_folder)

    if not emails:
        print("No emails to process")
        return []

    all_events = []

    # Use parallel processing if multiple emails
    if len(emails) > 1:
        print(f"Processing {len(emails)} email(s) in parallel (max {max_workers} workers)...\n")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(_process_single_email, email, config): email
                for email in emails
            }

            # Collect results as they complete
            for future in as_completed(futures):
                filename, subject, events = future.result()
                print(f"  {filename}: {len(events)} event(s)")
                all_events.extend(events)
    else:
        # Single email - no need for parallel processing
        print(f"Processing {len(emails)} email(s) with Ollama...\n")
        for email in emails:
            print(f"  {email['filename']}...")
            events = extract_events_with_ollama(
                email_text=email['body'],
                email_subject=email['subject'],
                config=config
            )
            if events:
                for event in events:
                    event['source'] = 'email'
                    event['source_file'] = email['filename']
                all_events.extend(events)
            print(f"    Found {len(events)} event(s)")

    print(f"\n✓ Extracted {len(all_events)} event(s) from email files")

    return all_events


def convert_email_events_to_calendar_format(email_events: list, config: dict) -> list:
    """
    Convert Ollama-extracted events to the format used by the calendar generator.

    Matches the format from parse_events(): title, date, start_time, end_time, description
    """
    calendar_events = []

    for event in email_events:
        try:
            # Parse date
            event_date = datetime.strptime(event['date'], '%Y-%m-%d')

            # Parse time if available
            start_time = None
            end_time = None
            if event.get('time') and event['time'] not in ('null', None, ''):
                try:
                    time_str = event['time']
                    if ':' in time_str:
                        time_parts = time_str.split(':')
                        hour = int(time_parts[0])
                        minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                        start_time = event_date.replace(hour=hour, minute=minute)
                        end_time = start_time + timedelta(hours=1)
                except (ValueError, IndexError):
                    pass

            # Build description
            description_parts = []
            if event.get('description') and event['description'] not in ('null', None):
                description_parts.append(event['description'])
            if event.get('grade_level') and event['grade_level'] not in ('null', None):
                description_parts.append(f"Grade: {event['grade_level']}")
            if event.get('source_file'):
                description_parts.append(f"Source: {event['source_file']}")

            calendar_events.append({
                'title': event['title'],
                'date': event_date,
                'start_time': start_time,
                'end_time': end_time,
                'description': '\n'.join(description_parts),
                'original': f"[Email] {event.get('source_file', 'unknown')}"
            })

        except (ValueError, KeyError) as e:
            print(f"Warning: Error converting event: {e}")
            continue

    return calendar_events
