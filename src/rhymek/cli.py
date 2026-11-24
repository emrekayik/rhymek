import argparse
import sys
from pathlib import Path
from typing import Optional

from rhymek.artists import (
    DEFAULT_ARTISTS_FILE,
    add_artist,
    load_artists,
    remove_artist,
    search_genius_artists,
)
from rhymek.songs import (
    DEFAULT_LYRICS_DIR,
    fetch_all_artists_songs,
    fetch_songs_for_artist,
)


def interactive_menu() -> None:
    """Etkileşimli terminal arayüzü."""
    print("=" * 50)
    print("        RHYMEK - Şarkı ve Sanatçı Yöneticisi")
    print("=" * 50)

    while True:
        print("\nİşlem seçin:")
        print("  [1] Kayıtlı sanatçıları listele")
        print("  [2] Yeni sanatçı ara ve listeye ekle")
        print("  [3] Listedeki TÜM sanatçıların şarkılarını çek")
        print("  [4] Tek bir sanatçının şarkılarını çek")
        print("  [5] Sanatçı sil")
        print("  [0] Çıkış")

        choice = input("\nSeçiminiz (0-5): ").strip()

        if choice == "1":
            artists = load_artists()
            if not artists:
                print("Henüz kayıtlı sanatçı yok. data/artists.json dosyasını veya [2] seçeneğini kullanın.")
            else:
                print(f"\nKayıtlı Sanatçılar ({len(artists)}):")
                for a in artists:
                    lyrics_count = len(list((DEFAULT_LYRICS_DIR / a["name"]).glob("*.txt"))) if (DEFAULT_LYRICS_DIR / a["name"]).exists() else 0
                    print(f"  • ID: {a['id']:<10} | İsim: {a['name']:<25} | İndirilen Şarkı: {lyrics_count}")

        elif choice == "2":
            query = input("Aramak istediğiniz sanatçı adı: ").strip()
            if not query:
                continue
            print(f"Genius üzerinde '{query}' aranıyor...")
            try:
                hits = search_genius_artists(query, max_results=5)
                if not hits:
                    print("Hiçbir sonuç bulunamadı.")
                    continue
                print("\nBulunan Sanatçılar:")
                for idx, hit in enumerate(hits, 1):
                    print(f"  [{idx}] {hit['name']} (Genius ID: {hit['id']})")
                sel = input("\nEklemek istediğiniz sıra numarasını girin (İptal için 0): ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(hits):
                    chosen = hits[int(sel) - 1]
                    res = add_artist(chosen["name"], artist_id=chosen["id"])
                    print(f"'{res['name']}' (ID: {res['id']}) başarıyla eklendi.")
                else:
                    print("İşlem iptal edildi.")
            except Exception as e:
                print(f"Hata: {e}")

        elif choice == "3":
            artists = load_artists()
            if not artists:
                print("Listede hiç sanatçı yok! Önce sanatçı ekleyin.")
                continue
            max_s = input("Sanatçı başına çekilecek en fazla şarkı sayısı (varsayılan 10): ").strip()
            max_songs = int(max_s) if max_s.isdigit() else 10
            fetch_all_artists_songs(max_songs_per_artist=max_songs)

        elif choice == "4":
            artists = load_artists()
            if not artists:
                print("Listede hiç sanatçı yok!")
                continue
            print("\nSanatçılar:")
            for idx, a in enumerate(artists, 1):
                print(f"  [{idx}] {a['name']} (ID: {a['id']})")
            sel = input("Hangi sanatçı? (Numara girin): ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(artists):
                chosen = artists[int(sel) - 1]
                max_s = input("Çekilecek en fazla şarkı sayısı (varsayılan 10): ").strip()
                max_songs = int(max_s) if max_s.isdigit() else 10
                fetch_songs_for_artist(artist_id=chosen["id"], artist_name=chosen["name"], max_songs=max_songs)
            else:
                print("Geçersiz seçim.")

        elif choice == "5":
            target = input("Silmek istediğiniz sanatçı adı veya ID: ").strip()
            if not target:
                continue
            ident = int(target) if target.isdigit() else target
            if remove_artist(ident):
                print(f"'{target}' başarıyla silindi.")
            else:
                print(f"'{target}' listede bulunamadı.")

        elif choice == "0":
            print("Çıkılıyor. İyi çalışmalar!")
            break
        else:
            print("Geçersiz seçim, lütfen tekrar deneyin.")


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="rhymek",
        description="Rhymek: Genius API ile sanatçı ID yönetimi ve şarkı sözü çekme aracı",
    )
    subparsers = parser.add_subparsers(dest="command", help="Alt komutlar")

    # add
    parser_add = subparsers.add_parser("add", help="Genius'tan sanatçı arayıp listeye ekle")
    parser_add.add_argument("name", help="Sanatçı adı")
    parser_add.add_argument("--id", type=int, default=None, help="Genius Sanatçı ID (opsiyonel)")

    # list
    subparsers.add_parser("list", help="Kayıtlı sanatçıları listele")

    # remove
    parser_rm = subparsers.add_parser("remove", help="Sanatçıyı listeden sil")
    parser_rm.add_argument("identifier", help="Sanatçı ID veya adı")

    # fetch
    parser_fetch = subparsers.add_parser("fetch", help="Şarkı sözlerini çek")
    parser_fetch.add_argument("--artist", help="Sadece belirli bir sanatçı adı veya ID")
    parser_fetch.add_argument("--all", action="store_true", help="Listedeki tüm sanatçıları çek")
    parser_fetch.add_argument("--max-songs", type=int, default=10, help="Sanatçı başına maksimum şarkı sayısı")
    parser_fetch.add_argument("--sort", choices=["popularity", "title"], default="popularity", help="Sıralama ölçütü")

    args = parser.parse_args(argv)

    if not args.command:
        # Eğer parametresiz çalıştırıldıysa interaktif menüyü aç
        interactive_menu()
        return

    if args.command == "list":
        artists = load_artists()
        if not artists:
            print(f"Kayıtlı sanatçı bulunamadı ({DEFAULT_ARTISTS_FILE}).")
            return
        print(f"\nKayıtlı Sanatçılar ({len(artists)}):")
        for a in artists:
            folder = DEFAULT_LYRICS_DIR / a["name"]
            count = len(list(folder.glob("*.txt"))) if folder.exists() else 0
            print(f"  • ID: {a['id']:<10} | İsim: {a['name']:<25} | İndirilen: {count} şarkı")

    elif args.command == "add":
        try:
            res = add_artist(args.name, artist_id=args.id)
            print(f"Başarıyla eklendi: {res['name']} (ID: {res['id']}) -> {DEFAULT_ARTISTS_FILE}")
        except Exception as e:
            print(f"Ekleme başarısız: {e}")
            sys.exit(1)

    elif args.command == "remove":
        ident = int(args.identifier) if args.identifier.isdigit() else args.identifier
        if remove_artist(ident):
            print(f"Silindi: {args.identifier}")
        else:
            print(f"Bulunamadı: {args.identifier}")

    elif args.command == "fetch":
        if args.artist:
            # Tek sanatçı için çek
            artists = load_artists()
            found = None
            for a in artists:
                if str(a["id"]) == args.artist or a["name"].lower() == args.artist.lower():
                    found = a
                    break
            if found:
                fetch_songs_for_artist(
                    artist_id=found["id"],
                    artist_name=found["name"],
                    max_songs=args.max_songs,
                    sort=args.sort,
                )
            else:
                # Listede yoksa doğrudan ID veya arama olarak dene
                if args.artist.isdigit():
                    fetch_songs_for_artist(
                        artist_id=int(args.artist),
                        max_songs=args.max_songs,
                        sort=args.sort,
                    )
                else:
                    print(f"'{args.artist}' listede bulunamadı. Önce 'rhymek add \"{args.artist}\"' ile ekleyin.")
        else:
            # Tüm sanatçılar için çek
            fetch_all_artists_songs(
                max_songs_per_artist=args.max_songs,
                sort=args.sort,
            )


if __name__ == "__main__":
    main()
