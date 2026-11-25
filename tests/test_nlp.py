"""NLP altyapısı için birim testleri."""

import json
import tempfile
import unittest
from pathlib import Path

from rhymek.nlp import (
    Pipeline,
    StatsAnalyzer,
    count_vowels,
    document_from_record,
    is_vowel,
    line_endings,
    load_corpus,
    normalize_text,
    parse_lyrics,
    rhyme_key,
    summarize_corpus,
    syllabify,
    tokenize,
    turkish_lower,
)


class TextTests(unittest.TestCase):
    def test_turkish_lower(self):
        self.assertEqual(turkish_lower("IĞDIR İZMİR"), "ığdır izmir")

    def test_normalize_text(self):
        self.assertEqual(
            normalize_text("  Ceza’nın   [Nakarat]\n"),
            "ceza'nın [nakarat]",
        )

    def test_tokenize(self):
        tokens = tokenize("Ceza'nın gözleri, 2 kere!")
        self.assertEqual(
            [token.normalized for token in tokens],
            ["ceza'nın", "gözleri", "2", "kere"],
        )
        self.assertEqual(tokens[0].text, "Ceza'nın")

    def test_parse_lyrics_stanzas_and_headers(self):
        text = "[Nakarat]\nGöz gözü görmüyor\nSus\n\n[Verse]\nİki satır"
        stanzas = parse_lyrics(text)

        self.assertEqual(len(stanzas), 2)
        self.assertEqual(len(stanzas[0].lines), 3)
        self.assertTrue(stanzas[0].lines[0].is_section_header)
        self.assertEqual(stanzas[0].lines[0].tokens, ())
        self.assertEqual(stanzas[1].lines[0].text, "[Verse]")

    def test_parse_lyrics_drops_headers(self):
        text = "[Nakarat]\nBir satır"
        stanzas = parse_lyrics(text, keep_section_headers=False)
        self.assertEqual(len(stanzas), 1)
        self.assertEqual(len(stanzas[0].lines), 1)
        self.assertEqual(stanzas[0].lines[0].text, "Bir satır")


class SyllableTests(unittest.TestCase):
    def test_vowels(self):
        self.assertTrue(is_vowel("I"))
        self.assertTrue(is_vowel("İ"))
        self.assertFalse(is_vowel("b"))
        self.assertEqual(count_vowels("Ceza'nın"), 3)

    def test_syllabify_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            syllabify("kafiye")


class RhymeTests(unittest.TestCase):
    def test_line_endings(self):
        stanzas = parse_lyrics("[Nakarat]\nBir iki\nÜç dört")
        document = document_from_record(
            {"id": 1, "title": "T", "artist": "A", "lyrics": stanzas[0].text}
        )
        endings = line_endings(document)
        self.assertEqual([token.normalized for token in endings], ["iki", "dört"])

    def test_rhyme_key_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            rhyme_key("kafiye")


class CorpusTests(unittest.TestCase):
    def _write_corpus(self, path: Path) -> None:
        records = [
            {
                "id": 1,
                "title": "Bir",
                "artist": "Sanatçı",
                "artist_id": 10,
                "lyrics": "bir iki üç",
                "album": "Albüm",
            },
            {
                "id": 2,
                "title": "Boş",
                "artist": "Sanatçı",
                "artist_id": 10,
                "lyrics": "",
            },
            {
                "id": 1,
                "title": "Tekrar",
                "artist": "Sanatçı",
                "artist_id": 10,
                "lyrics": "tekrar kayıt",
            },
            {
                "id": 3,
                "title": "Başka",
                "artist": "Diğer",
                "artist_id": 20,
                "lyrics": "başka bir şarkı daha",
            },
        ]
        with open(path, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def test_load_corpus_filters_and_dedupe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "songs.jsonl"
            self._write_corpus(path)

            documents = load_corpus(path)
            self.assertEqual([doc.song_id for doc in documents], [1, 3])
            self.assertEqual(documents[0].album, "Albüm")

            filtered = load_corpus(path, artist="Diğer")
            self.assertEqual([doc.song_id for doc in filtered], [3])

            by_id = load_corpus(path, artist_id=10)
            self.assertEqual([doc.song_id for doc in by_id], [1])

            limited = load_corpus(path, limit=1)
            self.assertEqual(len(limited), 1)

            min_tokens = load_corpus(path, min_tokens=4)
            self.assertEqual([doc.song_id for doc in min_tokens], [3])

    def test_missing_file_returns_empty(self):
        self.assertEqual(load_corpus("/nonexistent/songs.jsonl"), [])

    def test_document_metadata_keeps_extra_fields(self):
        document = document_from_record(
            {"id": 5, "title": "T", "artist": "A", "lyrics": "bir", "foo": "bar"}
        )
        self.assertEqual(document.metadata["foo"], "bar")


class PipelineTests(unittest.TestCase):
    def test_stats_analyzer_and_pipeline(self):
        documents = [
            document_from_record(
                {
                    "id": 1,
                    "title": "Bir",
                    "artist": "A",
                    "lyrics": "[Nakarat]\nbir iki bir\n\nüç",
                }
            )
        ]

        result = Pipeline([StatsAnalyzer(top_n=2)]).run(documents[0])
        stats = result.get("stats")

        self.assertEqual(stats["stanzas"], 2)
        self.assertEqual(stats["tokens"], 4)
        self.assertEqual(stats["unique_tokens"], 3)
        self.assertEqual(stats["top_tokens"][0], {"token": "bir", "count": 2})

    def test_duplicate_analyzer_rejected(self):
        pipeline = Pipeline([StatsAnalyzer()])
        with self.assertRaises(ValueError):
            pipeline.add(StatsAnalyzer())

    def test_summarize_corpus(self):
        documents = [
            document_from_record(
                {"id": 1, "title": "T1", "artist": "A", "lyrics": "bir iki"}
            ),
            document_from_record(
                {"id": 2, "title": "T2", "artist": "A", "lyrics": "iki üç"}
            ),
        ]
        summary = summarize_corpus(documents)
        self.assertEqual(summary["songs"], 2)
        self.assertEqual(summary["tokens"], 4)
        self.assertEqual(summary["unique_tokens"], 3)
        self.assertEqual(summary["top_tokens"][0], {"token": "iki", "count": 2})


if __name__ == "__main__":
    unittest.main()
