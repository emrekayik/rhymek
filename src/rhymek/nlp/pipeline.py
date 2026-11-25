"""
Analizörleri sırayla çalıştıran basit pipeline altyapısı.

Örnek:
    >>> from rhymek.nlp import Pipeline, StatsAnalyzer, load_corpus
    >>> docs = load_corpus(limit=1)
    >>> result = Pipeline([StatsAnalyzer()]).run(docs[0])
    >>> result.get("stats")["tokens"]
"""

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from rhymek.nlp.analyzers.base import Analyzer
from rhymek.nlp.analyzers.stats import StatsAnalyzer
from rhymek.nlp.types import AnalysisResult, SongDocument


class Pipeline:
    """Sıralı analiz hattı."""

    def __init__(self, analyzers: Optional[Sequence[Analyzer]] = None) -> None:
        self._analyzers: List[Analyzer] = []
        for analyzer in analyzers or ():
            self.add(analyzer)

    @property
    def analyzers(self) -> Tuple[Analyzer, ...]:
        """Hattaki analizörler."""
        return tuple(self._analyzers)

    @property
    def analyzer_names(self) -> Tuple[str, ...]:
        """Hattaki analizör adları."""
        return tuple(analyzer.name for analyzer in self._analyzers)

    def add(self, analyzer: Analyzer) -> "Pipeline":
        """
        Hatta yeni bir analizör ekler.

        Aynı ``name`` değerine sahip ikinci bir analizör eklenirse
        :class:`ValueError` yükseltilir.
        """
        if not isinstance(analyzer, Analyzer):
            raise TypeError("analyzer bir Analyzer örneği olmalı")
        if not analyzer.name:
            raise ValueError("analyzer.name boş olamaz")
        if analyzer.name in self.analyzer_names:
            raise ValueError(f"'{analyzer.name}' adlı analizör zaten ekli")
        self._analyzers.append(analyzer)
        return self

    def run(self, document: SongDocument) -> AnalysisResult:
        """Tüm analizörleri tek bir belge üzerinde çalıştırır."""
        values: Dict[str, object] = {
            analyzer.name: analyzer.analyze(document)
            for analyzer in self._analyzers
        }
        return AnalysisResult(
            song_id=document.song_id,
            title=document.title,
            artist=document.artist,
            values=values,
        )

    def run_corpus(self, documents: Iterable[SongDocument]) -> List[AnalysisResult]:
        """Tüm analizörleri her belge için çalıştırır."""
        return [self.run(document) for document in documents]


def default_pipeline() -> Pipeline:
    """Varsayılan (şu an yalnızca istatistik) analiz hattını döner."""
    return Pipeline([StatsAnalyzer()])


__all__ = ["Pipeline", "default_pipeline"]
