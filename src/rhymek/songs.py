import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
import lyricsgenius
from rich.console import Console

from rhymek.artists import DATA_DIR, load_artists
from rhymek.client import get_genius_client

DEFAULT_LYRICS_DIR = DATA_DIR / "lyrics"
DEFAULT_SONGS_JSONL = DATA_DIR / "songs.jsonl"
DEFAULT_FETCH_STATE = DATA_DIR / "fetch_state.json"
FETCH_STATE_VERSION = 1
DEFAULT_EXCLUDED_TERMS = (
    "tracklist",
    "track list",
    "album art",
    "album artwork",
    "liner notes",
    "booklet",
    "credits",
    "interview",
    "skit",
    "setlist",
)
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


def _now_iso() -> str:
    """UTC zaman damgasını ISO 8601 biçiminde döner."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty_fetch_state() -> Dict[str, Any]:
    return {"version": FETCH_STATE_VERSION, "artists": {}, "skipped_songs": {}}


def load_fetch_state(filepath: Union[str, Path] = DEFAULT_FETCH_STATE) -> Dict[str, Any]:
    """
    Daha önceki çekimlerin durumunu (hangi sanatçı hangi parametrelerle tarandı,
    hangi şarkılar başarısız oldu) okur. Dosya yoksa veya bozuksa boş durum döner.
    """
    path = Path(filepath)
    if not path.exists():
        return _empty_fetch_state()

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_fetch_state()

    if not isinstance(state, dict):
        return _empty_fetch_state()

    state.setdefault("version", FETCH_STATE_VERSION)
    state.setdefault("artists", {})
    state.setdefault("skipped_songs", {})
    if not isinstance(state["artists"], dict):
        state["artists"] = {}
    if not isinstance(state["skipped_songs"], dict):
        state["skipped_songs"] = {}
    return state


def save_fetch_state(
    state: Dict[str, Any],
    filepath: Union[str, Path] = DEFAULT_FETCH_STATE,
) -> None:
    """Çekim durumunu atomik olarak diske yazar."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def count_saved_songs_for_artist(
    artist_id: Union[int, str],
    filepath: Union[str, Path] = DEFAULT_SONGS_JSONL,
) -> int:
    """
    JSONL dosyasında belirli bir sanatçı ID'siyle kayıtlı şarkı sayısını döner.
    Tüm şarkı sözlerini belleğe almadan satır satır sayar.
    """
    path = Path(filepath)
    if not path.exists():
        return 0

    target = str(artist_id)
    seen: Set[int] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(data.get("artist_id")) != target:
                continue
            song_id = data.get("id")
            if song_id is None:
                continue
            try:
                seen.add(int(song_id))
            except (TypeError, ValueError):
                continue
    return len(seen)


def _artist_fetch_is_current(
    entry: Dict[str, Any],
    max_songs: Optional[int],
    sort: str,
    include_features: bool,
) -> bool:
    """
    Sanatçının aynı parametrelerle daha önce tamamen tarandığını söyler.
    Böylece tekrar tekrar API'ye gidilmez.
    """
    if not isinstance(entry, dict):
        return False
    if entry.get("sort") != sort:
        return False
    if bool(entry.get("include_features")) != bool(include_features):
        return False
    if entry.get("exhausted"):
        return True
    if max_songs is None:
        return False

    prev_limit = entry.get("limit")
    if not isinstance(prev_limit, int):
        return False
    scanned = entry.get("scanned") or 0
    return max_songs <= prev_limit and scanned >= max_songs


def _song_matches_artist(
    song_info: Dict[str, Any],
    artist_name: str,
    include_features: bool,
    artist_id: Optional[int] = None,
) -> bool:
    """
    Şarkının istenen sanatçıya ait (veya feat.) olup olmadığını kontrol eder.
    Öncelikle Genius artist ID'sini karşılaştırır; ID yoksa isme düşer.
    """
    candidates = [song_info.get("primary_artist") or {}]
    if include_features:
        candidates += [
            a for a in song_info.get("featured_artists") or [] if isinstance(a, dict)
        ]

    for artist in candidates:
        candidate_id = artist.get("id")
        if candidate_id is not None and artist_id is not None:
            try:
                if int(candidate_id) == int(artist_id):
                    return True
                continue
            except (TypeError, ValueError):
                pass
        if artist.get("name") == artist_name:
            return True

    return False


def _is_fetchable_song(
    client: lyricsgenius.Genius,
    song_info: Dict[str, Any],
    artist_name: str,
    include_features: bool,
    artist_id: Optional[int] = None,
) -> bool:
    """
    Şarkının indirilmeye uygun olup olmadığını belirler: sözleri tamamlanmış,
    enstrümantal olmayan, başlığı hariç tutulan terimlerden arınmış ve doğru sanatçıya ait.
    """
    if getattr(client, "skip_non_songs", True):
        if song_info.get("lyrics_state") != "complete":
            return False
        if song_info.get("instrumental"):
            return False
        title = (song_info.get("title") or "").lower()
        terms = getattr(client, "excluded_terms", None) or DEFAULT_EXCLUDED_TERMS
        if any(str(term).lower() in title for term in terms):
            return False

    return _song_matches_artist(song_info, artist_name, include_features, artist_id)


def _fetch_song_data(
    client: lyricsgenius.Genius,
    song_info: Dict[str, Any],
    artist_id: int,
    artist_name: str,
) -> Dict[str, Any]:
    """
    Tek bir şarkı için tam bilgiyi ve şarkı sözünü çeker.
    Sadece daha önce kaydedilmemiş şarkılar için çağrılır.
    """
    song_id = song_info.get("id")
    full_info: Dict[str, Any] = {}
    if song_id is not None:
        try:
            response = client.song(int(song_id)) or {}
            full_info = response.get("song") or {}
        except Exception:
            full_info = {}

    merged: Dict[str, Any] = {**song_info, **full_info} if full_info else dict(song_info)
    lyrics = None
    if merged.get("lyrics_state") == "complete" and not merged.get("instrumental"):
        lyrics = client.lyrics(song_url=merged.get("url"))

    album = merged.get("album")
    album_name = album.get("name") if isinstance(album, dict) else None

    return {
        "id": merged.get("id", song_id),
        "title": merged.get("title") or song_info.get("title"),
        "artist": (merged.get("primary_artist") or {}).get("name") or artist_name,
        "artist_id": artist_id,
        "album": album_name,
        "release_date": merged.get("release_date") or merged.get("release_date_for_display"),
        "url": merged.get("url") or song_info.get("url"),
        "lyrics": lyrics,
    }


def _record_skipped_song(
    state: Dict[str, Any],
    song_id: int,
    title: Optional[str],
    artist_id: int,
    reason: str,
    error: Optional[Exception] = None,
) -> None:
    """Başarısız/atlanan şarkıyı durum dosyasına yazar; böylece tekrar denenmez."""
    state["skipped_songs"][str(song_id)] = {
        "title": title,
        "artist_id": artist_id,
        "reason": reason,
        "error": str(error)[:300] if error else None,
        "at": _now_iso(),
    }


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
    *,
    cached_songs: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Belirli bir sanatçının yerel diskte (önce data/songs.jsonl, yoksa data/lyrics)
    bulunan şarkılarını listeler.
    """
    target = str(artist_name_or_id).lower()

    # 1. Önce songs.jsonl dosyasından çek
    all_jsonl_songs = (
        load_songs_from_jsonl(jsonl_file) if cached_songs is None else cached_songs
    )
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
    force: bool = False,
    state_file: Union[str, Path] = DEFAULT_FETCH_STATE,
) -> List[Dict[str, Any]]:
    """
    Verilen artist_id için şarkıları Genius API üzerinden çeker
    ve data/songs.jsonl dosyasına ekler (append).

    Tekrarlı çekimleri önlemek için:
    - Daha önce aynı parametrelerle taranmış sanatçılar hiç API'ye gitmeden atlanır.
    - JSONL'de kayıtlı şarkıların sözleri yeniden indirilmez.
    - Sözü bulunamayan/başarısız şarkılar durum dosyasına yazılır ve tekrar denenmez.

    Args:
        force: Daha önce çekilmiş sanatçıyı yeniden tara ve başarısız şarkıları
            tekrar dene. (JSONL'de zaten kayıtlı şarkılar yine indirilmez.)
        state_file: Çekim durumunun tutulduğu dosya.
    """
    client = genius or get_genius_client()
    output_base = Path(output_dir)
    jsonl_path = Path(jsonl_file)
    state_path = Path(state_file)

    state = load_fetch_state(state_path)
    artist_key = str(artist_id)
    artist_state = state["artists"].get(artist_key)
    skipped_songs = state["skipped_songs"]

    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)
        else:
            console.print(msg)

    # Sanatçı adı belirtilmemişse önce durum dosyasına, yoksa Genius API'ye bak
    if not artist_name:
        if isinstance(artist_state, dict):
            artist_name = artist_state.get("name")
        if not artist_name:
            artist_info = client.artist(artist_id)
            artist_name = artist_info.get("artist", {}).get("name", f"artist_{artist_id}")

    # Bu sanatçı daha önce aynı parametrelerle tamamen çekildi mi?
    if skip_existing and not force:
        saved_count = count_saved_songs_for_artist(artist_id, jsonl_path)
        skip_reason = None
        if artist_state is not None:
            if _artist_fetch_is_current(artist_state, max_songs, sort, include_features):
                skip_reason = "aynı parametrelerle daha önce çekildi"
        elif max_songs is not None and saved_count >= max_songs:
            # Durum dosyası yok (eski veri): yeterli sayıda şarkı zaten kayıtlıysa API'ye gitme
            skip_reason = f"zaten {saved_count} şarkı kayıtlı (limit: {max_songs})"

        if skip_reason:
            # Eski veride durum yoksa, bu parametre setini "taranmış" olarak işaretle;
            # böylece farklı bir sort/limit ile gelindiğinde yeniden taranabilir.
            if artist_state is None:
                state["artists"][artist_key] = {
                    "name": artist_name,
                    "sort": sort,
                    "include_features": bool(include_features),
                    "limit": max_songs,
                    "scanned": saved_count,
                    "exhausted": False,
                    "updated_at": _now_iso(),
                    "assumed": True,
                }
                save_fetch_state(state, state_path)
            log(
                f"[dim]⏭️ '{artist_name}' atlandı: {skip_reason}. "
                f"Yenilemek için force/--force kullanın.[/dim]"
            )
            return []

    saved_ids = get_saved_song_ids(jsonl_path) if skip_existing else set()
    artist_folder = output_base / sanitize_filename(artist_name)

    log(f"[bold cyan]🔍 '{artist_name}' (ID: {artist_id}) için şarkılar aranıyor...[/]")

    fetched_songs: List[Dict[str, Any]] = []
    skipped_saved = 0
    skipped_previous = 0
    failed = 0
    scanned = 0
    exhausted = False
    api_failed = False

    page: Optional[int] = 1
    while page is not None:
        try:
            response = client.artist_songs(
                artist_id=artist_id,
                per_page=50,
                page=page,
                sort=sort,
            ) or {}
        except Exception as e:
            api_failed = True
            log(f"[red]❌ '{artist_name}' şarkı listesi alınamadı:[/] {e}")
            break

        for song_info in response.get("songs") or []:
            if max_songs is not None and scanned >= max_songs:
                break
            if not _is_fetchable_song(
                client, song_info, artist_name, include_features, artist_id
            ):
                continue

            scanned += 1
            song_id = song_info.get("id")
            if song_id is None:
                continue
            song_id = int(song_id)
            title = song_info.get("title")

            # 1. JSONL'de zaten kayıtlıysa hiç söz indirme
            if skip_existing and song_id in saved_ids:
                skipped_saved += 1
                log(f"  [dim]⏭️ Zaten jsonl'de var (atlandı): {title}[/dim]")
                continue

            # 2. Daha önce denenip başarısız olduysa tekrar deneme
            if skip_existing and not force and str(song_id) in skipped_songs:
                skipped_previous += 1
                reason = skipped_songs[str(song_id)].get("reason", "başarısız")
                log(f"  [dim]⏭️ Daha önce denenmiş ({reason}), atlandı: {title}[/dim]")
                continue

            # 3. Sadece yeni şarkı için söz indir
            try:
                song_dict = _fetch_song_data(client, song_info, artist_id, artist_name)
            except Exception as e:
                failed += 1
                _record_skipped_song(state, song_id, title, artist_id, "error", e)
                log(f"  [red]✗ Çekilemedi:[/] {title} ({e})")
                continue

            if not (song_dict.get("lyrics") or "").strip():
                failed += 1
                _record_skipped_song(state, song_id, title, artist_id, "no_lyrics")
                log(f"  [yellow]⚠️ Şarkı sözü bulunamadı, atlandı:[/] {title}")
                continue

            skipped_songs.pop(str(song_id), None)

            # 4. data/songs.jsonl dosyasına ekle (append)
            append_song_to_jsonl(song_dict, filepath=jsonl_path)
            saved_ids.add(song_id)

            # 5. İsteğe bağlı olarak insan tarafından okunabilir .txt kaydet
            if save_txt:
                save_song_files(song_dict, artist_folder, save_txt=True, save_json=False)

            fetched_songs.append(song_dict)
            log(f"  [green]✓ JSONL'e Eklendi:[/] [bold]{song_dict['title']}[/]")

        if max_songs is not None and scanned >= max_songs:
            break

        page = response.get("next_page")
        if page is None:
            exhausted = True

    if not fetched_songs and scanned == 0 and not api_failed:
        log(f"[yellow]⚠️ '{artist_name}' için şarkı bulunamadı.[/]")

    # Başarılı bir taramaysa durumu kaydet; API hatasında sanatçıyı "taranmış" sayma
    if not api_failed:
        state["artists"][artist_key] = {
            "name": artist_name,
            "sort": sort,
            "include_features": bool(include_features),
            "limit": max_songs,
            "scanned": scanned,
            "exhausted": exhausted,
            "updated_at": _now_iso(),
        }
        save_fetch_state(state, state_path)
    elif fetched_songs:
        # Kısmi başarı: yeni şarkılar kaydedildi, durumu yine de güncelle
        state["artists"][artist_key] = {
            "name": artist_name,
            "sort": sort,
            "include_features": bool(include_features),
            "limit": max_songs,
            "scanned": scanned,
            "exhausted": False,
            "updated_at": _now_iso(),
        }
        save_fetch_state(state, state_path)

    total_in_db = count_saved_songs_for_artist(artist_id, jsonl_path)
    log(
        f"[bold green]✨ Tamamlandı:[/] {len(fetched_songs)} yeni şarkı eklendi, "
        f"{skipped_saved} zaten kayıtlı, {skipped_previous + failed} atlandı/başarısız. "
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
    force: bool = False,
    skip_existing: bool = True,
    state_file: Union[str, Path] = DEFAULT_FETCH_STATE,
) -> Dict[str, int]:
    """
    data/artists.json dosyasındaki tüm sanatçıları sırayla gezip şarkılarını
    data/songs.jsonl dosyasına toplu şekilde ekler.

    Daha önce çekilmiş sanatçılar varsayılan olarak atlanır (force=True ile yenilenir).
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
                force=force,
                skip_existing=skip_existing,
                state_file=state_file,
            )
            stats[a_name] = len(songs)
        except Exception as e:
            log(f"[red]❌ '{a_name}' için hata oluştu:[/] {e}")
            stats[a_name] = 0

    return stats
