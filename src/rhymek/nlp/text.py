"""
Türkçe şarkı sözleri için metin ön işleme yardımcıları.

Bu modül dilbilimsel analiz yapmaz; yalnızca normalize etme, token'lara ayırma
ve kıta/satır yapısını çıkarma gibi ortak altyapıyı sağlar.
"""

import re
import string
import unicodedata
from typing import Iterator, List, Optional, Tuple

from rhymek.nlp.types import Line, Stanza, Token

TURKISH_VOWELS = "aeıioöuü"

SECTION_HEADER_PATTERN = re.compile(r"^\[(?P<title>[^\]]+)\]$")
WORD_PATTERN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
WHITESPACE_PATTERN = re.compile(r"\s+", re.UNICODE)


def turkish_lower(text: str) -> str:
    """
    Türkçe kurallarına uygun küçük harfe çevirir.

    Python'un varsayılan `lower()` davranışı ``I -> i`` ve ``İ -> i̇`` üretir;
    Türkçede doğrusu sırasıyla ``ı`` ve ``i`` olduğu için önce bu harfler
    eşlenir, sonra kalan metin küçültülür.
    """
    return text.replace("İ", "i").replace("I", "ı").lower()


def normalize_text(
    text: Optional[str],
    *,
    lowercase: bool = True,
    turkish: bool = True,
    collapse_whitespace: bool = True,
    strip_punctuation: bool = False,
) -> str:
    """
    Metni analiz öncesi standart biçime getirir.

    Args:
        text: Normalize edilecek metin. ``None`` ise boş string döner.
        lowercase: Küçük harfe çevrilsin mi?
        turkish: ``lowercase`` açıkken Türkçe I/İ kuralları uygulansın mı?
        collapse_whitespace: Ardışık boşluk/yeni satırlar tek boşluğa indirilsin mi?
        strip_punctuation: ASCII noktalama işaretleri kaldırılsın mı?
    """
    if not text:
        return ""

    value = unicodedata.normalize("NFKC", text)
    value = (
        value.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )

    if lowercase:
        value = turkish_lower(value) if turkish else value.lower()

    if strip_punctuation:
        value = value.translate(str.maketrans("", "", string.punctuation))

    if collapse_whitespace:
        value = WHITESPACE_PATTERN.sub(" ", value).strip()

    return value


def iter_words(text: str) -> Iterator[Tuple[str, int, int]]:
    """
    Metindeki kelime parçalarını (kelime, başlangıç, bitiş) olarak üretir.

    Kesme işaretli ekler tek parça kabul edilir: ``Ceza'nın`` -> ``Ceza'nın``.
    """
    for match in WORD_PATTERN.finditer(text or ""):
        yield match.group(0), match.start(), match.end()


def tokenize(text: str, *, turkish: bool = True) -> Tuple[Token, ...]:
    """
    Metni normalize edilmiş :class:`Token` nesnelerine ayırır.

    Args:
        text: Token'lara ayrılacak satır/metin.
        turkish: Türkçe küçük harf kuralları uygulansın mı?
    """
    tokens: List[Token] = []
    for index, (word, start, end) in enumerate(iter_words(text)):
        normalized = normalize_text(
            word,
            lowercase=True,
            turkish=turkish,
            collapse_whitespace=False,
        )
        tokens.append(
            Token(
                text=word,
                normalized=normalized,
                index=index,
                start=start,
                end=end,
            )
        )
    return tuple(tokens)


def is_section_header(line: str) -> bool:
    """``[Nakarat]``, ``[Verse 1]`` gibi bölüm başlığı satırı mı?"""
    return bool(SECTION_HEADER_PATTERN.match((line or "").strip()))


def section_header_name(line: str) -> Optional[str]:
    """Bölüm başlığı satırından başlığı çıkarır; değilse ``None`` döner."""
    match = SECTION_HEADER_PATTERN.match((line or "").strip())
    return match.group("title").strip() if match else None


def parse_lyrics(
    text: Optional[str],
    *,
    keep_section_headers: bool = True,
) -> Tuple[Stanza, ...]:
    """
    Ham şarkı sözünü satır ve kıta yapısına dönüştürür.

    Kurallar:
    - Boş satırlar kıta ayırır.
    - ``[Nakarat]`` gibi bölüm başlıkları yeni bir kıta başlatır.
    - Bölüm başlığı satırlarının token'ı yoktur; istenirse tamamen atlanır.

    Args:
        text: Ham şarkı sözü.
        keep_section_headers: Başlık satırları belgede kalsın mı?
    """
    if not text or not text.strip():
        return ()

    stanzas: List[Stanza] = []
    current_lines: List[Line] = []
    line_index = 0
    stanza_index = 0

    def flush() -> None:
        nonlocal current_lines, stanza_index
        if current_lines:
            stanzas.append(Stanza(index=stanza_index, lines=tuple(current_lines)))
            stanza_index += 1
            current_lines = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            flush()
            continue

        header = is_section_header(stripped)
        if header:
            flush()
            if not keep_section_headers:
                continue

        current_lines.append(
            Line(
                index=line_index,
                text=stripped,
                tokens=() if header else tokenize(stripped),
                is_section_header=header,
            )
        )
        line_index += 1

    flush()
    return tuple(stanzas)


__all__ = [
    "TURKISH_VOWELS",
    "iter_words",
    "is_section_header",
    "normalize_text",
    "parse_lyrics",
    "section_header_name",
    "tokenize",
    "turkish_lower",
]
