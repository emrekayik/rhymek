import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import lyricsgenius

from rhymek.artists import load_artists
from rhymek.client import get_genius_client

DEFAULT_LYRICS_DIR = Path("data/lyrics")


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Dosya isimlerinde sorun yaratabilecek geçersiz karakterleri temizler.
    """
    # Geçersiz dosya adı karakterlerini alt çizgi ile değiştir
    clean = re.sub(r'[\\/*?:"<>|]', "_", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_length] if len(clean) > max_length else clean


def save_song_files(
    song_data: Dict[str, Any],
    artist_dir: Path,
    save_txt: bool = True,
    save_json: bool = True,
) -> None:
    """
    Şarkı sözünü ve metaverisini dosyaya kaydeder.
    """
    title = song_data.get("title", "isimsiz_sarki")
    safe_title = sanitize_filename(title)
    artist_dir.mkdir(parents=True, exist_ok=True)

    # 1. Metin (.txt) olarak kaydet
    if save_txt:
        txt_path = artist_dir / f"{safe_title}.txt"
        header = [
            f"# Başlık: {song_data.get('title')}",
            f"# Sanatçı: {song_data.get('artist')}",
            f"# Albüm: {song_data.get('album') or '-'}",
            f"# Tarih: {song_data.get('release_date') or song_data.get('year') or '-'}",
            f"# Genius URL: {song_data.get('url') or '-'}",
            "-" * 40,
            "",
        ]
        content = "\n".join(header) + (song_data.get("lyrics") or "")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(content)

    # 2. JSON olarak kaydet
    if save_json:
        json_path = artist_dir / f"{safe_title}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)


def fetch_songs_for_artist(
    artist_id: int,
    artist_name: Optional[str] = None,
    max_songs: Optional[int] = 20,
    sort: str = "popularity",
    output_dir: Union[str, Path] = DEFAULT_LYRICS_DIR,
    include_features: bool = False,
    skip_existing: bool = True,
    genius: Optional[lyricsgenius.Genius] = None,
) -> List[Dict[str, Any]]:
    """
    Verilen artist_id için şarkıları ve sözleri Genius API üzerinden çeker
    ve disk üzerine kaydeder.
    """
    client = genius or get_genius_client()
    output_base = Path(output_dir)

    # Sanatçı adı belirtilmemişse Genius API'den öğren
    if not artist_name:
        artist_info = client.artist(artist_id)
        artist_name = artist_info.get("artist", {}).get("name", f"artist_{artist_id}")

    safe_artist_folder = sanitize_filename(artist_name)
    artist_folder = output_base / safe_artist_folder
    artist_folder.mkdir(parents=True, exist_ok=True)

    print(f"\n[rhymek] '{artist_name}' (ID: {artist_id}) için şarkılar çekiliyor...")

    fetched_songs: List[Dict[str, Any]] = []

    # lyricsgenius ile sanatçının şarkılarını ara
    artist_obj = client.search_artist(
        artist_name=artist_name,
        artist_id=artist_id,
        max_songs=max_songs,
        sort=sort,
        include_features=include_features,
    )

    if not artist_obj or not artist_obj.songs:
        print(f"[rhymek] '{artist_name}' için şarkı bulunamadı.")
        return []

    for song in artist_obj.songs:
        safe_title = sanitize_filename(song.title)
        txt_file = artist_folder / f"{safe_title}.txt"

        if skip_existing and txt_file.exists():
            print(f"  -> Zaten var (atlandı): {song.title}")
            continue

        song_body = getattr(song, "_body", {}) or {}
        song_id = song_body.get("id") or getattr(song, "id", None)
        album_name = None
        if isinstance(song.album, dict):
            album_name = song.album.get("name")
        elif song.album:
            album_name = str(song.album)

        release_date = song_body.get("release_date") or getattr(song, "year", None)

        song_dict = {
            "id": song_id,
            "title": song.title,
            "artist": song.artist,
            "artist_id": artist_id,
            "album": album_name,
            "release_date": release_date,
            "url": song.url,
            "lyrics": song.lyrics,
        }

        save_song_files(song_dict, artist_folder, save_txt=True, save_json=True)
        fetched_songs.append(song_dict)
        print(f"  -> Kaydedildi: {song.title}")

    # Sanatçının tüm çekilen şarkı listesini özet JSON olarak da sakla
    summary_path = artist_folder / "_summary.json"
    summary_data = {
        "artist_id": artist_id,
        "artist_name": artist_name,
        "total_songs_fetched": len(fetched_songs),
        "songs": [
            {
                "id": s["id"],
                "title": s["title"],
                "album": s.get("album"),
                "release_date": s.get("release_date"),
            }
            for s in fetched_songs
        ],
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    print(f"[rhymek] Tamamlandı: {len(fetched_songs)} yeni şarkı kaydedildi ({artist_folder}).")
    return fetched_songs


def fetch_all_artists_songs(
    artists_file: Union[str, Path] = "data/artists.json",
    max_songs_per_artist: Optional[int] = 10,
    sort: str = "popularity",
    output_dir: Union[str, Path] = DEFAULT_LYRICS_DIR,
    genius: Optional[lyricsgenius.Genius] = None,
) -> Dict[str, int]:
    """
    data/artists.json dosyasındaki tüm sanatçıları sırayla gezip şarkılarını çeker.
    """
    artists = load_artists(artists_file)
    if not artists:
        print(f"[rhymek] '{artists_file}' içinde kayıtlı sanatçı bulunamadı!")
        return {}

    client = genius or get_genius_client()
    stats: Dict[str, int] = {}

    print(f"[rhymek] Toplam {len(artists)} sanatçı bulundu. Şarkılar çekiliyor...")

    for artist in artists:
        a_id = artist.get("id")
        a_name = artist.get("name")
        if not a_id:
            print(f"[rhymek] Uyarı: Sanatçı ID bulunamadı ({a_name}), atlanıyor.")
            continue

        try:
            songs = fetch_songs_for_artist(
                artist_id=int(a_id),
                artist_name=a_name,
                max_songs=max_songs_per_artist,
                sort=sort,
                output_dir=output_dir,
                genius=client,
            )
            stats[a_name] = len(songs)
        except Exception as e:
            print(f"[rhymek] '{a_name}' şarkıları çekilirken hata oluştu: {e}")
            stats[a_name] = 0

    return stats
