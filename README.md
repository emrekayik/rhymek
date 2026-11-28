[![rhymek: NLP Toolkit for Turkish Songs](https://ascii.rest/banner/rhymek.svg?color=f97316&tagline=NLP%20Toolkit%20for%20Turkish%20Songs)](https://ascii.rest/banner/)

A Python library for Natural Language Processing (NLP) for Turkish Songs.

---

## 🚀 Sanatçı ve Şarkı Sözü Yönetimi (CLI & TUI)

`rhymek`, sanatçı ID'lerini ve isimlerini merkezi bir dosyada toplayıp (`data/artists.json`), bu dosyadaki sanatçıların şarkı sözlerini Genius API üzerinden toplu veya tek tek çekmenizi sağlar.

Proje hem **modern bir CLI** (Typer + Rich), hem **ok tuşlu interaktif wizard** (Questionary), hem de **tam ekran Terminal Arayüzü** (Textual TUI) sunar.

### 📁 Proje Yapısı

```text
rhymek/
├── data/
│   ├── artists.json             # Sanatçı ID ve isim listesi
│   ├── songs.jsonl              # Tüm şarkıların toplu JSONL veri seti (Asla silinmez, eklenir)
│   ├── fetch_state.json         # Çekim durumu: taranan sanatçılar ve başarısız şarkılar
│   ├── embeddings/              # Transformer gömme indeksleri (Git tarafından yoksayılır)
│   └── lyrics/                  # İsteğe bağlı .txt şarkı sözleri (Git tarafından yoksayılır)
│       └── Ceza/
│           ├── Holocaust.txt    # Başlık, albüm, tarih ve şarkı sözü
│           └── Suspus.txt
├── src/rhymek/
│   ├── client.py                # Genius API istemcisi
│   ├── artists.py               # Sanatçı ekleme, silme, arama ve listeleme
│   ├── songs.py                 # Şarkı sözü çekme, kaydetme ve önbellek kontrolü
│   ├── nlp/
│   │   ├── types.py             # Token, satır, kıta ve belge modelleri
│   │   ├── text.py              # Türkçe normalizasyon ve tokenizasyon
│   │   ├── corpus.py            # JSONL → SongDocument yükleyicisi
│   │   ├── embeddings.py        # Transformer gömmeleri ve anlamsal arama
│   │   ├── pipeline.py          # Sıralı analiz hattı
│   │   ├── rhyme.py             # Kafiye altyapısı (iskelet)
│   │   ├── syllables.py         # Heceleme altyapısı (iskelet)
│   │   └── analyzers/           # Analyzer arayüzü ve istatistik analizi
│   ├── tui.py                   # Textual tabanlı tam ekran TUI dashboard
│   ├── cli.py                   # Typer, Rich ve Questionary ile zenginleştirilmiş CLI
│   └── __init__.py              # Dışa aktarılan ana fonksiyonlar
└── examples/
    ├── fetch_demo.py            # Python kodu üzerinden veri çekme örneği
    └── nlp_analysis.py          # NLP korpus analizi ve özel analizör örneği
```

---

### 1. Kurulum ve Ortam Değişkeni

`.env` dosyanızda Genius API erişim anahtarınızın tanımlı olduğundan emin olun:

```env
GENIUS_TOKEN="your_genius_client_access_token_here"
```

---

### 2. Kullanım Modları

#### 🖥️ Mod 1: Tam Ekran TUI Dashboard (Textual)

Görsel ve modern bir terminal arayüzü ile sol tarafta sanatçılarınızı görebilir, yeni sanatçı ekleyip silebilir, sağ tarafta seçili sanatçının indirilmiş şarkılarını tablo halinde inceleyebilir ve canlı log takibiyle şarkıları tek tıkla indirebilirsiniz.

```bash
uv run rhymek tui
```

- **Kısayollar:**
  - `q`: Çıkış
  - `r`: Sanatçı listesini ve tabloları yenile
  - `f`: Seçili sanatçının şarkılarını indir

---

#### 💬 Mod 2: İnteraktif Ok Tuşlu Menü (Questionary)

Hiçbir parametre vermeden çalıştırdığınızda kullanıcı dostu interaktif terminal menüsü açılır:

```bash
uv run rhymek
```

- Ok tuşlarıyla menüler arasında geçiş yapabilirsiniz.
- Şarkı indirme adımında **boşluk tuşuyla** birden fazla sanatçıyı kutucuklarla işaretleyip toplu indirebilirsiniz.

---

#### ⚡ Mod 3: Doğrudan Komut Satırı (CLI - Typer & Rich)

Hızlı işlemler ve otomasyon scriptleri için Rich destekli zengin komutlar:

- **📋 Kayıtlı Sanatçıları Tablo Halinde Listele:**
  ```bash
  uv run rhymek list
  ```

- **➕ Yeni Sanatçı Ekle (Genius'ta otomatik arar ve ID'yi çözer):**
  ```bash
  uv run rhymek add "Ezhel"
  # veya bilinen ID ile:
  uv run rhymek add "Ceza" --id 11586
  ```

- **🗑️ Sanatçı Sil:**
  ```bash
  uv run rhymek remove "Ezhel"
  ```

- **⬇️ Şarkı Sözlerini Çek:**
  ```bash
  # Belirli bir sanatçının en popüler 5 şarkısını çek:
  uv run rhymek fetch --artist "Ceza" --max-songs 5

  # Listedeki tüm sanatçıların şarkılarını çek:
  uv run rhymek fetch --all --max-songs 10

  # Daha önce çekilenleri atlamadan yeniden tara:
  uv run rhymek fetch --all --max-songs 10 --force
  ```

  > **Tekrarlı çekim koruması:** Zaten `data/songs.jsonl` içinde olan şarkıların sözleri
  > yeniden indirilmez. Aynı parametrelerle tamamen taranmış sanatçılar hiç API'ye
  > gitmeden atlanır; sözü bulunamayan şarkılar `data/fetch_state.json` içine yazılır ve
  > tekrar denenmez. Yeni çıkan şarkıları veya başarısız olanları yeniden denemek için
  > `--force` kullanın.

---

### 3. Python Kodundan Kullanım

```python
from rhymek import (
    load_artists,
    add_artist,
    fetch_songs_for_artist,
    fetch_all_artists_songs,
    launch_tui,
)

# 1. Kayıtlı sanatçıları oku
artists = load_artists()

# 2. Yeni sanatçı ekle (ID Genius API'den otomatik çekilir)
add_artist("Defkhan")

# 3. Şarkıları çek
fetch_songs_for_artist(artist_id=11586, artist_name="Ceza", max_songs=5)

# 4. İsterseniz kod içinden TUI'yi başlatın
# launch_tui()
```

---

### 4. NLP Altyapısı

`rhymek.nlp` paketi; kural tabanlı metin işleme, korpus yükleme, analiz
pipeline'ı ve Hugging Face `transformers` + `torch` tabanlı anlamsal arama
altyapısını sağlar. Kafiye ve heceleme modülleri hâlâ arayüz sözleşmesidir.

```python
from rhymek.nlp import Pipeline, StatsAnalyzer, load_corpus, summarize_corpus

# JSONL korpusunu belge nesnelerine dönüştür
docs = load_corpus(artist="Ceza", limit=50, min_tokens=20)

# Tek şarkıda analiz hattı çalıştır
result = Pipeline([StatsAnalyzer(top_n=5)]).run(docs[0])
print(result.get("stats")["tokens"])

# Korpus geneli özet
print(summarize_corpus(docs)["unique_tokens"])
```

| Modül | Durum | İçerik |
| --- | --- | --- |
| `rhymek.nlp.types` | ✅ | `Token`, `Line`, `Stanza`, `SongDocument`, `AnalysisResult` |
| `rhymek.nlp.text` | ✅ | Türkçe küçük harf, normalizasyon, tokenize, kıta/satır ayrıştırma |
| `rhymek.nlp.corpus` | ✅ | JSONL yükleme, sanatçı/token filtresi, tekilleştirme |
| `rhymek.nlp.analyzers` | ✅ | `Analyzer` arayüzü, `StatsAnalyzer`, `summarize_corpus` |
| `rhymek.nlp.pipeline` | ✅ | Sıralı analiz hattı (`Pipeline`) |
| `rhymek.nlp.embeddings` | ✅ | Transformer gömmeleri, kosinüs araması, artımlı önbellek |
| `rhymek.nlp.rhyme` | 🚧 | Satır sonu adayları hazır; `rhyme_key`/`rhyme_groups` iskelet |
| `rhymek.nlp.syllables` | 🚧 | Ünlü sayımı hazır; `syllabify`/`count_syllables` iskelet |

CLI üzerinden hızlı korpus özeti:

```bash
uv run rhymek nlp stats --limit 50
uv run rhymek nlp stats --artist "Ceza" --top 20 --json
```

#### Transformer tabanlı anlamsal arama

Torch ve transformers isteğe bağlı `ml` ekstrasındadır; temel kurulum hafif kalır:

```bash
uv sync --extra ml
```

İlk `embed` çalıştırmasında model (~470 MB) indirilir; sonraki çalıştırmalarda
yalnızca yeni veya sözleri değişmiş şarkılar hesaplanır.

```bash
# Tüm korpus için gömme indeksi
uv run rhymek nlp embed

# Hızlı deneme / sanatçı filtresi
uv run rhymek nlp embed --artist "Ceza" --limit 20

# Doğal dil ile anlamsal arama
uv run rhymek nlp search "yalnızlık ve sokak" --top 5
uv run rhymek nlp search "aşk" --artist "Ceza" --json

# Benzer şarkılar (kayıtlı vektörlerden, model yüklemez)
uv run rhymek nlp similar "Suspus" --top 5
uv run rhymek nlp similar --id 1913073
```

- Varsayılan model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- `--device auto` macOS'ta MPS'i, Linux'ta CUDA'yı, yoksa CPU'yu seçer.
- Vektörler `data/embeddings/<model>.npz` altında tutulur (git'e girmez).
- `--force` seçili şarkıları yeniden hesaplar; `--artist`/`--limit` ile alt küme seçilebilir.
- Uzun şarkılar 256 token'lık örtüşen parçalara bölünür; parça vektörlerinin ortalaması alınır.
- `rhymek` interaktif menüsünde **🔎 Anlamsal Şarkı Arama** seçeneği de bulunur.

Python API:

```python
from rhymek.nlp import (
    TransformerEmbedder,
    build_index,
    load_corpus,
    semantic_search,
)

docs = load_corpus(limit=100)
docs_by_id = {doc.song_id: doc for doc in docs}
embedder = TransformerEmbedder()  # ilk kullanımda modeli yükler
built = build_index(docs, embedder=embedder)

hits = semantic_search(
    built.index,
    "yalnızlık ve sokak",
    embedder,
    top_k=5,
    documents_by_id=docs_by_id,
)
for hit in hits:
    print(f"{hit.score:.3f}  {hit.title} — {hit.artist}")
```

Modeli bir kez yükleyip farklı sorgular için yeniden kullanabilirsiniz.

Örnek analiz betiği (`StatsAnalyzer` + özel `LineEndingAnalyzer` + pipeline):

```bash
# İlk 10 şarkıyı tablo halinde analiz et
uv run python examples/nlp_analysis.py

# Sanatçı filtresi ve JSON çıktısı
uv run python examples/nlp_analysis.py --artist "Ceza" --limit 20 --json

# Şarkı başına sonuçları JSONL olarak dışa aktar
uv run python examples/nlp_analysis.py --all --output nlp_results.jsonl
```

Testler:

```bash
uv run python -m unittest discover -s tests -v
```

