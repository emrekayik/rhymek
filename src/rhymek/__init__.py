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
    DEFAULT_LYRICS_DIR,
    fetch_songs_for_artist,
    fetch_all_artists_songs,
)
from rhymek.cli import main

__all__ = [
    "get_genius_client",
    "load_artists",
    "save_artists",
    "add_artist",
    "remove_artist",
    "search_genius_artists",
    "fetch_songs_for_artist",
    "fetch_all_artists_songs",
    "DEFAULT_ARTISTS_FILE",
    "DEFAULT_LYRICS_DIR",
    "main",
]
