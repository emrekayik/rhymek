import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import lyricsgenius

from rhymek.client import get_genius_client

DEFAULT_ARTISTS_FILE = Path("data/artists.json")


def load_artists(filepath: Union[str, Path] = DEFAULT_ARTISTS_FILE) -> List[Dict[str, Any]]:
    """
    Belirtilen JSON dosyasından sanatçı listesini okur.
    Dosya yoksa boş liste döndürür.
    """
    path = Path(filepath)
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "artists" in data:
                return data["artists"]
            return []
    except json.JSONDecodeError:
        return []


def save_artists(artists: List[Dict[str, Any]], filepath: Union[str, Path] = DEFAULT_ARTISTS_FILE) -> None:
    """
    Sanatçı listesini düzenli JSON formatında kaydeder.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(artists, f, ensure_ascii=False, indent=2)


def search_genius_artists(
    query: str,
    max_results: int = 5,
    genius: Optional[lyricsgenius.Genius] = None,
) -> List[Dict[str, Any]]:
    """
    Genius API üzerinde sanatçı araması yapar ve eşleşen sanatçıların ID ve isimlerini döner.
    """
    client = genius or get_genius_client(verbose=False)
    results = client.search_artists(query, per_page=max_results)
    hits = []
    for section in results.get("sections", []):
        for hit in section.get("hits", []):
            result = hit.get("result", {})
            hits.append(
                {
                    "id": result.get("id"),
                    "name": result.get("name"),
                    "url": result.get("url"),
                    "image_url": result.get("image_url"),
                }
            )
    return hits


def add_artist(
    name_or_query: str,
    artist_id: Optional[int] = None,
    filepath: Union[str, Path] = DEFAULT_ARTISTS_FILE,
    genius: Optional[lyricsgenius.Genius] = None,
) -> Dict[str, Any]:
    """
    Sanatçıyı ID'siyle birlikte listeye ekler.
    ID verilmemişse Genius API'den arayıp doğrular.
    """
    artists = load_artists(filepath)

    # Eğer ID verilmemişse Genius'tan sorgula
    if artist_id is None:
        hits = search_genius_artists(name_or_query, max_results=3, genius=genius)
        if not hits:
            raise ValueError(f"'{name_or_query}' için Genius üzerinde sanatçı bulunamadı!")
        # İlk en yakın eşleşmeyi seç
        selected = hits[0]
        artist_id = selected["id"]
        artist_name = selected["name"]
    else:
        # ID doğrudan verildiyse ismi doğrulamak veya korumak için
        artist_name = name_or_query

    # Listede zaten var mı kontrol et (id veya isim çakışması)
    for artist in artists:
        if artist.get("id") == artist_id:
            # Zaten mevcut
            return artist

    new_artist = {
        "id": artist_id,
        "name": artist_name,
    }
    artists.append(new_artist)
    save_artists(artists, filepath)
    return new_artist


def remove_artist(
    identifier: Union[int, str],
    filepath: Union[str, Path] = DEFAULT_ARTISTS_FILE,
) -> bool:
    """
    ID veya isme göre sanatçıyı dosyadan siler.
    """
    artists = load_artists(filepath)
    original_len = len(artists)

    filtered = [
        a for a in artists
        if a.get("id") != identifier and str(a.get("name", "")).lower() != str(identifier).lower()
    ]

    if len(filtered) < original_len:
        save_artists(filtered, filepath)
        return True
    return False
