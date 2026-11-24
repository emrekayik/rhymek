import os
from typing import Optional
from dotenv import load_dotenv
import lyricsgenius


def get_genius_client(
    token: Optional[str] = None,
    timeout: int = 15,
    retries: int = 3,
    sleep_time: float = 0.5,
    verbose: bool = True,
    remove_section_headers: bool = False,
    skip_non_songs: bool = True,
) -> lyricsgenius.Genius:
    """
    Genius API istemcisini başlatır ve döndürür.
    Token belirtilmezse .env dosyasından GENIUS_TOKEN okunur.
    """
    load_dotenv()
    api_token = token or os.getenv("GENIUS_TOKEN")
    if not api_token:
        raise ValueError(
            "GENIUS_TOKEN bulunamadı! Lütfen .env dosyasını kontrol edin veya token parametresi iletin."
        )

    genius = lyricsgenius.Genius(
        access_token=api_token,
        timeout=timeout,
        retries=retries,
        sleep_time=sleep_time,
        remove_section_headers=remove_section_headers,
        skip_non_songs=skip_non_songs,
    )
    genius.verbose = verbose
    return genius
