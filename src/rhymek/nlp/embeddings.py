"""
Transformer tabanlı şarkı sözü gömmeleri (embeddings) ve anlamsal arama.

Bu modül, Hugging Face ``transformers`` ve ``torch`` kullanarak Türkçe şarkı
sözlerini vektörlere dönüştürür. Vektörler ``data/embeddings/`` altında
önbelleğe alınır; aynı model ve değişmemiş sözler için yeniden hesaplanmaz.

Temel kullanım::

    from rhymek.nlp import (
        TransformerEmbedder,
        build_index,
        load_corpus,
        semantic_search,
    )

    docs = load_corpus(limit=100)
    embedder = TransformerEmbedder()
    result = build_index(docs, embedder=embedder)
    hits = semantic_search(
        result.index,
        "yalnızlık ve sokak",
        embedder,
        documents_by_id={doc.song_id: doc for doc in docs},
    )

Ağır bağımlılıklar (torch, transformers) yalnızca model gerçekten
kullanıldığında içe aktarılır. Bu sayede ``rhymek`` temel kurulumu ML
bağımlılıkları olmadan da çalışır.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
)

from rhymek.artists import DATA_DIR
from rhymek.nlp.text import tokenize
from rhymek.nlp.types import SongDocument

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_EMBEDDINGS_DIR = DATA_DIR / "embeddings"
DEFAULT_BATCH_SIZE = 16
DEFAULT_MAX_TOKENS = 256
DEFAULT_STRIDE = 64

ProgressCallback = Callable[[str], None]


class MLDependencyError(RuntimeError):
    """Torch/transformers gibi ML bağımlılıkları eksik olduğunda yükseltilir."""


class EmbeddingError(RuntimeError):
    """Gömme veya indeks işlemleri başarısız olduğunda yükseltilir."""


class TextEmbedder(Protocol):
    """Metinleri vektörlere dönüştüren model arayüzü."""

    model_name: str

    def embed_texts(
        self,
        texts: Sequence[str],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Any:
        """Her metin için tek boyutlu bir vektör döner."""
        ...


@dataclass(frozen=True, slots=True)
class SearchHit:
    """Anlamsal arama veya benzer şarkı sonucu."""

    song_id: int
    score: float
    title: str = ""
    artist: str = ""
    snippet: str = ""


@dataclass
class IndexBuildResult:
    """``build_index`` çıktısı."""

    index: "EmbeddingIndex"
    added: int
    reused: int
    path: Optional[Path]

    @property
    def total(self) -> int:
        """İndeksteki toplam şarkı sayısı."""
        return self.index.size


def _numpy():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - kurulum hatası
        raise MLDependencyError(
            "numpy kurulu değil. `uv sync --extra ml` çalıştırın."
        ) from exc
    return np


def _require_ml():
    """Torch, transformers ve numpy'yi tembel olarak içe aktarır."""
    try:
        # macOS'ta torch içe aktarılırken gelen ilgisiz dağıtık işlem notunu sustur.
        logging.getLogger(
            "torch.distributed.elastic.multiprocessing.redirects"
        ).setLevel(logging.ERROR)
        import numpy as np
        import torch
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils import logging as transformers_logging
    except ImportError as exc:  # pragma: no cover - kurulum hatası
        raise MLDependencyError(
            "Transformer bağımlılıkları kurulu değil. "
            "`uv sync --extra ml` çalıştırın."
        ) from exc

    # Model yükleme ilerleme çubukları CLI çıktısını kirletmesin.
    transformers_logging.set_verbosity_error()
    transformers_logging.disable_progress_bar()
    return np, torch, AutoModel, AutoTokenizer


def text_hash(text: str) -> str:
    """Metnin içerik önbelleği için kısa SHA-256 özetini döner."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_text(document: SongDocument) -> str:
    """
    Bir şarkıyı gömme modeline verilecek metne dönüştürür.

    Bölüm başlıkları (``[Nakarat]`` vb.) atlanır; başlık ve söz satırları
    korunur. Böylece model yalnızca anlamlı içeriği görür.
    """
    parts = []
    title = (document.title or "").strip()
    if title:
        parts.append(title)

    for line in document.lines:
        if line.is_section_header:
            continue
        text = line.text.strip()
        if text:
            parts.append(text)

    return "\n".join(parts)


def index_path_for_model(
    model_name: str,
    directory: Union[str, Path] = DEFAULT_EMBEDDINGS_DIR,
) -> Path:
    """Model adından güvenli bir önbellek dosya yolu üretir."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "__", model_name).strip("_")
    return Path(directory) / f"{slug or 'model'}.npz"


def chunk_token_ids(
    token_ids: Sequence[int],
    chunk_size: int,
    stride: int,
) -> list[list[int]]:
    """
    Uzun token dizisini örtüşen parçalara böler.

    Args:
        token_ids: Token ID'leri.
        chunk_size: Parça başına en fazla token sayısı.
        stride: Ardışık parçalar arasındaki örtüşme miktarı.
            0 ise parçalar örtüşmez.

    Raises:
        ValueError: ``chunk_size`` pozitif değilse veya ``stride``
            ``chunk_size`` değerine eşit/büyükse.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size pozitif olmalı")
    if stride < 0 or stride >= chunk_size:
        raise ValueError("stride 0 ile chunk_size arasında olmalı")

    ids = list(token_ids)
    if not ids:
        return [[]]

    chunks: list[list[int]] = []
    start = 0
    while True:
        end = min(start + chunk_size, len(ids))
        chunks.append(ids[start:end])
        if end >= len(ids):
            break
        start = end - stride
    return chunks


def find_snippet(
    document: SongDocument,
    query: str,
    *,
    max_chars: int = 160,
) -> str:
    """
    Şarkı içinden sorguyla en çok örtüşen satırı seçer.

    Basit token kesişimi kullanır; model çağrısı gerektirmez. Sorguyla
    eşleşen satır yoksa ilk anlamlı satır döner.
    """
    lines = [
        line
        for line in document.lines
        if not line.is_section_header and line.text.strip()
    ]
    if not lines:
        return ""

    query_tokens = {
        token.normalized for token in tokenize(query or "") if token.normalized
    }
    best_line = lines[0]
    best_score = -1

    for line in lines:
        line_tokens = {token.normalized for token in line.tokens}
        score = len(query_tokens & line_tokens)
        if score > best_score:
            best_score = score
            best_line = line

    text = best_line.text.strip()
    if max_chars > 0 and len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def _normalize_rows(vectors):
    """Her satırı L2 normu 1 olacak şekilde ölçekler."""
    np = _numpy()
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    return array / np.maximum(norms, 1e-12)


class EmbeddingIndex:
    """Şarkı ID'leri ile normalize edilmiş vektörleri birlikte tutar."""

    def __init__(
        self,
        model_name: str,
        song_ids: Sequence[int],
        vectors: Any,
        text_hashes: Sequence[str] = (),
    ) -> None:
        np = _numpy()
        array = np.asarray(vectors, dtype=np.float32)
        if array.ndim != 2:
            raise ValueError("vectors iki boyutlu olmalı")

        ids = tuple(int(song_id) for song_id in song_ids)
        if len(ids) != array.shape[0]:
            raise ValueError("song_ids ve vectors uzunlukları eşleşmeli")
        if len(set(ids)) != len(ids):
            raise ValueError("song_ids tekrarsız olmalı")

        hashes = tuple(str(value) for value in text_hashes)
        if hashes and len(hashes) != len(ids):
            raise ValueError("text_hashes ve song_ids uzunlukları eşleşmeli")
        if not hashes:
            hashes = tuple("" for _ in ids)

        self.model_name = model_name
        self.song_ids = ids
        self.vectors = array
        self.text_hashes = hashes

    @property
    def size(self) -> int:
        """İndeksteki şarkı sayısı."""
        return len(self.song_ids)

    @property
    def dimension(self) -> int:
        """Vektör boyutu."""
        return int(self.vectors.shape[1]) if self.vectors.size else 0

    def contains(self, song_id: int) -> bool:
        """Şarkı indekste var mı?"""
        return int(song_id) in self.song_ids

    def vector_for(self, song_id: int) -> Any:
        """Şarkının vektörünü döner; yoksa ``KeyError`` yükseltir."""
        try:
            position = self.song_ids.index(int(song_id))
        except ValueError as exc:
            raise KeyError(song_id) from exc
        return self.vectors[position]

    def save(self, path: Union[str, Path]) -> Path:
        """İndeksi sıkıştırılmamış ``.npz`` olarak kaydeder."""
        np = _numpy()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            target,
            model_name=np.asarray(self.model_name),
            song_ids=np.asarray(self.song_ids, dtype=np.int64),
            vectors=np.asarray(self.vectors, dtype=np.float32),
            text_hashes=np.asarray(self.text_hashes, dtype=np.str_),
        )
        return target

    @classmethod
    def load(cls, path: Union[str, Path]) -> "EmbeddingIndex":
        """Kaydedilmiş indeksi okur."""
        np = _numpy()
        with np.load(Path(path), allow_pickle=False) as data:
            model_value = data["model_name"]
            model_name = str(model_value.item()) if model_value.shape == () else str(
                model_value[0]
            )
            song_ids = tuple(int(value) for value in data["song_ids"])
            vectors = np.asarray(data["vectors"], dtype=np.float32)
            hashes = (
                tuple(str(value) for value in data["text_hashes"])
                if "text_hashes" in data.files
                else ()
            )
        return cls(
            model_name=model_name,
            song_ids=song_ids,
            vectors=vectors,
            text_hashes=hashes,
        )

    def search(
        self,
        query_vector: Any,
        *,
        top_k: int = 10,
        candidate_ids: Optional[Sequence[int]] = None,
    ) -> list[Tuple[int, float]]:
        """
        Sorgu vektörüne kosinüs benzerliği en yüksek şarkıları döner.

        Args:
            query_vector: Sorgu vektörü.
            top_k: Döndürülecek en fazla sonuç sayısı.
            candidate_ids: Yalnızca bu şarkı ID'leri arasında ara.
        """
        np = _numpy()
        if top_k <= 0 or self.size == 0:
            return []

        query = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        if query.shape[0] != self.dimension:
            raise ValueError("Sorgu vektörünün boyutu indeksle uyuşmuyor")

        query_norm = float(np.linalg.norm(query))
        if query_norm == 0.0:
            return []

        positions = np.arange(self.size)
        if candidate_ids is not None:
            allowed = {int(song_id) for song_id in candidate_ids}
            mask = np.asarray(
                [song_id in allowed for song_id in self.song_ids],
                dtype=bool,
            )
            if not mask.any():
                return []
            positions = positions[mask]

        row_vectors = self.vectors[positions]
        row_norms = np.linalg.norm(row_vectors, axis=1)
        denominators = np.maximum(row_norms * query_norm, 1e-12)
        scores = (row_vectors @ query) / denominators

        order = np.argsort(-scores)[:top_k]
        return [
            (int(self.song_ids[positions[index]]), float(scores[index]))
            for index in order
        ]

    def similar(
        self,
        song_id: int,
        *,
        top_k: int = 10,
        candidate_ids: Optional[Sequence[int]] = None,
    ) -> list[Tuple[int, float]]:
        """Verilen şarkıya en çok benzeyen diğer şarkıları döner."""
        vector = self.vector_for(song_id)
        hits = self.search(
            vector,
            top_k=top_k + 1,
            candidate_ids=candidate_ids,
        )
        return [
            (hit_id, score)
            for hit_id, score in hits
            if hit_id != int(song_id)
        ][:top_k]


def build_index(
    documents: Sequence[SongDocument],
    *,
    embedder: TextEmbedder,
    index_path: Union[str, Path, None] = None,
    force: bool = False,
    progress_callback: Optional[ProgressCallback] = None,
) -> IndexBuildResult:
    """
    Belgeler için gömme indeksi oluşturur veya mevcut indeksi günceller.

    Aynı model ve değişmemiş sözler için mevcut vektörler yeniden
    kullanılır. ``documents`` filtrelenmiş bir alt küme olsa bile indeksteki
    diğer şarkılar korunur.

    Args:
        documents: İndekse eklenecek/güncellenecek belgeler.
        embedder: Metinleri vektöre çeviren model.
        index_path: Kayıt yolu; ``None`` ise yalnızca bellekte tutulur.
        force: Mevcut vektörleri yok sayıp hepsini yeniden hesapla.
        progress_callback: Durum mesajları için isteğe bağlı geri çağırma.
    """
    np = _numpy()
    path = Path(index_path) if index_path is not None else None

    existing: Optional[EmbeddingIndex] = None
    if path is not None and path.exists():
        try:
            existing = EmbeddingIndex.load(path)
        except Exception as exc:
            if progress_callback:
                progress_callback(f"Eski indeks okunamadı, yeniden oluşturulacak: {exc}")
            existing = None

    if existing is not None and existing.model_name != embedder.model_name:
        existing = None

    existing_vectors: dict[int, Tuple[Any, str]] = {}
    if existing is not None:
        for song_id, vector, content_hash in zip(
            existing.song_ids,
            existing.vectors,
            existing.text_hashes,
        ):
            existing_vectors[song_id] = (vector, content_hash)

    vectors_by_id = dict(existing_vectors)
    valid_documents = [
        document for document in documents if document.song_id is not None
    ]

    missing: list[Tuple[SongDocument, str, str]] = []
    reused = 0
    for document in valid_documents:
        text = document_text(document)
        content_hash = text_hash(text)
        song_id = int(document.song_id)
        previous = existing_vectors.get(song_id)
        if not force and previous is not None and previous[1] == content_hash:
            reused += 1
            continue
        missing.append((document, text, content_hash))

    if missing:
        if progress_callback:
            progress_callback(
                f"{len(missing)} şarkı için gömme vektörü hesaplanıyor..."
            )
        new_vectors = np.asarray(
            embedder.embed_texts(
                [text for _, text, _ in missing],
                progress_callback=progress_callback,
            ),
            dtype=np.float32,
        )
        if new_vectors.ndim == 1:
            new_vectors = new_vectors.reshape(1, -1)
        if new_vectors.shape[0] != len(missing):
            raise EmbeddingError(
                "Model, beklenen sayıda gömme vektörü üretmedi"
            )
        if (
            existing is not None
            and existing.dimension > 0
            and new_vectors.shape[1] != existing.dimension
        ):
            raise EmbeddingError(
                "Yeni vektörlerin boyutu mevcut indeksle uyuşmuyor"
            )

        new_vectors = _normalize_rows(new_vectors)
        for (document, _, content_hash), vector in zip(missing, new_vectors):
            vectors_by_id[int(document.song_id)] = (vector, content_hash)

    ordered_ids: list[int] = []
    seen: set[int] = set()
    for document in valid_documents:
        song_id = int(document.song_id)
        if song_id in vectors_by_id and song_id not in seen:
            ordered_ids.append(song_id)
            seen.add(song_id)
    for song_id in existing_vectors:
        if song_id not in seen:
            ordered_ids.append(song_id)
            seen.add(song_id)

    if ordered_ids:
        vectors = np.vstack(
            [vectors_by_id[song_id][0] for song_id in ordered_ids]
        )
        hashes = tuple(
            vectors_by_id[song_id][1] for song_id in ordered_ids
        )
    else:
        vectors = np.zeros((0, 0), dtype=np.float32)
        hashes = ()

    index = EmbeddingIndex(
        model_name=embedder.model_name,
        song_ids=ordered_ids,
        vectors=vectors,
        text_hashes=hashes,
    )

    if path is not None:
        index.save(path)
        if progress_callback:
            progress_callback(f"İndeks kaydedildi: {path}")

    return IndexBuildResult(
        index=index,
        added=len(missing),
        reused=reused,
        path=path,
    )


def semantic_search(
    index: EmbeddingIndex,
    query: str,
    embedder: TextEmbedder,
    *,
    top_k: int = 10,
    documents_by_id: Optional[Mapping[int, SongDocument]] = None,
    candidate_ids: Optional[Sequence[int]] = None,
    snippet_chars: int = 160,
) -> list[SearchHit]:
    """
    Doğal dil sorgusuyla korpusta anlamsal arama yapar.

    Args:
        index: Şarkı gömme indeksi.
        query: Aranacak metin.
        embedder: Sorguyu vektöre çevirecek model.
        top_k: Döndürülecek sonuç sayısı.
        documents_by_id: Başlık/sanatçı/parça bilgisi için belge eşlemesi.
        candidate_ids: Yalnızca bu şarkılar arasında ara.
        snippet_chars: Sonuç parçasının en fazla karakter sayısı.
    """
    if not query or not query.strip():
        raise ValueError("Sorgu boş olamaz")

    np = _numpy()
    query_vectors = np.asarray(
        embedder.embed_texts([query]),
        dtype=np.float32,
    )
    if query_vectors.ndim == 1:
        query_vectors = query_vectors.reshape(1, -1)
    if query_vectors.shape[0] != 1:
        raise EmbeddingError("Sorgu için tek bir vektör bekleniyordu")

    documents = documents_by_id or {}
    results = index.search(
        query_vectors[0],
        top_k=top_k,
        candidate_ids=candidate_ids,
    )

    hits: list[SearchHit] = []
    for song_id, score in results:
        document = documents.get(int(song_id))
        hits.append(
            SearchHit(
                song_id=int(song_id),
                score=score,
                title=document.title if document else "",
                artist=document.artist if document else "",
                snippet=(
                    find_snippet(document, query, max_chars=snippet_chars)
                    if document
                    else ""
                ),
            )
        )
    return hits


def similar_songs(
    index: EmbeddingIndex,
    song_id: int,
    *,
    top_k: int = 10,
    documents_by_id: Optional[Mapping[int, SongDocument]] = None,
    candidate_ids: Optional[Sequence[int]] = None,
    snippet_chars: int = 160,
) -> list[SearchHit]:
    """Bir şarkıya anlamsal olarak benzeyen şarkıları döner."""
    documents = documents_by_id or {}
    target = documents.get(int(song_id))
    query = target.title if target else ""

    results = index.similar(
        song_id,
        top_k=top_k,
        candidate_ids=candidate_ids,
    )

    hits: list[SearchHit] = []
    for hit_id, score in results:
        document = documents.get(int(hit_id))
        hits.append(
            SearchHit(
                song_id=int(hit_id),
                score=score,
                title=document.title if document else "",
                artist=document.artist if document else "",
                snippet=(
                    find_snippet(document, query, max_chars=snippet_chars)
                    if document
                    else ""
                ),
            )
        )
    return hits


class TransformerEmbedder:
    """
    Hugging Face ``transformers`` modeliyle metin gömmeleri üretir.

    Uzun şarkı sözleri örtüşen token parçalarına bölünür; parça vektörlerinin
    ortalaması alınır ve L2 normalize edilir. Model ilk kullanımda yüklenir.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        *,
        device: str = "auto",
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stride: int = DEFAULT_STRIDE,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size pozitif olmalı")
        if max_tokens <= 0:
            raise ValueError("max_tokens pozitif olmalı")
        if stride < 0 or stride >= max_tokens:
            raise ValueError("stride 0 ile max_tokens arasında olmalı")

        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.max_tokens = max_tokens
        self.stride = stride

        self._np = None
        self._torch = None
        self._tokenizer = None
        self._model = None
        self._resolved_device: Optional[str] = None
        self._token_limit = max_tokens
        self._dimension = 0

    @property
    def is_loaded(self) -> bool:
        """Model belleğe yüklendi mi?"""
        return self._model is not None

    @property
    def resolved_device(self) -> Optional[str]:
        """Modelin yüklendiği cihaz (yüklenmeden önce ``None``)."""
        return self._resolved_device

    @property
    def embedding_dim(self) -> int:
        """Vektör boyutu (model yüklenmeden önce 0)."""
        return self._dimension

    @staticmethod
    def _resolve_device(torch, requested: str) -> str:
        if requested != "auto":
            return requested
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
        return "cpu"

    def load(
        self,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        """Tokenizer ve modeli yükler; ikinci çağrıda yeniden yüklemez."""
        if self._model is not None:
            return

        np, torch, AutoModel, AutoTokenizer = _require_ml()
        if progress_callback:
            progress_callback(f"Model yükleniyor: {self.model_name}")

        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModel.from_pretrained(self.model_name)

        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = (
                tokenizer.eos_token or tokenizer.unk_token or tokenizer.sep_token
            )

        max_positions = int(
            getattr(model.config, "max_position_embeddings", 512) or 512
        )
        special_count = (
            tokenizer.num_special_tokens_to_add()
            if hasattr(tokenizer, "num_special_tokens_to_add")
            else 2
        )
        self._token_limit = max(
            1,
            min(self.max_tokens, max_positions - special_count),
        )

        device = self._resolve_device(torch, self.device)
        model.to(device)
        model.eval()

        self._np = np
        self._torch = torch
        self._tokenizer = tokenizer
        self._model = model
        self._resolved_device = device
        self._dimension = int(model.config.hidden_size)

    def _add_special_tokens(self, chunk: Sequence[int]) -> list[int]:
        """Parçaya modelin beklediği özel token'ları ekler."""
        tokenizer = self._tokenizer
        builder = getattr(tokenizer, "build_inputs_with_special_tokens", None)
        if callable(builder):
            return list(builder(list(chunk)))

        cls_id = getattr(tokenizer, "cls_token_id", None)
        sep_id = getattr(tokenizer, "sep_token_id", None)
        if cls_id is not None and sep_id is not None:
            return [cls_id, *chunk, sep_id]

        # Farklı bir özel token şablonu kullanan modeller için güvenli yol.
        text = tokenizer.decode(
            list(chunk),
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        return tokenizer.encode(text, add_special_tokens=True, verbose=False)

    def _pad_batch(self, chunk_ids: Sequence[Sequence[int]]):
        torch = self._torch
        pad_id = self._tokenizer.pad_token_id or 0
        max_length = max(len(ids) for ids in chunk_ids)

        input_ids = torch.full(
            (len(chunk_ids), max_length),
            pad_id,
            dtype=torch.long,
        )
        attention_mask = torch.zeros(
            (len(chunk_ids), max_length),
            dtype=torch.long,
        )
        for row, ids in enumerate(chunk_ids):
            if not ids:
                continue
            input_ids[row, : len(ids)] = torch.as_tensor(ids, dtype=torch.long)
            attention_mask[row, : len(ids)] = 1
        return input_ids, attention_mask

    def embed_texts(
        self,
        texts: Sequence[str],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Any:
        """Metinleri normalize edilmiş vektörlere dönüştürür."""
        values = list(texts)
        if not values:
            if self._np is None:
                return []
            return self._np.zeros(
                (0, self._dimension),
                dtype=self._np.float32,
            )

        self.load(progress_callback)
        np = self._np
        torch = self._torch

        chunks: list[list[int]] = []
        owners: list[int] = []
        for owner, text in enumerate(values):
            token_ids = self._tokenizer(
                text or "",
                add_special_tokens=False,
                verbose=False,
            )["input_ids"]
            for chunk in chunk_token_ids(
                token_ids,
                self._token_limit,
                self.stride,
            ):
                chunks.append(self._add_special_tokens(chunk))
                owners.append(owner)

        total = len(chunks)
        sums = np.zeros((len(values), self._dimension), dtype=np.float32)
        counts = np.zeros((len(values), 1), dtype=np.float32)

        for start in range(0, total, self.batch_size):
            batch = chunks[start : start + self.batch_size]
            batch_owners = owners[start : start + self.batch_size]

            input_ids, attention_mask = self._pad_batch(batch)
            input_ids = input_ids.to(self._resolved_device)
            attention_mask = attention_mask.to(self._resolved_device)

            with torch.inference_mode():
                outputs = self._model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                )

            hidden = outputs.last_hidden_state
            mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(
                min=1e-6
            )
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            vectors = pooled.detach().cpu().numpy().astype(np.float32)

            for owner, vector in zip(batch_owners, vectors):
                sums[owner] += vector
                counts[owner, 0] += 1

            if progress_callback:
                done = min(start + self.batch_size, total)
                progress_callback(f"{done}/{total} parça işlendi")

        counts = np.maximum(counts, 1.0)
        return _normalize_rows(sums / counts)

    def embed_documents(
        self,
        documents: Sequence[SongDocument],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Any:
        """Belgeleri gömme vektörlerine dönüştürür."""
        return self.embed_texts(
            [document_text(document) for document in documents],
            progress_callback=progress_callback,
        )


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_EMBEDDINGS_DIR",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "DEFAULT_STRIDE",
    "EmbeddingError",
    "EmbeddingIndex",
    "IndexBuildResult",
    "MLDependencyError",
    "ProgressCallback",
    "SearchHit",
    "TextEmbedder",
    "TransformerEmbedder",
    "build_index",
    "chunk_token_ids",
    "document_text",
    "find_snippet",
    "index_path_for_model",
    "semantic_search",
    "similar_songs",
    "text_hash",
]
