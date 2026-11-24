"""
Örnek kullanım:
data/artists.json dosyasından sanatçıları okuyup şarkılarını çeker.
"""

from rhymek import (
    load_artists,
    add_artist,
    fetch_songs_for_artist,
    fetch_all_artists_songs,
)


def main():
    # 1. Kayıtlı sanatçıları listele
    artists = load_artists()
    print(f"Kayıtlı Sanatçılar: {artists}")

    # 2. İsterseniz kod içinden yeni bir sanatçı ekleyin:
    # add_artist("Ezhel")

    # 3. Belirli bir sanatçının en popüler 3 şarkısını çek:
    if artists:
        first_artist = artists[0]
        print(f"\n{first_artist['name']} için 2 şarkı çekiliyor...")
        fetch_songs_for_artist(
            artist_id=first_artist["id"],
            artist_name=first_artist["name"],
            max_songs=2,
            sort="popularity",
        )

    # 4. Veya listedeki tüm sanatçıların şarkılarını çekmek için:
    # fetch_all_artists_songs(max_songs_per_artist=5)


if __name__ == "__main__":
    main()
