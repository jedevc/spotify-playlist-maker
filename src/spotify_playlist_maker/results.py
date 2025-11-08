"""
Data structures for passing analysis results.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class YearMonth:
    """Represents a year-month combination."""

    year: int
    month: int

    def __str__(self) -> str:
        """Format as YYYY-MM string."""
        return f"{self.year:04d}-{self.month:02d}"

    def __lt__(self, other: "YearMonth") -> bool:
        """Enable sorting by chronological order."""
        return (self.year, self.month) < (other.year, other.month)


@dataclass
class Song:
    """Represents a song with its metadata."""

    name: str
    artist: str
    uri: str


@dataclass
class Playlist:
    """Represents a playlist with its metadata."""

    name: str
    id: str
    track_count: int


@dataclass
class Diff:
    """Results of comparing liked songs vs playlist for a date."""

    date: YearMonth
    playlist: Optional[Playlist]
    liked_songs: List[Song]
    playlist_songs: List[Song]

    @property
    def liked_uris(self) -> set:
        """URIs of liked songs."""
        return {song.uri for song in self.liked_songs}

    @property
    def playlist_uris(self) -> set:
        """URIs of playlist songs."""
        return {song.uri for song in self.playlist_songs}

    @property
    def liked_only_uris(self) -> set:
        """URIs only in liked songs."""
        return self.liked_uris - self.playlist_uris

    @property
    def playlist_only_uris(self) -> set:
        """URIs only in playlist."""
        return self.playlist_uris - self.liked_uris

    @property
    def liked_only_songs(self) -> List[Song]:
        """Songs liked but not in playlist."""
        liked_dict = {song.uri: song for song in self.liked_songs}
        return [liked_dict[uri] for uri in self.liked_only_uris]

    @property
    def playlist_only_songs(self) -> List[Song]:
        """Songs in playlist but not liked."""
        playlist_dict = {song.uri: song for song in self.playlist_songs}
        return [playlist_dict[uri] for uri in self.playlist_only_uris]

    @property
    def is_perfect_match(self) -> bool:
        """True if liked songs and playlist are perfectly in sync."""
        return len(self.liked_only_uris) == 0 and len(self.playlist_only_uris) == 0

    def format_diff(self) -> str:
        """Generate a formatted diff display with emojis and styling."""
        lines = []

        # Header
        lines.append(f"\n🔍 Comparing {self.date}:")
        lines.append("-" * 40)

        # Check if playlist exists
        if self.playlist is None:
            lines.append("  ⚠️  No matching monthly playlist found")
            lines.append(f"  📊 Liked songs: {len(self.liked_songs)}")
            if self.liked_songs:
                lines.append(
                    f"\n  ➕ Songs that would need a new playlist ({len(self.liked_songs)}):"
                )
                for song in sorted(self.liked_songs, key=lambda s: s.name):
                    lines.append(f"     • {song.name} - {song.artist}")
        else:
            # Summary stats
            lines.append(f"  📊 Liked songs: {len(self.liked_songs)}")
            lines.append(f"     Playlist songs: {len(self.playlist_songs)}")
            lines.append(f"     In both: {len(self.liked_uris & self.playlist_uris)}")

            # Songs missing from playlist (liked but not in playlist)
            if self.liked_only_songs:
                lines.append(
                    f"\n  ➕ Songs liked but NOT in playlist ({len(self.liked_only_songs)}):"
                )
                for song in sorted(self.liked_only_songs, key=lambda s: s.name):
                    lines.append(f"     • {song.name} - {song.artist}")

            # Songs in playlist but not liked
            if self.playlist_only_songs:
                lines.append(
                    f"\n  ➖ Songs in playlist but NOT liked ({len(self.playlist_only_songs)}):"
                )
                for song in sorted(self.playlist_only_songs, key=lambda s: s.name):
                    lines.append(f"     • {song.name} - {song.artist}")

            # Perfect match indicator
            if self.is_perfect_match:
                lines.append("  ✅ Perfect match! All songs are in sync.")

        return "\n".join(lines)


@dataclass
class AnalysisResults:
    """Complete results of the Spotify analysis."""

    songs_by_date: Dict[YearMonth, List[Song]]
    monthly_playlists: Dict[YearMonth, Playlist]
    diffs: Dict[YearMonth, Diff]
    target_dates: Optional[List[YearMonth]]
    username: str
