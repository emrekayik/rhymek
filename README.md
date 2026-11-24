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
│   └── lyrics/                  # İsteğe bağlı .txt şarkı sözleri (Git tarafından yoksayılır)
│       └── Ceza/
│           ├── Holocaust.txt    # Başlık, albüm, tarih ve şarkı sözü
│           └── Suspus.txt
├── src/rhymek/
│   ├── client.py                # Genius API istemcisi
│   ├── artists.py               # Sanatçı ekleme, silme, arama ve listeleme
│   ├── songs.py                 # Şarkı sözü çekme, kaydetme ve önbellek kontrolü
│   ├── tui.py                   # Textual tabanlı tam ekran TUI dashboard
│   ├── cli.py                   # Typer, Rich ve Questionary ile zenginleştirilmiş CLI
│   └── __init__.py              # Dışa aktarılan ana fonksiyonlar
└── examples/
    └── fetch_demo.py            # Python kodu üzerinden kullanım örneği
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
  ```

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
