"""Transformer tabanlı gömme ve anlamsal arama altyapısı testleri."""

import hashlib
import tempfile
import unittest
from pathlib import Path

import numpy as np

from rhymek.nlp import document_from_record
from rhymek.nlp.embeddings import (
    EmbeddingIndex,
    TransformerEmbedder,
    build_index,
    chunk_token_ids,
    document_text,
    find_snippet,
    index_path_for_model,
    semantic_search,
    similar_songs,
    text_hash,
)


def make_document(song_id, title, lyrics, artist="Test Sanatçı"):
    return document_from_record(
        {
            "id": song_id,
            "title": title,
            "artist": artist,
            "lyrics": lyrics,
        }
    )


class FakeEmbedder:
    """Torch yüklemeden deterministik vektör üreten sahte model."""

    model_name = "fake-model"

    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.calls = []

    def embed_texts(self, texts, progress_callback=None):
        self.calls.append(tuple(texts))
        vectors = []
        for text in texts:
            vector = self.mapping.get(text)
            if vector is None:
                digest = hashlib.sha256(text.encode("utf-8")).digest()
                vector = [digest[0] / 255, digest[1] / 255, digest[2] / 255]
            vectors.append(vector)
        return np.asarray(vectors, dtype=np.float32)


class HelperTests(unittest.TestCase):
    def test_chunk_token_ids_without_overlap(self):
        self.assertEqual(
            chunk_token_ids(list(range(10)), chunk_size=4, stride=0),
            [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]],
        )

    def test_chunk_token_ids_with_overlap(self):
        self.assertEqual(
            chunk_token_ids(list(range(10)), chunk_size=4, stride=1),
            [[0, 1, 2, 3], [3, 4, 5, 6], [6, 7, 8, 9]],
        )

    def test_chunk_token_ids_short_text_and_empty(self):
        self.assertEqual(chunk_token_ids([1, 2], 8, 2), [[1, 2]])
        self.assertEqual(chunk_token_ids([], 8, 2), [[]])

    def test_chunk_token_ids_rejects_invalid_arguments(self):
        with self.assertRaises(ValueError):
            chunk_token_ids([1], chunk_size=0, stride=0)
        with self.assertRaises(ValueError):
            chunk_token_ids([1], chunk_size=4, stride=4)

    def test_document_text_skips_section_headers(self):
        document = make_document(
            1,
            "Gece",
            "[Nakarat]\nsokakta yalnızım\n\nbir başka satır",
        )
        self.assertEqual(
            document_text(document),
            "Gece\nsokakta yalnızım\nbir başka satır",
        )

    def test_text_hash_changes_with_text(self):
        self.assertEqual(text_hash("aynı"), text_hash("aynı"))
        self.assertNotEqual(text_hash("bir"), text_hash("iki"))

    def test_find_snippet_prefers_query_overlap(self):
        document = make_document(
            1,
            "Gece",
            "gündüz kalabalık\nsokakta yalnızlık var\nbaşka satır",
        )
        self.assertEqual(
            find_snippet(document, "yalnızlık"),
            "sokakta yalnızlık var",
        )

    def test_find_snippet_falls_back_to_first_line(self):
        document = make_document(1, "Gece", "ilk satır\nikinci satır")
        self.assertEqual(find_snippet(document, "uymayan kelime"), "ilk satır")

    def test_find_snippet_truncates(self):
        document = make_document(1, "Gece", "a" * 50)
        snippet = find_snippet(document, "", max_chars=10)
        self.assertEqual(len(snippet), 10)
        self.assertTrue(snippet.endswith("…"))

    def test_index_path_for_model(self):
        path = index_path_for_model(
            "sentence-transformers/ornek-model",
            directory="/tmp/embeddings",
        )
        self.assertEqual(path.parent, Path("/tmp/embeddings"))
        self.assertEqual(path.name, "sentence-transformers__ornek-model.npz")


class EmbeddingIndexTests(unittest.TestCase):
    def make_index(self):
        return EmbeddingIndex(
            model_name="test-model",
            song_ids=(10, 20, 30),
            vectors=np.asarray(
                [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
                dtype=np.float32,
            ),
            text_hashes=("a", "b", "c"),
        )

    def test_search_orders_by_cosine_similarity(self):
        hits = self.make_index().search(
            np.asarray([1.0, 0.0], dtype=np.float32),
            top_k=2,
        )
        self.assertEqual([song_id for song_id, _ in hits], [10, 30])
        self.assertAlmostEqual(hits[0][1], 1.0, places=5)
        self.assertAlmostEqual(hits[1][1], 0.7071, places=4)

    def test_search_supports_candidate_filter(self):
        hits = self.make_index().search(
            np.asarray([1.0, 0.0], dtype=np.float32),
            top_k=2,
            candidate_ids=[20, 30],
        )
        self.assertEqual([song_id for song_id, _ in hits], [30, 20])

    def test_similar_excludes_itself(self):
        hits = self.make_index().similar(10, top_k=2)
        self.assertEqual([song_id for song_id, _ in hits], [30, 20])

    def test_vector_for_unknown_song_raises(self):
        with self.assertRaises(KeyError):
            self.make_index().vector_for(999)

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "index.npz"
            original = self.make_index()
            original.save(path)

            loaded = EmbeddingIndex.load(path)
            self.assertEqual(loaded.model_name, "test-model")
            self.assertEqual(loaded.song_ids, (10, 20, 30))
            self.assertEqual(loaded.text_hashes, ("a", "b", "c"))
            np.testing.assert_allclose(loaded.vectors, original.vectors)

    def test_length_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            EmbeddingIndex(
                model_name="test-model",
                song_ids=(1, 2),
                vectors=np.zeros((1, 3), dtype=np.float32),
            )


class BuildIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.index_path = Path(self.tmp.name) / "index.npz"
        self.doc1 = make_document(1, "Gece", "sokakta yalnızım")
        self.doc2 = make_document(2, "Gündüz", "kalabalık caddeler")

    def test_build_index_adds_all_documents(self):
        embedder = FakeEmbedder(
            {
                document_text(self.doc1): [1.0, 0.0],
                document_text(self.doc2): [0.0, 1.0],
            }
        )
        result = build_index(
            [self.doc1, self.doc2],
            embedder=embedder,
            index_path=self.index_path,
        )

        self.assertEqual(result.added, 2)
        self.assertEqual(result.reused, 0)
        self.assertEqual(result.total, 2)
        self.assertTrue(self.index_path.exists())
        self.assertEqual(result.index.song_ids, (1, 2))

    def test_second_build_reuses_unchanged_documents(self):
        mapping = {
            document_text(self.doc1): [1.0, 0.0],
            document_text(self.doc2): [0.0, 1.0],
        }
        build_index(
            [self.doc1, self.doc2],
            embedder=FakeEmbedder(mapping),
            index_path=self.index_path,
        )

        second = FakeEmbedder(mapping)
        result = build_index(
            [self.doc1, self.doc2],
            embedder=second,
            index_path=self.index_path,
        )

        self.assertEqual(result.added, 0)
        self.assertEqual(result.reused, 2)
        self.assertEqual(second.calls, [])

    def test_changed_lyrics_is_reembedded_only(self):
        mapping = {
            document_text(self.doc1): [1.0, 0.0],
            document_text(self.doc2): [0.0, 1.0],
        }
        build_index(
            [self.doc1, self.doc2],
            embedder=FakeEmbedder(mapping),
            index_path=self.index_path,
        )

        changed = make_document(2, "Gündüz", "tamamen değişti")
        changed_text = document_text(changed)
        third = FakeEmbedder({changed_text: [0.0, 1.0]})
        result = build_index(
            [self.doc1, changed],
            embedder=third,
            index_path=self.index_path,
        )

        self.assertEqual(result.added, 1)
        self.assertEqual(result.reused, 1)
        self.assertEqual(third.calls, [(changed_text,)])

    def test_force_reembeds_even_unchanged(self):
        mapping = {
            document_text(self.doc1): [1.0, 0.0],
            document_text(self.doc2): [0.0, 1.0],
        }
        build_index(
            [self.doc1, self.doc2],
            embedder=FakeEmbedder(mapping),
            index_path=self.index_path,
        )

        forced = FakeEmbedder(mapping)
        result = build_index(
            [self.doc1, self.doc2],
            embedder=forced,
            index_path=self.index_path,
            force=True,
        )

        self.assertEqual(result.added, 2)
        self.assertEqual(result.reused, 0)
        self.assertEqual(len(forced.calls), 1)

    def test_subset_build_preserves_other_documents(self):
        mapping = {
            document_text(self.doc1): [1.0, 0.0],
            document_text(self.doc2): [0.0, 1.0],
        }
        build_index(
            [self.doc1, self.doc2],
            embedder=FakeEmbedder(mapping),
            index_path=self.index_path,
        )

        changed = make_document(1, "Gece", "yeni sözler")
        build_index(
            [changed],
            embedder=FakeEmbedder({document_text(changed): [1.0, 1.0]}),
            index_path=self.index_path,
        )

        loaded = EmbeddingIndex.load(self.index_path)
        self.assertEqual(set(loaded.song_ids), {1, 2})

    def test_build_without_index_path_keeps_memory_only(self):
        embedder = FakeEmbedder(
            {
                document_text(self.doc1): [1.0, 0.0],
                document_text(self.doc2): [0.0, 1.0],
            }
        )
        result = build_index(
            [self.doc1, self.doc2],
            embedder=embedder,
            index_path=None,
        )
        self.assertIsNone(result.path)
        self.assertEqual(result.total, 2)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.doc1 = make_document(1, "Gece", "sokakta yalnızlık", artist="A")
        self.doc2 = make_document(2, "Aşk", "seni seviyorum", artist="B")
        self.doc3 = make_document(3, "Gündüz", "kalabalık caddeler", artist="A")
        self.docs_by_id = {1: self.doc1, 2: self.doc2, 3: self.doc3}
        self.mapping = {
            document_text(self.doc1): [1.0, 0.0],
            document_text(self.doc2): [0.0, 1.0],
            document_text(self.doc3): [0.7, 0.7],
            "yalnızlık": [1.0, 0.0],
        }
        self.embedder = FakeEmbedder(self.mapping)
        self.index = build_index(
            [self.doc1, self.doc2, self.doc3],
            embedder=self.embedder,
            index_path=None,
        ).index

    def test_semantic_search_returns_metadata_and_snippet(self):
        hits = semantic_search(
            self.index,
            "yalnızlık",
            self.embedder,
            top_k=2,
            documents_by_id=self.docs_by_id,
        )

        self.assertEqual(hits[0].song_id, 1)
        self.assertEqual(hits[0].title, "Gece")
        self.assertEqual(hits[0].artist, "A")
        self.assertEqual(hits[0].snippet, "sokakta yalnızlık")
        self.assertGreater(hits[0].score, hits[1].score)

    def test_semantic_search_filters_candidates(self):
        hits = semantic_search(
            self.index,
            "yalnızlık",
            self.embedder,
            top_k=10,
            documents_by_id=self.docs_by_id,
            candidate_ids=[2, 3],
        )
        self.assertEqual({hit.song_id for hit in hits}, {2, 3})

    def test_semantic_search_rejects_empty_query(self):
        with self.assertRaises(ValueError):
            semantic_search(
                self.index,
                "   ",
                self.embedder,
                documents_by_id=self.docs_by_id,
            )

    def test_similar_songs_excludes_target(self):
        hits = similar_songs(
            self.index,
            1,
            top_k=2,
            documents_by_id=self.docs_by_id,
        )
        self.assertEqual([hit.song_id for hit in hits], [3, 2])
        self.assertEqual(hits[0].title, "Gündüz")


class TransformerEmbedderValidationTests(unittest.TestCase):
    def test_invalid_batch_size(self):
        with self.assertRaises(ValueError):
            TransformerEmbedder(batch_size=0)

    def test_invalid_chunk_settings(self):
        with self.assertRaises(ValueError):
            TransformerEmbedder(max_tokens=0)
        with self.assertRaises(ValueError):
            TransformerEmbedder(max_tokens=16, stride=16)


if __name__ == "__main__":
    unittest.main()
