"""Satır sonlarında yazıma dayalı kafiye adayları."""

from collections import defaultdict
from typing import Dict, List, Union

from rhymek.nlp.syllables import is_vowel
from rhymek.nlp.text import normalize_text
from rhymek.nlp.types import SongDocument, Token

LineEnding = Union[Token, str]


def line_endings(
    document: SongDocument,
    *,
    skip_section_headers: bool = True,
) -> List[Token]:
    """
    Her satırın son token'ını döner.

    Bölüm başlıkları varsayılan olarak atlanır.
    """
    endings: List[Token] = []
    for line in document.lines:
        if skip_section_headers and line.is_section_header:
            continue
        if line.tokens:
            endings.append(line.tokens[-1])
    return endings


def rhyme_key(
    token: LineEnding,
    *,
    min_suffix_length: int = 2,
    max_suffix_length: int = 4,
) -> str:
    """Ünlü içeren normalize edilmiş bir sonek döner."""
    if not 1 <= min_suffix_length <= max_suffix_length:
        raise ValueError("Sonek uzunlukları 1 <= min <= max koşulunu sağlamalı")
    text = token.normalized if isinstance(token, Token) else token
    letters = "".join(char for char in normalize_text(text) if char.isalpha())
    suffix = letters[-max_suffix_length:]
    if len(suffix) < min_suffix_length or not any(map(is_vowel, suffix)):
        return ""
    return suffix


def rhyme_groups(
    document: SongDocument,
    *,
    skip_section_headers: bool = True,
) -> Dict[str, List[Token]]:
    """En uzun ortak soneklerden başlayarak satır sonlarını gruplar."""
    candidates: dict[str, list[int]] = defaultdict(list)
    endings = line_endings(document, skip_section_headers=skip_section_headers)
    for index, token in enumerate(endings):
        suffix = rhyme_key(token)
        for length in range(2, len(suffix) + 1):
            key = suffix[-length:]
            if any(map(is_vowel, key)):
                candidates[key].append(index)

    groups: dict[str, list[Token]] = {}
    grouped: set[int] = set()
    for key in sorted(candidates, key=len, reverse=True):
        matches = [index for index in candidates[key] if index not in grouped]
        if len(matches) >= 2:
            groups[key] = [endings[index] for index in matches]
            grouped.update(matches)
    return groups


__all__ = ["LineEnding", "line_endings", "rhyme_groups", "rhyme_key"]
