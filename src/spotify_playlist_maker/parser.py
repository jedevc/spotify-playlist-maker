"""
Date and playlist name parsing utilities.
"""

import re
from calendar import month_abbr, month_name
from typing import Dict, List, Optional, Tuple

from dateutil import parser as date_parser


def parse_month_year(month_str: str) -> List[Tuple[int, int]]:
    """Parse various month/year formats and return list of (year, month) tuples.

    Supports both single dates and ranges:
    - "March 2025" -> [(2025, 3)]
    - "October 2023 - March 2024" -> [(2023, 10), (2023, 11), (2023, 12), (2024, 1), (2024, 2), (2024, 3)]

    Args:
        month_str: Month/year string or range in various formats

    Returns:
        List of (year, month) tuples

    Raises:
        ValueError: If the string cannot be parsed
    """
    # Check if it's a range (contains " - ")
    if " - " in month_str:
        try:
            start_str, end_str = month_str.split(" - ", 1)
            start_year, start_month = _parse_single_date(start_str.strip())
            end_year, end_month = _parse_single_date(end_str.strip())
            return _generate_month_range(start_year, start_month, end_year, end_month)
        except ValueError as e:
            raise ValueError(
                f"Could not parse range '{month_str}'. Both parts must be valid dates. {e}"
            )
    else:
        # Single date
        year, month = _parse_single_date(month_str)
        return [(year, month)]


def _parse_single_date(month_str: str) -> Tuple[int, int]:
    """Parse a single month/year string and return (year, month) tuple."""
    try:
        parsed_date = date_parser.parse(month_str, fuzzy=True)
        return parsed_date.year, parsed_date.month
    except (ValueError, TypeError):
        raise ValueError(
            f"Could not parse '{month_str}' as a month/year. "
            f"Try formats like 'March 2025', '03-25', '2024-03'"
        )


def _generate_month_range(
    start_year: int, start_month: int, end_year: int, end_month: int
) -> List[Tuple[int, int]]:
    """Generate all (year, month) tuples in the inclusive range from start to end."""
    result = []

    # Validate that start <= end
    if (start_year, start_month) > (end_year, end_month):
        raise ValueError(
            f"Start date {start_year}-{start_month:02d} is after end date {end_year}-{end_month:02d}"
        )

    current_year = start_year
    current_month = start_month

    while (current_year, current_month) <= (end_year, end_month):
        result.append((current_year, current_month))

        # Move to next month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return result


def _build_month_names_dict() -> Dict[str, int]:
    """Build a mapping of month names/abbreviations to month numbers."""
    month_names = {}
    for i, name in enumerate(month_name[1:], 1):  # Skip empty first element
        month_names[name.lower()] = i
    for i, abbr in enumerate(month_abbr[1:], 1):  # Skip empty first element
        month_names[abbr.lower()] = i
    return month_names


def extract_month_year_from_playlist(playlist_name: str) -> Optional[Tuple[int, int]]:
    """Extract (year, month) from playlist name using generous pattern matching.

    Args:
        playlist_name: Name of the playlist

    Returns:
        Tuple of (year, month) if found, None otherwise
    """
    month_names = _build_month_names_dict()

    # Patterns for different playlist naming conventions
    patterns = [
        r"\[(\d{4})\]\s*([a-zA-Z]+)",  # [2025] March, [2025] MON
        r"([a-zA-Z]+)\s+(\d{4})",  # March 2025, MON 2025
        r"(\d{4})[/\-]\s*([a-zA-Z]+)",  # 2025/March, 2025-MON
        r"(\d{1,2})[/\-\s]+(\d{4})",  # 03 2025, 03-2025
        r"(\d{4})[/\-](\d{1,2})",  # 2025-03, 2025/03
    ]

    for pattern in patterns:
        match = re.search(pattern, playlist_name, re.IGNORECASE)
        if not match:
            continue

        group1, group2 = match.groups()
        year, month = _parse_year_month_groups(group1, group2, month_names)

        if year and month and 1 <= month <= 12:
            return (year, month)

    return None


def _parse_year_month_groups(
    group1: str, group2: str, month_names: Dict[str, int]
) -> Tuple[Optional[int], Optional[int]]:
    """Parse two regex groups to determine year and month."""
    year: Optional[int] = None
    month: Optional[int] = None

    # Determine which group is year and which is month
    if len(group1) == 4 and group1.isdigit():  # group1 is year
        year = int(group1)
        if group2.isdigit():  # MM format
            month = int(group2)
        else:  # month name
            month = month_names.get(group2.lower())
    elif len(group2) == 4 and group2.isdigit():  # group2 is year
        year = int(group2)
        if group1.isdigit():  # MM format
            month = int(group1)
        else:  # month name
            month = month_names.get(group1.lower())

    return year, month
