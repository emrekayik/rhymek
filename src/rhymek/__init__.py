import os
from dotenv import load_dotenv
import lyricsgenius

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# API anahtarını güvenli bir şekilde al ve doğrula
token = os.getenv("GENIUS_TOKEN")
if not token:
    raise ValueError("genius.com API token is missing! Please check .env file.")

genius = lyricsgenius.Genius(token)


def main() -> None:
    print("Hello from rhymek!")
    # Örnek kullanım:
    song = genius.search_song("Bohemian Rhapsody", "Queen")
    if song:
        print(song.lyrics)


if __name__ == "__main__":
    main()