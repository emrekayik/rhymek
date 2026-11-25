"""
rhymek: NLP Toolkit for Turkish Songs.
Genius API entegrasyonu, sanatçı ID yönetimi ve şarkı sözü veri seti toplayıcı.
"""

from rhymek.client import get_genius_client
from rhymek.artists import (
    DEFAULT_ARTISTS_FILE,
    load_artists,
    save_artists,
    add_artist,
    remove_artist,
    search_genius_artists,
)
from rhymek.songs import (
    DEFAULT_FETCH_STATE,
    DEFAULT_LYRICS_DIR,
    DEFAULT_SONGS_JSONL,
    count_saved_songs_for_artist,
    fetch_songs_for_artist,
    fetch_all_artists_songs,
    get_downloaded_songs_for_artist,
    load_fetch_state,
    load_songs_from_jsonl,
    get_saved_song_ids,
    save_fetch_state,
)
from rhymek.tui import launch_tui
from rhymek.cli import main, app

__all__ = [
    "get_genius_client",
    "load_artists",
    "save_artists",
    "add_artist",
    "remove_artist",
    "search_genius_artists",
    "fetch_songs_for_artist",
    "fetch_all_artists_songs",
    "get_downloaded_songs_for_artist",
    "launch_tui",
    "DEFAULT_ARTISTS_FILE",
    "DEFAULT_FETCH_STATE",
    "DEFAULT_LYRICS_DIR",
    "DEFAULT_SONGS_JSONL",
    "load_songs_from_jsonl",
    "load_fetch_state",
    "save_fetch_state",
    "get_saved_song_ids",
    "count_saved_songs_for_artist",
    "main",
    "app",
]
