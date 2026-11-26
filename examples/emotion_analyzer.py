from collections import Counter
import polars as pl
import torch
from transformers import pipeline

# GPU varsa 0, yoksa CPU (-1)
device = 0 if torch.cuda.is_available() else -1

MODEL_NAME = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

print("Zero-Shot mDeBERTa-v3 modeli yükleniyor...")
classifier = pipeline(
    "zero-shot-classification",
    model=MODEL_NAME,
    device=device,
)

# Şarkı sözlerinin ruhuna uygun özel Türkçe duygu ve tema etiketleri
CANDIDATE_LABELS = [
    "öfke, isyan ve sert eleştiri",
    "hüzün, melankoli ve yalnızlık",
    "umut, neşe ve yaşama sevinci",
    "korku, kaygı ve karamsarlık",
    "özgüven, meydan okuma ve güç",
]

# Çıktıları raporda kısa göstermek için eşleştirme
SHORT_LABELS = {
    "öfke, isyan ve sert eleştiri": "Öfke / İsyan",
    "hüzün, melankoli ve yalnızlık": "Hüzün / Melankoli",
    "umut, neşe ve yaşama sevinci": "Umut / Neşe",
    "korku, kaygı ve karamsarlık": "Korku / Kaygı",
    "özgüven, meydan okuma ve güç": "Özgüven / Meydan Okuma",
}


def analyze_song_zero_shot(
    lines: list[str], confidence_threshold: float = 0.35
) -> dict:
    # 3 kelimeden kısa satırları ele
    valid_lines = [line for line in lines if len(line.split()) >= 3]

    if not valid_lines:
        return {"dominant_emotion": "Belirsiz", "emotion_distribution": "{}"}

    # Türkçe cümle yapısına uygun hipotez şablonu (Doğruluğu ciddi oranda artırır)
    results = classifier(
        valid_lines,
        candidate_labels=CANDIDATE_LABELS,
        hypothesis_template="Bu şarkı sözü {} duygusunu yansıtıyor.",
        batch_size=16,
    )

    selected_emotions = []
    for res in results:
        top_label = res["labels"][0]
        top_score = res["scores"][0]

        # 5 seçenek olduğu için rastgele tahmin %20'dir; %35 üzeri anlamlı kabul edilir
        if top_score >= confidence_threshold:
            selected_emotions.append(SHORT_LABELS[top_label])

    if not selected_emotions:
        return {"dominant_emotion": "Karışık", "emotion_distribution": "{}"}

    counts = Counter(selected_emotions)
    total = len(selected_emotions)

    distribution = {
        emotion: round((count / total) * 100, 1)
        for emotion, count in counts.most_common()
    }

    dominant = counts.most_common(1)[0][0]

    return {
        "dominant_emotion": dominant,
        "emotion_distribution": str(distribution),
    }


def test_sample_lines():
    """Modelin mecazları nasıl anladığını görmek için hızlı dize testi."""
    samples = [
        "Göz gözü görmüyor, hep pus, takipteler ses etme sus",  # Suspus
        "Ormandaki ağaç kadar yalnızlık yakından",  # 366.Gün
        "Kanadımı kırdılar, uçamadım anne, savaşa soktular",  # Med Cezir
        "Hızlı söyleyen ben değilim, yavaş dinleyen sizlersiniz hep",  # Suspus
        "Sonbaharda dökülen yapraktım, ilkbaharda geri geldim ben",  # Med Cezir
    ]

    print("\n--- Örnek Dize Doğruluk Testi ---")
    results = classifier(
        samples,
        candidate_labels=CANDIDATE_LABELS,
        hypothesis_template="Bu şarkı sözü {} duygusunu yansıtıyor.",
    )
    for res in results:
        print(f"Dize  : {res['sequence']}")
        print(
            f"Tahmin: {SHORT_LABELS[res['labels'][0]]} (Skor: %{round(res['scores'][0]*100, 1)})\n"
        )


def main():
    # Önce 5 örnek dizede modelin kalitesini doğrula
    test_sample_lines()

    # Ardından tüm Parquet veri setini analiz et
    df = pl.read_parquet("data/lyrics_clean.parquet")

    dominant_list = []
    dist_list = []

    print("--- Şarkı Bazlı Analiz Başlıyor ---\n")
    for row in df.iter_rows(named=True):
        res = analyze_song_zero_shot(row["lines"])
        dominant_list.append(res["dominant_emotion"])
        dist_list.append(res["emotion_distribution"])

        print(f"🎵 {row['artist']} - {row['title']}")
        print(f"   Baskın Duygu : {res['dominant_emotion']}")
        print(f"   Dağılım      : {res['emotion_distribution']}\n")

    df = df.with_columns([
        pl.Series("dominant_emotion", dominant_list),
        pl.Series("emotion_distribution", dist_list),
    ])

    df.write_parquet("data/lyrics_zeroshot.parquet")
    print(
        "Tüm sonuçlar 'data/lyrics_zeroshot.parquet' dosyasına kaydedildi."
    )


if __name__ == "__main__":
    main()