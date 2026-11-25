"""
Analizörler için ortak arayüz.

Yeni bir NLP analizi eklemek için :class:`Analyzer` alt sınıfı yazıp
``name`` ve ``analyze`` üyelerini doldurmak yeterlidir.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Mapping

from rhymek.nlp.types import SongDocument


class Analyzer(ABC):
    """Tek bir şarkı üzerinde çalışan analiz adımı."""

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    @abstractmethod
    def analyze(self, document: SongDocument) -> Mapping[str, Any]:
        """Belgeyi analiz edip JSON'a yazılabilir bir sonuç döner."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"


__all__ = ["Analyzer"]
