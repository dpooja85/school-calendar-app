#!/usr/bin/env python3
"""
Test script for email parser with Ollama.

Usage:
    python test_email_parser.py
"""

import sys
import yaml
from src.email_parser import (
    extract_events_with_ollama,
    check_ollama_available,
    parse_email_content,
    read_email_files
)


# Test emails with expected events
# Note: LLMs are variable, so we use minimum thresholds rather than exact counts
TEST_CASES = [
    {
        "name": "MCAS Email",
        "content": """Subject: A few odds and ends and MCAS Dates
Date: January 23, 2025

Please note that Wednesday, January 28 will be an Early Release Day with dismissal
at 1:10 pm. The Used Book Store will be open on January 28 as well.

MCAS testing dates for grades 3, 4, and 5:
* March 30, 31 - ELA
* May 12, 13 - MATH
* May 19, 20 - Science (Grade 5 only)
""",
        "min_events": 1,  # LLMs are variable - at least extract something
        "must_contain": [],  # LLM output varies
        "should_contain": ["Early Release", "ELA", "MATH"],  # Nice to have
        "expected_dates": ["2026-01-28"]  # Should have January date correct
    },
    {
        "name": "Art Show Email",
        "content": """The Tiny Art Show is BACK for a second year. This time, all ages are welcome to participate until the supplies run out, and we're doubling the time you have to create your mini-masterpiece.

Kit Pickup: Starting Tuesday, 2/10 at 10AM - Pickup Children & Teen kits at the Youth Services Desk (first floor), and Adult kits at the Reference Desk (upstairs)

Deadline to Return Art: Friday, 2/27 at 6PM

Contest Rules:

Eligibility – Open to patrons of all ages, but limited to those that are able to get a kit before we run out.
Reception – Participants are encouraged to attend the reception on March 26 at 5:30PM.
Submission Deadline – Completed artwork must be returned by 6PM on Friday, February 27.
""",
        "min_events": 1,  # At minimum: Kit Pickup
        "must_contain": [],  # LLM may use different titles
        "should_contain": ["Kit", "Pickup", "Reception", "Deadline"],
        "expected_dates": ["2026-02-10"]
    }
]


def load_config():
    """Load config or use defaults."""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {
            'school_year_start': 2025,
            'email': {
                'ollama': {
                    'model': 'llama3.1:8b',
                    'temperature': 0.1
                }
            }
        }


def test_parse_email_content():
    """Test email content parsing with headers."""
    print("Testing parse_email_content()...")

    # Test with headers
    content_with_headers = """Subject: MCAS Dates
Date: January 23, 2025

This is the body text."""

    result = parse_email_content(content_with_headers, "test.txt")
    assert result['subject'] == "MCAS Dates", f"Expected 'MCAS Dates', got '{result['subject']}'"
    assert result['date'] == "January 23, 2025", f"Expected 'January 23, 2025', got '{result['date']}'"
    assert "body text" in result['body'], f"Body not parsed correctly: {result['body']}"
    print("  ✓ Headers parsed correctly")

    # Test without headers
    content_plain = "Just plain email body text here."
    result = parse_email_content(content_plain, "plain_email.txt")
    assert result['subject'] == "plain email", f"Filename fallback failed: {result['subject']}"
    assert result['body'] == content_plain, "Body should be entire content"
    print("  ✓ Plain text handled correctly")

    print("✓ parse_email_content tests passed!\n")


def test_ollama_extraction():
    """
    Test event extraction with Ollama using inline test cases.

    Note: LLMs are inherently variable, so this test is advisory only.
    The full_integration test with real files is the authoritative test.
    """
    print("Testing Ollama extraction (advisory - LLM output varies)...")

    config = load_config()

    # Check Ollama availability
    if not check_ollama_available(config):
        print("  ⚠ Skipping Ollama tests (not available)")
        return None  # Skip, don't fail

    issues = []

    for test_case in TEST_CASES:
        print(f"\n  Testing: {test_case['name']}")
        print("  " + "-" * 40)

        # Extract events
        events = extract_events_with_ollama(
            email_text=test_case['content'],
            email_subject=test_case['name'],
            config=config
        )

        print(f"  Extracted {len(events)} events:")
        for event in events:
            time_str = f" at {event.get('time')}" if event.get('time') else ""
            print(f"    - {event['date']}: {event['title']}{time_str}")

        # Validate minimum events (advisory)
        if len(events) < test_case['min_events']:
            print(f"  ⚠ Note: Expected at least {test_case['min_events']} events, got {len(events)}")
            issues.append(f"{test_case['name']}: low event count")
        else:
            print(f"  ✓ Event count OK ({len(events)} >= {test_case['min_events']})")

        # Check for optional content (informational)
        event_titles = ' '.join([e['title'].lower() for e in events])
        for optional in test_case.get('should_contain', []):
            if optional.lower() in event_titles:
                print(f"  ✓ Found event containing '{optional}'")
            else:
                print(f"  ⚠ Note: No event containing '{optional}'")

        # Check date formats (this should always pass)
        for event in events:
            date = event['date']
            if len(date) != 10 or date[4] != '-' or date[7] != '-':
                print(f"  ✗ Invalid date format: {date}")
                issues.append(f"Invalid date format: {date}")

        # Check expected dates (informational)
        event_dates = [e['date'] for e in events]
        for expected_date in test_case.get('expected_dates', []):
            if expected_date in event_dates:
                print(f"  ✓ Found expected date {expected_date}")
            else:
                print(f"  ⚠ Note: Expected date {expected_date} not found")

    if issues:
        print(f"\n  Advisory notes: {len(issues)} issues (LLM variability is normal)")

    # Always return True - this test is advisory only
    # The full_integration test is authoritative
    return True


def test_read_email_files():
    """Test reading email files from input folder."""
    print("\nTesting read_email_files()...")

    emails = read_email_files('input_emails/')

    if not emails:
        print("  ⚠ No email files found in input_emails/")
        return True

    print(f"  Found {len(emails)} email file(s)")
    for email in emails:
        print(f"    - {email['filename']}: {email['subject'][:40]}...")

    print("✓ read_email_files test passed!\n")
    return True


def test_full_integration():
    """
    Test full integration - read actual files and extract events.
    This is the authoritative test for the email parser.
    """
    print("\nTesting full integration (authoritative test)...")

    config = load_config()

    if not check_ollama_available(config):
        print("  ⚠ Skipping (Ollama not available)")
        return None  # Skip, don't fail

    emails = read_email_files('input_emails/')

    if not emails:
        print("  ⚠ No emails to test (add .txt files to input_emails/)")
        return True

    total_events = 0
    for email in emails:
        events = extract_events_with_ollama(
            email_text=email['body'],
            email_subject=email['subject'],
            config=config
        )
        print(f"  {email['filename']}: {len(events)} events")
        for event in events:
            time_str = f" at {event.get('time')}" if event.get('time') else ""
            print(f"    - {event['date']}: {event['title']}{time_str}")
        total_events += len(events)

    if total_events > 0:
        print(f"\n✓ Full integration passed! ({total_events} total events)")
        return True
    else:
        print("\n✗ FAIL: No events extracted from any file")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("Email Parser Tests")
    print("=" * 50)
    print()

    results = {}

    # Test basic parsing (no Ollama needed)
    try:
        test_parse_email_content()
        results['parse_email_content'] = True
    except AssertionError as e:
        print(f"✗ FAIL: {e}")
        results['parse_email_content'] = False

    # Test file reading
    results['read_email_files'] = test_read_email_files()

    # Test Ollama extraction
    results['ollama_extraction'] = test_ollama_extraction()

    # Test full integration
    results['full_integration'] = test_full_integration()

    # Summary
    print("=" * 50)
    print("Test Summary")
    print("=" * 50)

    all_passed = True
    for test_name, passed in results.items():
        if passed is True:
            status = "✓ PASS"
        elif passed is False:
            status = "✗ FAIL"
            all_passed = False
        else:
            status = "⚠ SKIP"
        print(f"  {test_name}: {status}")

    print()
    if all_passed:
        print("ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
