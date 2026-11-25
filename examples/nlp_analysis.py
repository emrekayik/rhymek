#!/usr/bin/env python3
"""
Rhymek NLP altyapısı için örnek analiz betiği.

Bu örnek şunları gösterir:

1. ``load_corpus`` ile JSONL veri setini ``SongDocument`` nesnelerine dönüştürme
2. ``StatsAnalyzer`` ile hazır istatistik analizini çalıştırma
3. ``Analyzer`` alt sınıfı yazarak kendi analizörünü ekleme
4. ``Pipeline`` ile analizörleri sırayla çalıştırma
5. Sonuçları tablo, JSON veya JSONL olarak dışa aktarma

Kullanım::

    uv run python examples/nlp_analysis.py
    uv run python examples/nlp_analysis.py --artist "Ceza" --limit 20
    uv run python examples/nlp_analysis.py --limit 50 --json
    uv run python examples/nlp_analysis.py --all --output nlp_results.jsonl

Not: ``LineEndingAnalyzer`` gerçek kafiye tespiti yapmaz. Yalnızca satır sonu
kelimelerinin birebir tekrarına bakar; fonetik kafiye için
``rhymek.nlp.rhyme.rhyme_key`` ileride doldurulacaktır.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping

from rich.console import Console
from rich.table import Table

from rhymek.nlp import (
    AnalysisResult,
    Analyzer,
    Pipeline,
    SongDocument,
    StatsAnalyzer,
    count_vowels,
    line_endings,
    load_corpus,
    summarize_corpus,
)

console = Console()


class LineEndingAnalyzer(Analyzer):
    """Satır sonlarını inceleyen örnek (özel) analizör."""

    name = "line_endings"
    description = "Satır sonu kelimeleri, tekrarlar ve hece sinyali"

    def analyze(self, document: SongDocument) -> Mapping[str, Any]:
        endings = [token.normalized for token in line_endings(document)]
        counts = Counter(endings)
        repeated = {
            token: count for token, count in counts.most_common() if count > 1
        }
        vowel_counts = [count_vowels(token) for token in endings]

        return {
            "endings": len(endings),
            "unique_endings": len(counts),
            "repeated_endings": repeated,
            # Heceleme henüz uygulanmadığı için ünlü sayısı kaba bir sinyal.
            "avg_vowels_per_ending": (
                round(sum(vowel_counts) / len(vowel_counts), 2)
                if vowel_counts
                else 0.0
            ),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rhymek NLP altyapısı örnek analizi",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="JSONL korpus dosyası (varsayılan: data/songs.jsonl)",
    )
    parser.add_argument(
        "--artist",
        "-a",
        default=None,
        help="Sanatçı adına göre filtrele (Türkçe büyük/küçük harf duyarsız)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="En fazla kaç şarkı işlensin (varsayılan: 10, --all ile sınırsız)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Tüm korpusu işle (--limit değerini yok sayar)",
    )
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=0,
        help="Bu token sayısından kısa şarkıları atla",
    )
    parser.add_argument(
        "--top",
        "-t",
        type=int,
        default=10,
        help="Tablolarda gösterilecek kayıt sayısı (varsayılan: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Konsol tablosu yerine JSON çıktısı ver",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Şarkı başına analiz sonuçlarını bu JSONL dosyasına yaz",
    )
    return parser.parse_args()


def build_report(
    documents: List[SongDocument],
    results: List[AnalysisResult],
    *,
    top_n: int,
) -> Dict[str, Any]:
    """Korpus özeti + şarkı başına sonuçlardan JSON'a uygun rapor üretir."""
    summary = summarize_corpus(documents, top_n=top_n)

    corpus_endings: Counter = Counter()
    for document in documents:
        corpus_endings.update(
            token.normalized for token in line_endings(document)
        )

    return {
        "corpus": summary,
        "top_line_endings": [
            {"token": token, "count": count}
            for token, count in corpus_endings.most_common(top_n)
        ],
        "songs": [
            {
                "song_id": result.song_id,
                "title": result.title,
                "artist": result.artist,
                "analyses": dict(result.values),
            }
            for result in results
        ],
    }


def print_report(report: Dict[str, Any], *, top_n: int) -> None:
    """Raporu Rich tablolarıyla ekrana basar."""
    summary = report["corpus"]

    console.print(
        "\n[bold magenta]🎵 Rhymek NLP Örnek Analizi[/bold magenta]\n"
    )

    summary_table = Table(
        title="📊 [bold cyan]Korpus Özeti[/bold cyan]",
        header_style="bold magenta",
        border_style="cyan",
        show_header=False,
    )
    summary_table.add_column("Metrik", style="bold white")
    summary_table.add_column("Değer", justify="right", style="bold yellow")

    for key, label in [
        ("songs", "Şarkı"),
        ("stanzas", "Kıta"),
        ("lines", "Satır"),
        ("section_headers", "Bölüm başlığı"),
        ("tokens", "Token"),
        ("unique_tokens", "Benzersiz token"),
        ("type_token_ratio", "Type/token oranı"),
    ]:
        summary_table.add_row(label, str(summary[key]))
    console.print(summary_table)

    token_table = Table(
        title=f"🔝 [bold cyan]En Sık {top_n} Token[/bold cyan]",
        header_style="bold magenta",
        border_style="cyan",
    )
    token_table.add_column("#", style="dim", width=4)
    token_table.add_column("Token", style="bold white")
    token_table.add_column("Frekans", justify="right", style="bold yellow")
    for rank, item in enumerate(summary["top_tokens"], 1):
        token_table.add_row(str(rank), item["token"], str(item["count"]))
    console.print(token_table)

    endings_table = Table(
        title="🔚 [bold cyan]En Sık Satır Sonları[/bold cyan]",
        header_style="bold magenta",
        border_style="cyan",
    )
    endings_table.add_column("#", style="dim", width=4)
    endings_table.add_column("Kelime", style="bold white")
    endings_table.add_column("Tekrar", justify="right", style="bold yellow")
    for rank, item in enumerate(report["top_line_endings"], 1):
        endings_table.add_row(str(rank), item["token"], str(item["count"]))
    console.print(endings_table)

    songs_table = Table(
        title="🎼 [bold cyan]Şarkı Başına Analiz[/bold cyan]",
        header_style="bold magenta",
        border_style="cyan",
    )
    songs_table.add_column("Şarkı", style="bold white")
    songs_table.add_column("Sanatçı", style="dim")
    songs_table.add_column("Token", justify="right")
    songs_table.add_column("Satır sonu", justify="right")
    songs_table.add_column("Tekrar eden", justify="right")
    songs_table.add_column("Ünlü/satır sonu", justify="right")

    for song in report["songs"]:
        stats = song["analyses"]["stats"]
        endings = song["analyses"]["line_endings"]
        songs_table.add_row(
            song["title"] or "(başlıksız)",
            song["artist"] or "-",
            str(stats["tokens"]),
            str(endings["endings"]),
            str(sum(endings["repeated_endings"].values())),
            str(endings["avg_vowels_per_ending"]),
        )
    console.print(songs_table)


def main() -> int:
    args = parse_args()

    load_kwargs: Dict[str, Any] = {
        "artist": args.artist,
        "min_tokens": args.min_tokens,
        "limit": None if args.all else args.limit,
    }
    if args.file is not None:
        load_kwargs["filepath"] = args.file

    documents = load_corpus(**load_kwargs)
    if not documents:
        console.print(
            "[yellow]⚠️ Kriterlere uyan şarkı bulunamadı. "
            "Önce `uv run rhymek fetch --all` ile veri çekin.[/]"
        )
        return 1

    pipeline = Pipeline(
        [
            StatsAnalyzer(top_n=args.top),
            LineEndingAnalyzer(),
        ]
    )
    results = pipeline.run_corpus(documents)
    report = build_report(documents, results, top_n=args.top)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            for song in report["songs"]:
                handle.write(
                    json.dumps(song, ensure_ascii=False) + "\n"
                )
        console.print(
            f"[green]✓[/] Şarkı başına sonuçlar yazıldı: "
            f"[blue]{args.output}[/]"
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report, top_n=args.top)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
