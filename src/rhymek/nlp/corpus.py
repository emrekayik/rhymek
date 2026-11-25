"""
JSONL şarkı veri setini NLP belgelerine dönüştüren korpus yükleyicisi.

`data/songs.jsonl` (bir satırda bir JSON) dosyasını okur; her kaydı
:class:`~rhymek.nlp.types.SongDocument` nesnesine çevirir.
"""

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Union

from rhymek.nlp.text import parse_lyrics, turkish_lower
from rhymek.nlp.types import SongDocument
from rhymek.songs import DEFAULT_SONGS_JSONL

DEFAULT_CORPUS_PATH = DEFAULT_SONGS_JSONL

_DOCUMENT_FIELDS = {
    "id",
    "title",
    "artist",
    "artist_id",
    "album",
    "release_date",
    "url",
    "lyrics",
}


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def document_from_record(
    record: Dict[str, Any],
    *,
    keep_section_headers: bool = True,
) -> SongDocument:
    """
    JSONL'den okunan tek bir kaydı :class:`SongDocument` nesnesine çevirir.

    Şarkı sözü dışındaki bilinmeyen alanlar ``metadata`` içinde korunur.
    """
    metadata = {
        key: value for key, value in record.items() if key not in _DOCUMENT_FIELDS
    }
    return SongDocument(
        song_id=_as_int(record.get("id")),
        title=str(record.get("title") or ""),
        artist=str(record.get("artist") or ""),
        artist_id=_as_int(record.get("artist_id")),
        album=_as_optional_str(record.get("album")),
        release_date=_as_optional_str(record.get("release_date")),
        url=_as_optional_str(record.get("url")),
        stanzas=parse_lyrics(
            record.get("lyrics"),
            keep_section_headers=keep_section_headers,
        ),
        metadata=metadata,
    )


def iter_corpus(
    filepath: Union[str, Path] = DEFAULT_CORPUS_PATH,
    *,
    artist: Optional[str] = None,
    artist_id: Optional[int] = None,
    limit: Optional[int] = None,
    min_tokens: int = 0,
    require_lyrics: bool = True,
    dedupe: bool = True,
    keep_section_headers: bool = True,
) -> Iterator[SongDocument]:
    """
    JSONL dosyasını satır satır okuyup belgeleri üretir.

    Args:
        filepath: Kaynak JSONL dosyası.
        artist: Sanatçı adına göre (Türkçe büyük/küçük harf duyarsız) filtre.
        artist_id: Genius artist ID'sine göre filtre.
        limit: En fazla kaç belge üretileceği.
        min_tokens: Bu token sayısından az olan belgeleri atla.
        require_lyrics: Şarkı sözü boş olan kayıtları atla.
        dedupe: Aynı şarkı ID'si birden fazla kez geçerse ilkini tut.
        keep_section_headers: ``[Nakarat]`` gibi başlık satırları korunsun mu?
    """
    path = Path(filepath)
    if not path.exists():
        return

    target_artist = turkish_lower(artist) if artist else None
    seen_ids: Set[int] = set()
    produced = 0

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue

            if require_lyrics and not str(record.get("lyrics") or "").strip():
                continue

            record_artist = str(record.get("artist") or "")
            if target_artist is not None and turkish_lower(record_artist) != target_artist:
                continue

            if artist_id is not None and _as_int(record.get("artist_id")) != artist_id:
                continue

            song_id = _as_int(record.get("id"))
            if dedupe and song_id is not None:
                if song_id in seen_ids:
                    continue
                seen_ids.add(song_id)

            document = document_from_record(
                record,
                keep_section_headers=keep_section_headers,
            )
            if document.word_count < min_tokens:
                continue

            yield document
            produced += 1
            if limit is not None and produced >= limit:
                return


def load_corpus(
    filepath: Union[str, Path] = DEFAULT_CORPUS_PATH,
    *,
    artist: Optional[str] = None,
    artist_id: Optional[int] = None,
    limit: Optional[int] = None,
    min_tokens: int = 0,
    require_lyrics: bool = True,
    dedupe: bool = True,
    keep_section_headers: bool = True,
) -> List[SongDocument]:
    """`iter_corpus` sonuçlarını liste olarak döner."""
    return list(
        iter_corpus(
            filepath,
            artist=artist,
            artist_id=artist_id,
            limit=limit,
            min_tokens=min_tokens,
            require_lyrics=require_lyrics,
            dedupe=dedupe,
            keep_section_headers=keep_section_headers,
        )
    )


__all__ = [
    "DEFAULT_CORPUS_PATH",
    "document_from_record",
    "iter_corpus",
    "load_corpus",
]
