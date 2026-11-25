"""
NLP katmanı için temel veri modelleri.

Bu modül yalnızca veri taşıyıcılarını tanımlar; metin işleme kuralları
`rhymek.nlp.text`, korpus yükleme ise `rhymek.nlp.corpus` içindedir.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True, slots=True)
class Token:
    """Tek bir kelime/parça ve normalize edilmiş biçimi."""

    text: str
    normalized: str
    index: int
    start: Optional[int] = None
    end: Optional[int] = None


@dataclass(frozen=True, slots=True)
class Line:
    """Şarkı sözündeki tek bir satır."""

    index: int
    text: str
    tokens: Tuple[Token, ...] = ()
    is_section_header: bool = False

    @property
    def normalized(self) -> str:
        """Satırdaki token'ların normalize edilmiş halini boşlukla birleştirir."""
        return " ".join(token.normalized for token in self.tokens)


@dataclass(frozen=True, slots=True)
class Stanza:
    """Şarkı sözündeki kıta (paragraf)."""

    index: int
    lines: Tuple[Line, ...]

    @property
    def text(self) -> str:
        """Kıtayı düz metin olarak döner."""
        return "\n".join(line.text for line in self.lines)

    @property
    def tokens(self) -> Tuple[Token, ...]:
        """Kıtadaki tüm token'ları sırayla döner."""
        return tuple(token for line in self.lines for token in line.tokens)


@dataclass(frozen=True, slots=True)
class SongDocument:
    """NLP işlemlerine hazır tek bir şarkı belgesi."""

    song_id: Optional[int]
    title: str
    artist: str
    artist_id: Optional[int] = None
    album: Optional[str] = None
    release_date: Optional[str] = None
    url: Optional[str] = None
    stanzas: Tuple[Stanza, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def lines(self) -> Tuple[Line, ...]:
        """Belgedeki tüm satırları sırayla döner."""
        return tuple(line for stanza in self.stanzas for line in stanza.lines)

    @property
    def tokens(self) -> Tuple[Token, ...]:
        """Belgedeki tüm token'ları sırayla döner."""
        return tuple(token for line in self.lines for token in line.tokens)

    @property
    def text(self) -> str:
        """Belgeyi düz metin olarak döner."""
        return "\n".join(line.text for line in self.lines)

    @property
    def normalized_text(self) -> str:
        """Belgeyi normalize edilmiş token'larla düz metin olarak döner."""
        return " ".join(token.normalized for token in self.tokens)

    @property
    def word_count(self) -> int:
        """Belgedeki token sayısı."""
        return len(self.tokens)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Bir şarkı için çalıştırılan analizlerin sonucu."""

    song_id: Optional[int]
    title: str
    artist: str
    values: Mapping[str, Any] = field(default_factory=dict)

    def get(self, analyzer_name: str, default: Any = None) -> Any:
        """İlgili analizörün sonucunu döner."""
        return self.values.get(analyzer_name, default)


__all__ = [
    "Token",
    "Line",
    "Stanza",
    "SongDocument",
    "AnalysisResult",
]
