"""
Türkçe heceleme ve hece sayımı için altyapı.

Heceleme henüz uygulanmadı. Arayüz, ileride `turkishnlp` veya kendi
kural tabanlı heceleyicinizle doldurulmak üzere tanımlanmıştır.

Türkçe heceleme için dikkat edilmesi gerekenler:
- Ünlü harfler hece çekirdeğidir: a, e, ı, i, o, ö, u, ü
- Ünsüz kümeleri ve ünlü çevresindeki dağılım hece sınırını belirler
- Kesme işaretli ekler (``Ceza'nın``) ayrı değerlendirilebilir
"""

from typing import List

from rhymek.nlp.text import TURKISH_VOWELS, turkish_lower

VOWELS = frozenset(TURKISH_VOWELS)


def is_vowel(char: str) -> bool:
    """Karakterin Türkçe ünlü harf olup olmadığını döner."""
    return bool(char) and turkish_lower(char)[:1] in VOWELS


def count_vowels(text: str) -> int:
    """Metindeki Türkçe ünlü harf sayısını döner (kaba bir ön sinyal)."""
    return sum(1 for char in turkish_lower(text or "") if char in VOWELS)


def syllabify(word: str) -> List[str]:
    """
    Kelimeyi hecelere ayırır.

    .. note::
        Henüz uygulanmadı; ``NotImplementedError`` yükseltir.
    """
    raise NotImplementedError(
        "Türkçe heceleme henüz uygulanmadı. "
        "'turkishnlp' entegrasyonu veya kural tabanlı bir heceleyici eklenecek."
    )


def count_syllables(word: str) -> int:
    """
    Kelimedeki hece sayısını döner.

    .. note::
        Henüz uygulanmadı; :func:`syllabify` tamamlandığında etkinleşecek.
    """
    return len(syllabify(word))


__all__ = ["VOWELS", "count_syllables", "count_vowels", "is_vowel", "syllabify"]
