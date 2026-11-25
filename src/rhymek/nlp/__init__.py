"""
Rhymek NLP altyapısı.

Bu paket, Türkçe şarkı sözleri üzerinde çalışacak analizler için ortak
veri modellerini, korpus yükleyicisini, metin ön işleme yardımcılarını ve
analiz pipeline'ını sağlar.

Kapsam bilinçli olarak "altyapı" ile sınırlıdır:
- Çalışan: JSONL korpus yükleme, normalize etme, tokenize etme, kıta/satır
  ayrıştırma, istatistik analizi, pipeline
- İskelet: kafiye anahtarı ve Türkçe heceleme (``NotImplementedError``)
"""

from rhymek.nlp.analyzers import Analyzer, StatsAnalyzer, summarize_corpus
from rhymek.nlp.corpus import (
    DEFAULT_CORPUS_PATH,
    document_from_record,
    iter_corpus,
    load_corpus,
)
from rhymek.nlp.pipeline import Pipeline, default_pipeline
from rhymek.nlp.rhyme import LineEnding, line_endings, rhyme_groups, rhyme_key
from rhymek.nlp.syllables import (
    VOWELS,
    count_syllables,
    count_vowels,
    is_vowel,
    syllabify,
)
from rhymek.nlp.text import (
    TURKISH_VOWELS,
    is_section_header,
    iter_words,
    normalize_text,
    parse_lyrics,
    section_header_name,
    tokenize,
    turkish_lower,
)
from rhymek.nlp.types import AnalysisResult, Line, SongDocument, Stanza, Token

__all__ = [
    # types
    "AnalysisResult",
    "Line",
    "SongDocument",
    "Stanza",
    "Token",
    # corpus
    "DEFAULT_CORPUS_PATH",
    "document_from_record",
    "iter_corpus",
    "load_corpus",
    # text
    "TURKISH_VOWELS",
    "is_section_header",
    "iter_words",
    "normalize_text",
    "parse_lyrics",
    "section_header_name",
    "tokenize",
    "turkish_lower",
    # pipeline / analyzers
    "Analyzer",
    "Pipeline",
    "StatsAnalyzer",
    "default_pipeline",
    "summarize_corpus",
    # rhyme
    "LineEnding",
    "line_endings",
    "rhyme_groups",
    "rhyme_key",
    # syllables
    "VOWELS",
    "count_syllables",
    "count_vowels",
    "is_vowel",
    "syllabify",
]
