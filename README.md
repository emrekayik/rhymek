[![rhymek: NLP Toolkit for Turkish Songs](https://ascii.rest/banner/rhymek.svg?color=f97316&tagline=NLP%20Toolkit%20for%20Turkish%20Songs)](https://ascii.rest/banner/)

A Python library for Natural Language Processing (NLP) for Turkish Songs.

---

## 🚀 Sanatçı ve Şarkı Sözü Yönetimi

`rhymek`, sanatçı ID'lerini ve isimlerini merkezi bir dosyada toplayıp (`data/artists.json`), bu dosyadaki sanatçıların şarkı sözlerini Genius API üzerinden toplu veya tek tek çekmenizi sağlar.

### 📁 Proje Yapısı

```text
rhymek/
├── data/
│   ├── artists.json             # Sanatçı ID ve isim listesi
│   └── lyrics/                  # İndirilen şarkı sözleri ve metaveriler
│       └── Ceza/
│           ├── Holocaust.txt    # Şarkı sözü (başlık, albüm, tarih ile)
│           ├── Holocaust.json   # Yapılandırılmış JSON metaverisi
│           └── _summary.json    # Sanatçıya ait çekilen şarkıların özeti
├── src/rhymek/
│   ├── client.py                # Genius API istemcisi
│   ├── artists.py               # Sanatçı ekleme, silme, arama ve listeleme
│   ├── songs.py                 # Şarkı sözü çekme ve kaydetme
│   └── cli.py                   # Terminal arayüzü ve CLI komutları
└── examples/
    └── fetch_demo.py            # Kod üzerinden kullanım örneği
```

---

### 1. Kurulum ve Ortam Değişkeni

`.env` dosyanızda Genius API erişim anahtarınızın tanımlı olduğundan emin olun:

```env
GENIUS_TOKEN="your_genius_client_access_token_here"
```

---

### 2. Sanatçı Listesi (`data/artists.json`)

Sanatçıları ister doğrudan `data/artists.json` dosyasını düzenleyerek, ister CLI veya Python fonksiyonları üzerinden ekleyebilirsiniz:

```json
[
  {
    "id": 11586,
    "name": "Ceza"
  },
  {
    "id": 1421,
    "name": "Sagopa Kajmer"
  },
  {
    "id": 195369,
    "name": "Ezhel"
  }
]
```

---

### 3. Komut Satırı (CLI) Kullanımı

#### 📋 Kayıtlı Sanatçıları ve Durumu Listele
```bash
uv run python -m rhymek list
```

#### ➕ Yeni Sanatçı Ekle
Genius API'de otomatik arar, ID'sini çözer ve `data/artists.json` dosyasına ekler:
```bash
uv run python -m rhymek add "Şanışer"
# veya ID biliyorsanız doğrudan:
uv run python -m rhymek add "Ceza" --id 11586
```

#### 🎵 Şarkı Sözlerini Çek
- **Tüm kayıtlı sanatçıların şarkılarını çekmek için:**
  ```bash
  uv run python -m rhymek fetch --all --max-songs 10
  ```

- **Sadece belirli bir sanatçının şarkılarını çekmek için:**
  ```bash
  uv run python -m rhymek fetch --artist "Ceza" --max-songs 5
  ```

#### 💬 Etkileşimli Menü
Hiçbir parametre vermeden çalıştırırsanız interaktif terminal arayüzü açılır:
```bash
uv run python -m rhymek
```

---

### 4. Python Kodundan Kullanım

Kendi NLP veya analiz betiklerinizde doğrudan `rhymek` fonksiyonlarını kullanabilirsiniz:

```python
from rhymek import (
    load_artists,
    add_artist,
    fetch_songs_for_artist,
    fetch_all_artists_songs,
)

# 1. Kayıtlı sanatçıları oku
artists = load_artists()
for artist in artists:
    print(artist["name"], artist["id"])

# 2. Yeni sanatçı ekle (ID otomatik bulunur)
add_artist("Defkhan")

# 3. Belirli bir sanatçının en popüler 5 şarkısını çek
fetch_songs_for_artist(artist_id=11586, artist_name="Ceza", max_songs=5)

# 4. data/artists.json dosyasındaki tüm sanatçıların şarkılarını çek
fetch_all_artists_songs(max_songs_per_artist=10)
```
