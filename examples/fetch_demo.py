"""
Örnek kullanım:
data/artists.json dosyasından sanatçıları okuyup şarkılarını data/songs.jsonl'e ekler.
"""

from rhymek import (
    load_artists,
    add_artist,
    fetch_songs_for_artist,
    fetch_all_artists_songs,
    load_songs_from_jsonl,
)


def main():
    # 1. Kayıtlı sanatçıları listele
    artists = load_artists()
    print(f"Kayıtlı Sanatçılar: {artists}")

    # 2. İsterseniz kod içinden yeni bir sanatçı ekleyin:
    # add_artist("Saian")

    # 3. Belirli bir sanatçının en popüler 2 şarkısını çek (data/songs.jsonl'e eklenir):
    if artists:
        first_artist = artists[0]
        print(f"\n{first_artist['name']} için şarkılar çekiliyor...")
        fetch_songs_for_artist(
            artist_id=first_artist["id"],
            artist_name=first_artist["name"],
            max_songs=2,
            sort="popularity",
        )

    # 4. JSONL dosyasındaki kayıtlı tüm şarkıları oku:
    all_songs = load_songs_from_jsonl()
    print(f"\nToplam JSONL şarkı sayısı: {len(all_songs)}")
    for s in all_songs:
        print(f"  • [{s.get('artist')}] {s.get('title')} ({s.get('release_date')})")


if __name__ == "__main__":
    main()
