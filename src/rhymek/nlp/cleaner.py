import re
import polars as pl  # Çok hızlı veri işleme için


def clean_lyrics(raw_text: str) -> str:
    if not raw_text:
        return ""

    # 1. En baştaki ["Şarkı Adı" için şarkı sözleri] satırını kaldır
    text = re.sub(r'^\["[^"]+" için şarkı sözleri\]\s*', "", raw_text)

    # 2. [Nakarat], [Verse 1: Ceza] gibi köşeli parantez etiketlerini kaldır
    text = re.sub(r"\[.*?\]", "", text)

    # 3. Satır sonu/içi parantez ad-lib'leri kaldır: (Pus, pus, pus), (Hah)
    text = re.sub(r"\([^)]*\)", "", text)

    # 4. Kekeleme efektlerini normalize et (Örn: Mik-mik-mikrofon -> mikrofon)
    text = re.sub(
        r"\b([a-zA-ZçğıöşüÇĞİÖŞÜ]{1,4}-){2,}([a-zA-ZçğıöşüÇĞİÖŞÜ]+)\b",
        r"\2",
        text,
        flags=re.IGNORECASE,
    )

    # 5. Em-dash (─) ve fazla boşlukları temizle
    text = text.replace("─", " ")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    return "\n".join(lines)


def calculate_ttr(clean_text: str) -> float:
    """Kelime Çeşitliliği (Type-Token Ratio) hesaplar."""
    words = re.findall(r"\b\w+\b", clean_text.lower())
    if not words:
        return 0.0
    return round(len(set(words)) / len(words), 3)


def process_dataset(jsonl_path: str, parquet_path: str):
    # JSONL dosyasını Polars ile oku
    df = pl.read_ndjson(jsonl_path)

    # Temizlenmiş sözler ve temel istatistik sütunlarını oluştur
    df = df.with_columns([
        pl.col("lyrics")
        .map_elements(clean_lyrics, return_dtype=pl.Utf8)
        .alias("clean_lyrics")
    ])

    df = df.with_columns([
        pl.col("clean_lyrics")
        .map_elements(lambda x: x.split("\n"), return_dtype=pl.List(pl.Utf8))
        .alias("lines"),
        pl.col("clean_lyrics")
        .map_elements(calculate_ttr, return_dtype=pl.Float64)
        .alias("lexical_diversity"),
    ])

    # Satır sayısını ve toplam kelime sayısını ekle
    df = df.with_columns([
        pl.col("lines").list.len().alias("line_count"),
        pl.col("clean_lyrics")
        .map_elements(lambda x: len(x.split()), return_dtype=pl.Int64)
        .alias("word_count"),
    ])

    # Parquet olarak kaydet
    df.write_parquet(parquet_path)
    print(f"Başarıyla kaydedildi: {parquet_path} | Toplam Şarkı: {len(df)}")
    print(
        df.select([
            "title",
            "artist",
            "line_count",
            "word_count",
            "lexical_diversity",
        ])
    )

__ALL__ = ["clean_lyrics", "calculate_ttr", "process_dataset"]