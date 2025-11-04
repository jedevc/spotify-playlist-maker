import calendar
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, TypeVar

import spotipy

from .constants import BATCH_SIZE
from .parser import extract_month_year_from_playlist
from .results import AnalysisResults, Diff, Playlist, Song, YearMonth

T = TypeVar("T")


class SpotifyAnalyzer:
    """Main class for analyzing Spotify liked songs and playlists."""

    sp: spotipy.Spotify
    user: Dict[str, Any]
    playlist_format: str

    def __init__(
        self, spotify_client: spotipy.Spotify, playlist_format: str = "[%Y] %B"
    ):
        self.sp = spotify_client
        self.playlist_format = playlist_format

        user = self.sp.current_user()
        if user is None:
            raise Exception("Failed to fetch current user info")
        self.user = user  # type: ignore # spotipy doesn't have proper typing

    def _create_song_from_track(self, track: Dict[str, Any]) -> Song:
        """Create Song object from Spotify track data."""
        return Song(
            name=track["name"],
            artist=", ".join([artist["name"] for artist in track["artists"]]),
            uri=track["uri"],
        )

    def _paginate_spotify_results(
        self,
        initial_results: Dict[str, Any],
        process_item_func: Callable[[Dict[str, Any]], Optional[T]],
    ) -> List[T]:
        """Generic pagination handler for Spotify API results."""
        items = []
        results = initial_results

        while results:
            for item in results["items"]:
                processed = process_item_func(item)
                if processed:
                    items.append(processed)

            results = self.sp.next(results) if results["next"] else None  # type: ignore

        return items

    def analyze(
        self, target_dates: Optional[List[YearMonth]] = None
    ) -> AnalysisResults:
        """Perform complete analysis and return results."""
        # Get user info
        username = self.user["display_name"] or self.user["id"]

        # Get liked songs
        songs_by_date = self.get_liked_songs_by_date(target_dates)

        if not songs_by_date:
            return AnalysisResults(
                songs_by_date={},
                monthly_playlists={},
                diffs={},
                target_dates=target_dates,
                username=username,
            )

        # Get playlists
        all_playlists = self.get_user_playlists()
        monthly_playlists = self.find_monthly_playlists(all_playlists)

        # Perform comparisons
        diffs = self.compare_all_dates(songs_by_date, monthly_playlists)

        return AnalysisResults(
            songs_by_date=songs_by_date,
            monthly_playlists=monthly_playlists,
            diffs=diffs,
            target_dates=target_dates,
            username=username,
        )

    def get_liked_songs_by_date(
        self, target_dates: Optional[List[YearMonth]] = None
    ) -> Dict[YearMonth, List[Song]]:
        """Fetch liked songs and group them by year-month.

        Args:
            target_dates: List of YearMonth objects to filter for

        Returns:
            Dictionary mapping YearMonth objects to lists of songs
        """
        liked_songs = defaultdict(list)
        total_songs = 0

        # Determine oldest date for optimization
        oldest_date = self._get_oldest_target_date(target_dates)

        results = self.sp.current_user_saved_tracks(limit=BATCH_SIZE)

        while results:
            should_continue = False
            found_songs_in_batch = False

            for item in results["items"]:
                track = item["track"]
                added_at = item["added_at"]

                # Parse timestamp and check date constraints
                added_date = datetime.fromisoformat(added_at.replace("Z", "+00:00"))
                song_date = added_date.date()
                year_month = YearMonth(added_date.year, added_date.month)

                # Early termination optimization
                if oldest_date and song_date < oldest_date:
                    break  # This will break out of the inner loop only

                # Filter by target dates if specified
                if target_dates and year_month not in target_dates:
                    if oldest_date and song_date >= oldest_date:
                        should_continue = True
                    continue

                # Extract song information
                song = self._create_song_from_track(track)

                liked_songs[year_month].append(song)
                total_songs += 1
                found_songs_in_batch = True

                should_continue = True

            # If we hit the oldest date cutoff and found no songs, stop completely
            if oldest_date and not should_continue and not found_songs_in_batch:
                break

            # Get next batch
            if results["next"]:
                results = self.sp.next(results)
            else:
                break

        return dict(liked_songs)

    def _get_oldest_target_date(
        self, target_dates: Optional[List[YearMonth]]
    ) -> Optional[date]:
        """Calculate the oldest date we need to fetch based on target dates."""
        if not target_dates:
            return None

        date_objects = [date(ym.year, ym.month, 1) for ym in target_dates]
        oldest_date = min(date_objects)
        return oldest_date

    def get_user_playlists(self) -> List[Playlist]:
        """Fetch all user-owned playlists."""

        def process_playlist(playlist: Dict[str, Any]) -> Optional[Playlist]:
            if playlist["owner"]["id"] == self.user["id"]:
                return Playlist(
                    name=playlist["name"],
                    id=playlist["id"],
                    track_count=playlist["tracks"]["total"],
                )
            return None

        results = self.sp.current_user_playlists(limit=BATCH_SIZE)
        return self._paginate_spotify_results(results, process_playlist)

    def get_playlist_tracks(self, playlist_id: str) -> List[Song]:
        """Fetch all tracks from a specific playlist."""

        def process_track_item(item: Dict[str, Any]) -> Optional[Song]:
            if item["track"] and item["track"]["type"] == "track":
                return self._create_song_from_track(item["track"])
            return None

        results = self.sp.playlist_tracks(playlist_id, limit=BATCH_SIZE)
        return self._paginate_spotify_results(results, process_track_item)

    def find_monthly_playlists(
        self, all_playlists: List[Playlist]
    ) -> Dict[YearMonth, Playlist]:
        """Identify monthly playlists from user's playlist collection."""
        monthly_playlists = {}

        for playlist in all_playlists:
            month_year = extract_month_year_from_playlist(playlist.name)
            if month_year:
                year, month = month_year
                year_month = YearMonth(year, month)
                monthly_playlists[year_month] = playlist

        return monthly_playlists

    def compare_all_dates(
        self,
        songs_by_date: Dict[YearMonth, List[Song]],
        monthly_playlists: Dict[YearMonth, Playlist],
    ) -> Dict[YearMonth, Diff]:
        """Compare liked songs vs playlists for all dates."""
        diffs = {}

        for year_month, liked_songs in songs_by_date.items():
            if year_month in monthly_playlists:
                playlist = monthly_playlists[year_month]

                playlist_songs = self.get_playlist_tracks(playlist.id)
                diff = Diff(
                    date=year_month,
                    playlist=playlist,
                    liked_songs=liked_songs,
                    playlist_songs=playlist_songs,
                )
            else:
                # No matching playlist - create diff with empty playlist
                diff = Diff(
                    date=year_month,
                    playlist=None,
                    liked_songs=liked_songs,
                    playlist_songs=[],
                )

            diffs[year_month] = diff

        return diffs

    def apply_diff_to_playlist(
        self, playlist_id: str, missing_songs: List[Song]
    ) -> None:
        """Add missing songs to the playlist."""
        if not missing_songs:
            return

        # Extract URIs for the songs to add
        uris_to_add = [song.uri for song in missing_songs]

        for i in range(0, len(uris_to_add), BATCH_SIZE):
            batch = uris_to_add[i : i + BATCH_SIZE]
            try:
                self.sp.playlist_add_items(playlist_id, batch)
            except Exception as e:
                print(f"   ❌ Error adding batch: {e}")

    def create_playlist_for_date(self, date: YearMonth) -> str:
        """Create a new playlist for the given date and return its ID."""
        # Create a datetime object for strftime formatting
        try:
            # Create datetime object with the 1st day of the month
            dt = datetime(date.year, date.month, 1)
            playlist_name = dt.strftime(self.playlist_format)
        except (ValueError, OSError):
            # Fallback to simple format if strftime fails
            playlist_name = str(date)

        # Create the playlist
        playlist = self.sp.user_playlist_create(
            user=self.user["id"],
            name=playlist_name,
            public=False,  # Make it private
            description=f"Songs liked during {playlist_name}",
        )

        return playlist["id"]

    def apply_diffs(self, diffs: List[Diff]) -> None:
        """Apply a list of diffs to their respective playlists."""
        if not diffs:
            return

        # Count songs that need to be added (including those needing new playlists)
        total_songs_to_add = sum(
            len(diff.liked_only_songs) for diff in diffs if diff.liked_only_songs
        )
        if total_songs_to_add == 0:
            return

        for diff in diffs:
            if not diff.liked_only_songs:
                continue

            if diff.playlist is not None:
                # Existing playlist - add missing songs
                self.apply_diff_to_playlist(diff.playlist.id, diff.liked_only_songs)
            else:
                # No playlist exists - create one and add all liked songs
                playlist_id = self.create_playlist_for_date(diff.date)
                self.apply_diff_to_playlist(playlist_id, diff.liked_only_songs)
