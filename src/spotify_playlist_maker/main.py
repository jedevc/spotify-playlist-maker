"""
Spotify liked songs analyzer and playlist comparison tool.

Analyzes Spotify liked songs, groups them by month, and compares them with
existing monthly playlists to identify sync differences.

Before running:
1. Create a Spotify app at https://developer.spotify.com/dashboard
2. Set SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI environment variables
"""

import argparse
import os
from typing import List, Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .analyzer import SpotifyAnalyzer
from .constants import SPOTIFY_SCOPES, CACHE_FILE
from .parser import parse_month_year
from .results import YearMonth


def check_environment_variables() -> bool:
    """Check if required Spotify API environment variables are set."""
    required_vars = [
        "SPOTIPY_CLIENT_ID",
        "SPOTIPY_CLIENT_SECRET",
        "SPOTIPY_REDIRECT_URI",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   {var}")
        print("\nPlease set these variables before running the script.")
        return False

    return True


def create_spotify_client() -> spotipy.Spotify:
    """Create and return a Spotify client with required scopes and caching."""
    auth_manager = SpotifyOAuth(
        scope=SPOTIFY_SCOPES,
        cache_path=CACHE_FILE,
        show_dialog=False,  # Don't force re-auth every time
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Analyze Spotify liked songs grouped by month",
        epilog="Examples:\n"
        "  %(prog)s                           # Get all liked songs\n"
        "  %(prog)s 'March 2025'              # Songs from March 2025\n"
        "  %(prog)s '03-25' '04-25'           # Songs from March and April 2025\n"
        "  %(prog)s 'march 2024' '2024-04'    # Mixed formats work too\n"
        "  %(prog)s 'Oct 2023 - Mar 2024'     # Range: October 2023 through March 2024\n"
        "  %(prog)s --apply-diff 'March 2025' # Apply missing songs to playlist\n"
        "  %(prog)s --playlist-format '%%B %%Y' # Format: 'March 2025'\n"
        "  %(prog)s --playlist-format '📅 %%Y-%%m' # Format: '📅 2025-03'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "months",
        nargs="*",
        help="Month/year combinations or ranges (e.g., 'March 2025', '03-25', 'Oct 2023 - Mar 2024')",
    )
    parser.add_argument(
        "--apply-diff",
        action="store_true",
        help="🚨 DANGER: Apply diff by adding missing songs to playlists. USE WITH EXTREME CAUTION! 🚨",
    )
    parser.add_argument(
        "--playlist-format",
        default="[%Y] %B",
        help="strftime format for playlist names (default: '[%%Y] %%B' -> '[2025] March')",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    # Parse target dates if provided
    target_dates: Optional[List[YearMonth]] = None
    if args.months:
        target_dates = []

        for month_str in args.months:
            try:
                year_month_tuples = parse_month_year(month_str)
                target_dates.extend(
                    YearMonth(year, month) for year, month in year_month_tuples
                )
            except ValueError as e:
                print(f"❌ {e}")
                return

    # Check environment and create client
    if not check_environment_variables():
        return

    try:
        sp = create_spotify_client()
        analyzer = SpotifyAnalyzer(sp, args.playlist_format)

        # Perform analysis
        results = analyzer.analyze(target_dates)

        # Print diffs only
        for diff in results.diffs.values():
            print(diff.format_diff())

        if all((diff.is_perfect_match for diff in results.diffs.values())):
            print("✅ All playlists are in sync with liked songs!")
            return

        if not args.apply_diff:
            try:
                if input("Apply diff? type yes to continue: ") != "yes":
                    print("❌ Aborting without applying diffs.")
                    return
            except KeyboardInterrupt:
                print("\n❌ Interrupted by user. Aborting without applying diffs.")
                return

        diffs_list = list(results.diffs.values())
        analyzer.apply_diffs(diffs_list)

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
