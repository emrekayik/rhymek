import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
import lyricsgenius
from rich.console import Console

from rhymek.artists import load_artists
from rhymek.client import get_genius_client

DEFAULT_LYRICS_DIR = Path("data/lyrics")
DEFAULT_SONGS_JSONL = Path("data/songs.jsonl")
console = Console()


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Dosya isimlerinde sorun yaratabilecek geçersiz karakterleri temizler.
    """
    clean = re.sub(r'[\\/*?:"<>|]', "_", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_length] if len(clean) > max_length else clean


def load_songs_from_jsonl(filepath: Union[str, Path] = DEFAULT_SONGS_JSONL) -> List[Dict[str, Any]]:
    """
    Belirtilen .jsonl dosyasındaki tüm şarkıları okur ve liste olarak döner.
    Dosya yoksa boş liste döner.
    """
    path = Path(filepath)
    if not path.exists():
        return []

    songs: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                songs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return songs


def get_saved_song_ids(filepath: Union[str, Path] = DEFAULT_SONGS_JSONL) -> Set[int]:
    """
    JSONL dosyasında kayıtlı olan tüm şarkı ID'lerini bir küme (set) olarak döner.
    Hızlı varlık kontrolü için kullanılır.
    """
    path = Path(filepath)
    if not path.exists():
        return set()

    song_ids: Set[int] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                s_id = data.get("id")
                if s_id is not None:
                    song_ids.add(int(s_id))
            except (json.JSONDecodeError, ValueError):
                continue
    return song_ids


def append_song_to_jsonl(
    song_data: Dict[str, Any],
    filepath: Union[str, Path] = DEFAULT_SONGS_JSONL,
) -> bool:
    """
    Şarkıyı .jsonl dosyasının sonuna ekler (append mode).
    Daha önce kaydedilmiş şarkıları ASLA silmez.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "a", encoding="utf-8") as f:
        line = json.dumps(song_data, ensure_ascii=False)
        f.write(line + "\n")
    return True


def save_song_files(
    song_data: Dict[str, Any],
    artist_dir: Path,
    save_txt: bool = True,
    save_json: bool = False,
) -> None:
    """
    İsteğe bağlı olarak şarkı sözünü insan tarafından okunabilir .txt olarak kaydeder.
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

    # 2. Bireysel JSON olarak kaydet
    if save_json:
        json_path = artist_dir / f"{safe_title}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(song_data, f, ensure_ascii=False, indent=2)


def get_downloaded_songs_for_artist(
    artist_name_or_id: Union[str, int],
    jsonl_file: Union[str, Path] = DEFAULT_SONGS_JSONL,
    output_dir: Union[str, Path] = DEFAULT_LYRICS_DIR,
) -> List[Dict[str, Any]]:
    """
    Belirli bir sanatçının yerel diskte (önce data/songs.jsonl, yoksa data/lyrics)
    bulunan şarkılarını listeler.
    """
    target = str(artist_name_or_id).lower()

    # 1. Önce songs.jsonl dosyasından çek
    all_jsonl_songs = load_songs_from_jsonl(jsonl_file)
    if all_jsonl_songs:
        matched = [
            s for s in all_jsonl_songs
            if str(s.get("artist_id", "")).lower() == target or str(s.get("artist", "")).lower() == target
        ]
        if matched:
            return matched

    # 2. Eğer jsonl'de henüz yoksa veya eski dosyalar varsa data/lyrics klasörüne bak
    folder = Path(output_dir) / sanitize_filename(str(artist_name_or_id))
    if not folder.exists():
        return []

    songs = []
    for json_file in folder.glob("*.json"):
        if json_file.name == "_summary.json":
            continue
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                songs.append(data)
        except Exception:
            continue
    return songs


def fetch_songs_for_artist(
    artist_id: int,
    artist_name: Optional[str] = None,
    max_songs: Optional[int] = 20,
    sort: str = "popularity",
    jsonl_file: Union[str, Path] = DEFAULT_SONGS_JSONL,
    output_dir: Union[str, Path] = DEFAULT_LYRICS_DIR,
    include_features: bool = False,
    skip_existing: bool = True,
    save_txt: bool = True,
    genius: Optional[lyricsgenius.Genius] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Verilen artist_id için şarkıları Genius API üzerinden çeker
    ve data/songs.jsonl dosyasına ekler (append).
    Mevcut şarkıları asla silmez; zaten varsa atlar.
    """
    client = genius or get_genius_client()
    output_base = Path(output_dir)
    jsonl_path = Path(jsonl_file)

    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)
        else:
            console.print(msg)

    # Sanatçı adı belirtilmemişse Genius API'den öğren
    if not artist_name:
        artist_info = client.artist(artist_id)
        artist_name = artist_info.get("artist", {}).get("name", f"artist_{artist_id}")

    safe_artist_folder = sanitize_filename(artist_name)
    artist_folder = output_base / safe_artist_folder
    if save_txt:
        artist_folder.mkdir(parents=True, exist_ok=True)

    log(f"[bold cyan]🔍 '{artist_name}' (ID: {artist_id}) için şarkılar aranıyor...[/]")

    # Mevcut kayıtlı şarkı ID'lerini oku
    saved_ids = get_saved_song_ids(jsonl_path) if skip_existing else set()

    fetched_songs: List[Dict[str, Any]] = []

    artist_obj = client.search_artist(
        artist_name=artist_name,
        artist_id=artist_id,
        max_songs=max_songs,
        sort=sort,
        include_features=include_features,
    )

    if not artist_obj or not artist_obj.songs:
        log(f"[yellow]⚠️ '{artist_name}' için şarkı bulunamadı.[/]")
        return []

    for song in artist_obj.songs:
        song_body = getattr(song, "_body", {}) or {}
        song_id = song_body.get("id") or getattr(song, "id", None)

        if skip_existing and song_id is not None and int(song_id) in saved_ids:
            log(f"  [dim]⏭️ Zaten jsonl'de var (atlandı): {song.title}[/dim]")
            continue

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

        # 1. data/songs.jsonl dosyasına ekle (append)
        append_song_to_jsonl(song_dict, filepath=jsonl_path)
        if song_id is not None:
            saved_ids.add(int(song_id))

        # 2. İsteğe bağlı olarak insan tarafından okunabilir .txt kaydet
        if save_txt:
            save_song_files(song_dict, artist_folder, save_txt=True, save_json=False)

        fetched_songs.append(song_dict)
        log(f"  [green]✓ JSONL'e Eklendi:[/] [bold]{song.title}[/]")

    total_in_db = len(get_downloaded_songs_for_artist(artist_name, jsonl_file=jsonl_path))
    log(
        f"[bold green]✨ Tamamlandı:[/] {len(fetched_songs)} yeni şarkı eklendi. "
        f"('{artist_name}' toplam kayıtlı şarkı: [bold cyan]{total_in_db}[/], dosya: [blue]{jsonl_path}[/])."
    )
    return fetched_songs


def fetch_all_artists_songs(
    artists_file: Union[str, Path] = "data/artists.json",
    jsonl_file: Union[str, Path] = DEFAULT_SONGS_JSONL,
    max_songs_per_artist: Optional[int] = 10,
    sort: str = "popularity",
    output_dir: Union[str, Path] = DEFAULT_LYRICS_DIR,
    genius: Optional[lyricsgenius.Genius] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, int]:
    """
    data/artists.json dosyasındaki tüm sanatçıları sırayla gezip şarkılarını
    data/songs.jsonl dosyasına toplu şekilde ekler.
    """
    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)
        else:
            console.print(msg)

    artists = load_artists(artists_file)
    if not artists:
        log(f"[yellow]⚠️ '{artists_file}' içinde kayıtlı sanatçı bulunamadı![/]")
        return {}

    client = genius or get_genius_client()
    stats: Dict[str, int] = {}

    log(f"[bold magenta]🚀 Toplam {len(artists)} sanatçı bulundu. JSONL'e toplu indirme başlıyor...[/]")

    for artist in artists:
        a_id = artist.get("id")
        a_name = artist.get("name")
        if not a_id:
            log(f"[yellow]⚠️ Sanatçı ID bulunamadı ({a_name}), atlanıyor.[/]")
            continue

        try:
            songs = fetch_songs_for_artist(
                artist_id=int(a_id),
                artist_name=a_name,
                max_songs=max_songs_per_artist,
                sort=sort,
                jsonl_file=jsonl_file,
                output_dir=output_dir,
                genius=client,
                progress_callback=progress_callback,
            )
            stats[a_name] = len(songs)
        except Exception as e:
            log(f"[red]❌ '{a_name}' için hata oluştu:[/] {e}")
            stats[a_name] = 0

    return stats
