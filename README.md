# Spotify Playlist Maker

Sync your Spotify liked songs into monthly playlists automatically.

> [!WARNING]
>
> This whole thing is a vibe-coded mess. Use at your own risk :)

## Setup

1. Create a Spotify app at [developer.spotify.com](https://developer.spotify.com/dashboard)
2. Set environment variables:

   ```bash
   export SPOTIPY_CLIENT_ID="your_client_id"
   export SPOTIPY_CLIENT_SECRET="your_client_secret"  
   export SPOTIPY_REDIRECT_URI="http://localhost:8080"
   ```

3. Install: `uv sync`

## Usage

```bash
# Show diffs for all months
uv run python -m spotify_playlist_maker

# Specific months or ranges
uv run python -m spotify_playlist_maker "March 2025" "Oct 2023 - Dec 2023"

# Apply changes (creates/updates playlists)
uv run python -m spotify_playlist_maker "March 2025" --apply-diff

# Custom playlist format
uv run python -m spotify_playlist_maker --playlist-format "📅 %B %Y" --apply-diff
```

## Development

- Install dev deps: `uv sync --dev`
- Type check: `uv run mypy src/ --ignore-missing-imports`
- Format: `uv run black src/`
