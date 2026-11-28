"""Türkçe yazıma dayalı heceleme yardımcıları."""

import re
import unicodedata

from rhymek.nlp.text import TURKISH_VOWELS, turkish_lower

VOWELS = frozenset(TURKISH_VOWELS + "âîû")


def is_vowel(char: str) -> bool:
    """Karakterin Türkçe ünlü harf olup olmadığını döner."""
    return bool(char) and turkish_lower(char)[:1] in VOWELS


def count_vowels(text: str) -> int:
    """Metindeki Türkçe ünlü harf sayısını döner (kaba bir ön sinyal)."""
    return sum(1 for char in turkish_lower(text or "") if char in VOWELS)


def syllabify(word: str) -> list[str]:
    """Ünlü çekirdeklerine göre heceler ve özgün harf büyüklüğünü korur."""
    syllables: list[str] = []
    for part in re.findall(r"[^\W\d_]+", unicodedata.normalize("NFC", word)):
        nuclei = [index for index, char in enumerate(part) if is_vowel(char)]
        if not nuclei:
            continue
        start = 0
        for left, right in zip(nuclei, nuclei[1:]):
            boundary = max(left + 1, right - 1)
            syllables.append(part[start:boundary])
            start = boundary
        syllables.append(part[start:])
    return syllables


def count_syllables(word: str) -> int:
    """Kelimedeki hece sayısını döner."""
    return len(syllabify(word))


__all__ = ["VOWELS", "count_syllables", "count_vowels", "is_vowel", "syllabify"]
