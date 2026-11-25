"""
Temel korpus/şarkı istatistikleri.

Bu analizör bilinçli olarak dilbilimsel model kullanmaz; altyapının çalıştığını
göstermek ve diğer analizler için referans bir uygulama sunmak amacındadır.
"""

from collections import Counter
from typing import Any, Dict, Iterable, List, Mapping

from rhymek.nlp.analyzers.base import Analyzer
from rhymek.nlp.types import SongDocument


def _top_tokens(counter: Counter, top_n: int) -> List[Dict[str, Any]]:
    return [
        {"token": token, "count": count}
        for token, count in counter.most_common(top_n)
    ]


class StatsAnalyzer(Analyzer):
    """Şarkı başına token/satır/kıta ve kelime frekansı istatistikleri."""

    name = "stats"
    description = "Token, satır, kıta ve kelime frekansı istatistikleri"

    def __init__(self, top_n: int = 10) -> None:
        if top_n < 0:
            raise ValueError("top_n negatif olamaz")
        self.top_n = top_n

    def analyze(self, document: SongDocument) -> Mapping[str, Any]:
        tokens = [token.normalized for token in document.tokens]
        counter = Counter(tokens)
        unique_tokens = len(counter)

        return {
            "song_id": document.song_id,
            "stanzas": len(document.stanzas),
            "lines": sum(1 for line in document.lines if not line.is_section_header),
            "section_headers": sum(
                1 for line in document.lines if line.is_section_header
            ),
            "tokens": len(tokens),
            "unique_tokens": unique_tokens,
            "type_token_ratio": (
                round(unique_tokens / len(tokens), 4) if tokens else 0.0
            ),
            "top_tokens": _top_tokens(counter, self.top_n),
        }


def summarize_corpus(
    documents: Iterable[SongDocument],
    *,
    top_n: int = 10,
) -> Dict[str, Any]:
    """Bir belge koleksiyonu için toplu istatistik üretir."""
    if top_n < 0:
        raise ValueError("top_n negatif olamaz")

    counter: Counter = Counter()
    song_count = 0
    stanza_count = 0
    line_count = 0
    header_count = 0
    token_count = 0

    for document in documents:
        song_count += 1
        stanza_count += len(document.stanzas)
        line_count += sum(
            1 for line in document.lines if not line.is_section_header
        )
        header_count += sum(
            1 for line in document.lines if line.is_section_header
        )
        normalized = [token.normalized for token in document.tokens]
        token_count += len(normalized)
        counter.update(normalized)

    unique_tokens = len(counter)
    return {
        "songs": song_count,
        "stanzas": stanza_count,
        "lines": line_count,
        "section_headers": header_count,
        "tokens": token_count,
        "unique_tokens": unique_tokens,
        "type_token_ratio": (
            round(unique_tokens / token_count, 4) if token_count else 0.0
        ),
        "top_tokens": _top_tokens(counter, top_n),
    }


__all__ = ["StatsAnalyzer", "summarize_corpus"]
