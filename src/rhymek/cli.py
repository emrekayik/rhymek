from typing import Optional

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from rhymek.artists import (
    add_artist,
    load_artists,
    remove_artist,
    search_genius_artists,
)
from rhymek.songs import (
    fetch_all_artists_songs,
    fetch_songs_for_artist,
    get_downloaded_songs_for_artist,
)
from rhymek.tui import launch_tui

app = typer.Typer(
    name="rhymek",
    help="🎵 Rhymek: Türkçe Şarkılar için NLP, Sanatçı ve Şarkı Sözü Toplama Aracı",
    rich_markup_mode="rich",
)
console = Console()

nlp_app = typer.Typer(
    name="nlp",
    help="🧠 Doğal dil işleme altyapısı komutları.",
    no_args_is_help=True,
)
app.add_typer(nlp_app, name="nlp")


def print_artists_table() -> None:
    """Kayıtlı sanatçıları Rich tablosu olarak yazdırır."""
    artists = load_artists()
    if not artists:
        console.print(
            Panel(
                "[yellow]Henüz kayıtlı sanatçı bulunmuyor.[/yellow]\n"
                "[cyan]rhymek add <sanatçı>[/] komutuyla veya interaktif menüden ekleyebilirsiniz.",
                title="[bold]Sanatçı Listesi[/bold]",
                border_style="yellow",
            )
        )
        return

    table = Table(
        title="🎤 [bold cyan]Kayıtlı Sanatçılar ve Şarkı İstatistikleri[/bold cyan]",
        header_style="bold magenta",
        border_style="cyan",
        show_lines=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Genius ID", style="bold green", width=12)
    table.add_column("Sanatçı Adı", style="bold white", min_width=20)
    table.add_column("JSONL Kayıtlı Şarkı", justify="center", style="bold yellow", width=22)

    total_songs = 0
    for idx, a in enumerate(artists, 1):
        name = a.get("name", "")
        a_id = str(a.get("id", ""))
        downloaded = len(get_downloaded_songs_for_artist(name))
        total_songs += downloaded
        count_display = f"{downloaded} adet" if downloaded > 0 else "[dim]Henüz yok[/dim]"
        table.add_row(str(idx), a_id, name, count_display)

    table.caption = f"[dim]Toplam [bold cyan]{total_songs}[/bold cyan] şarkı [blue]data/songs.jsonl[/blue] dosyasında kayıtlı.[/dim]"
    console.print(table)


def interactive_menu() -> None:
    """Questionary tabanlı interaktif ok tuşlu menü."""
    console.print(
        Panel.fit(
            "[bold orange3]🎵 RHYMEK - Türkçe Şarkı ve Şarkı Sözü Yöneticisi[/bold orange3]\n"
            "[dim]Ok tuşları ile gezinin, Enter ile seçin[/dim]",
            border_style="orange3",
        )
    )

    while True:
        choice = questionary.select(
            "Ne yapmak istiyorsunuz?",
            choices=[
                "🖥️  Tam Ekran TUI Dashboard'u Başlat (Textual)",
                "📋 Kayıtlı Sanatçıları Listele",
                "🔍 Yeni Sanatçı Ara ve Ekle",
                "⬇️  Şarkı Sözlerini İndir",
                "🗑️  Sanatçı Sil",
                "🚪 Çıkış",
            ],
            style=questionary.Style(
                [
                    ("qmark", "fg:#f97316 bold"),
                    ("question", "bold"),
                    ("pointer", "fg:#f97316 bold"),
                    ("highlighted", "fg:#f97316 bold"),
                    ("selected", "fg:#10b981"),
                ]
            ),
        ).ask()

        if not choice or "Çıkış" in choice:
            console.print("[dim]İyi çalışmalar![/dim]")
            break

        elif "Dashboard" in choice:
            launch_tui()

        elif "Listele" in choice:
            print_artists_table()

        elif "Yeni Sanatçı" in choice:
            query = questionary.text("Aramak istediğiniz sanatçı adı:").ask()
            if not query or not query.strip():
                continue

            with console.status(f"[bold cyan]Genius'ta '{query}' aranıyor...[/]"):
                hits = search_genius_artists(query.strip(), max_results=5)

            if not hits:
                console.print(f"[red]❌ '{query}' için sonuç bulunamadı.[/]")
                continue

            choices = [
                f"{h['name']} (ID: {h['id']})"
                for h in hits
            ] + ["[İptal]"]

            sel = questionary.select("Hangisini eklemek istiyorsunuz?", choices=choices).ask()
            if sel and sel != "[İptal]":
                selected_hit = hits[choices.index(sel)]
                res = add_artist(selected_hit["name"], artist_id=selected_hit["id"])
                console.print(f"[bold green]✓ Başarıyla eklendi:[/] {res['name']} (ID: {res['id']})")

        elif "İndir" in choice:
            artists = load_artists()
            if not artists:
                console.print("[yellow]Listede sanatçı yok! Önce sanatçı ekleyin.[/]")
                continue

            mode = questionary.select(
                "İndirme kapsamı:",
                choices=[
                    "Seçtiğim sanatçıların şarkılarını çek",
                    "Listedeki TÜM sanatçıların şarkılarını çek",
                    "[Geri Dön]",
                ],
            ).ask()

            if not mode or mode == "[Geri Dön]":
                continue

            limit_str = questionary.text(
                "Sanatçı başına maksimum kaç şarkı indirilsin?", default="10"
            ).ask()
            limit = int(limit_str) if limit_str and limit_str.isdigit() else 10

            if mode.startswith("Seçtiğim"):
                artist_choices = [
                    questionary.Choice(f"{a['name']} (ID: {a['id']})", value=a)
                    for a in artists
                ]
                selected_artists = questionary.checkbox(
                    "Şarkıları çekilecek sanatçıları seçin (Boşluk tuşu ile işaretleyin):",
                    choices=artist_choices,
                ).ask()

                if selected_artists:
                    for a in selected_artists:
                        fetch_songs_for_artist(
                            artist_id=a["id"],
                            artist_name=a["name"],
                            max_songs=limit,
                        )
            else:
                fetch_all_artists_songs(max_songs_per_artist=limit)

        elif "Sil" in choice:
            artists = load_artists()
            if not artists:
                console.print("[yellow]Silinecek sanatçı yok.[/]")
                continue

            del_choices = [f"{a['name']} (ID: {a['id']})" for a in artists] + ["[İptal]"]
            sel = questionary.select("Hangi sanatçıyı silmek istiyorsunuz?", choices=del_choices).ask()
            if sel and sel != "[İptal]":
                target_artist = artists[del_choices.index(sel)]
                remove_artist(target_artist["id"])
                console.print(f"[red]🗑️ '{target_artist['name']}' listeden silindi.[/]")


@app.command("tui", help="Tam ekran Textual TUI dashboard'unu başlatır.")
def cmd_tui():
    launch_tui()


@app.command("list", help="Kayıtlı sanatçıları ve indirilen şarkı istatistiklerini listeler.")
def cmd_list():
    print_artists_table()


@nlp_app.command("stats", help="Korpus/şarkı istatistiklerini gösterir.")
def cmd_nlp_stats(
    artist: Optional[str] = typer.Option(
        None, "--artist", "-a", help="Sanatçı adına göre filtrele"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="En fazla kaç şarkı işlensin"
    ),
    top: int = typer.Option(
        10, "--top", "-t", help="En sık kaç token gösterilsin"
    ),
    as_json: bool = typer.Option(False, "--json", help="JSON çıktı ver"),
):
    """Korpus yükleme + istatistik pipeline'ı için örnek CLI girişi."""
    from rhymek.nlp import load_corpus, summarize_corpus

    documents = load_corpus(artist=artist, limit=limit)
    if not documents:
        console.print("[yellow]⚠️ Kriterlere uyan şarkı bulunamadı.[/]")
        raise typer.Exit(code=1)

    summary = summarize_corpus(documents, top_n=top)

    if as_json:
        console.print_json(data=summary)
        return

    table = Table(
        title="🧠 [bold cyan]NLP Korpus İstatistikleri[/bold cyan]",
        header_style="bold magenta",
        border_style="cyan",
        show_header=False,
    )
    table.add_column("Metrik", style="bold white")
    table.add_column("Değer", justify="right", style="bold yellow")

    labels = [
        ("songs", "Şarkı"),
        ("stanzas", "Kıta"),
        ("lines", "Satır"),
        ("section_headers", "Bölüm başlığı"),
        ("tokens", "Token"),
        ("unique_tokens", "Benzersiz token"),
        ("type_token_ratio", "Type/token oranı"),
    ]
    for key, label in labels:
        table.add_row(label, str(summary[key]))
    console.print(table)

    if summary["top_tokens"]:
        top_table = Table(
            title=f"🔝 [bold cyan]En Sık {top} Token[/bold cyan]",
            header_style="bold magenta",
            border_style="cyan",
        )
        top_table.add_column("#", style="dim", width=4)
        top_table.add_column("Token", style="bold white")
        top_table.add_column("Frekans", justify="right", style="bold yellow")
        for rank, item in enumerate(summary["top_tokens"], 1):
            top_table.add_row(str(rank), item["token"], str(item["count"]))
        console.print(top_table)


@app.command("add", help="Genius üzerinden sanatçı arayıp data/artists.json dosyasına ekler.")
def cmd_add(
    name: str = typer.Argument(..., help="Sanatçı adı"),
    artist_id: Optional[int] = typer.Option(None, "--id", "-i", help="Doğrudan bilinen Genius Sanatçı ID"),
):
    with console.status(f"[bold cyan]Genius'ta '{name}' aranıyor...[/]"):
        try:
            res = add_artist(name, artist_id=artist_id)
            console.print(f"[bold green]✓ Başarıyla eklendi:[/] [bold]{res['name']}[/] (ID: {res['id']})")
        except Exception as e:
            console.print(f"[red]❌ Hata:[/] {e}")
            raise typer.Exit(code=1)


@app.command("remove", help="Sanatçıyı kayıtlı listeden siler.")
def cmd_remove(
    identifier: str = typer.Argument(..., help="Sanatçı adı veya ID"),
):
    ident = int(identifier) if identifier.isdigit() else identifier
    if remove_artist(ident):
        console.print(f"[green]✓ Silindi:[/] {identifier}")
    else:
        console.print(f"[yellow]⚠️ Bulunamadı:[/] {identifier}")


@app.command("fetch", help="Genius API üzerinden şarkı sözlerini çeker ve kaydeder.")
def cmd_fetch(
    artist: Optional[str] = typer.Option(None, "--artist", "-a", help="Belirli bir sanatçı adı veya ID"),
    all_artists: bool = typer.Option(False, "--all", help="Listedeki tüm sanatçıları çeker"),
    max_songs: int = typer.Option(10, "--max-songs", "-m", help="Sanatçı başına maksimum şarkı sayısı"),
    sort: str = typer.Option("popularity", "--sort", "-s", help="Sıralama ölçütü (popularity veya title)"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Daha önce çekilen sanatçıları atlama; yeniden tara ve başarısız şarkıları tekrar dene.",
    ),
):
    if artist:
        artists = load_artists()
        found = None
        for a in artists:
            if str(a["id"]) == artist or a["name"].lower() == artist.lower():
                found = a
                break

        if found:
            fetch_songs_for_artist(
                artist_id=found["id"],
                artist_name=found["name"],
                max_songs=max_songs,
                sort=sort,
                force=force,
            )
        elif artist.isdigit():
            fetch_songs_for_artist(
                artist_id=int(artist),
                max_songs=max_songs,
                sort=sort,
                force=force,
            )
        else:
            console.print(f"[red]❌ '{artist}' listede bulunamadı.[/] Önce 'rhymek add \"{artist}\"' ile ekleyin.")
            raise typer.Exit(code=1)
    else:
        # Default to all artists
        fetch_all_artists_songs(
            max_songs_per_artist=max_songs,
            sort=sort,
            force=force,
        )


@app.callback(invoke_without_command=True)
def default_callback(ctx: typer.Context):
    """
    Parametre verilmediğinde interaktif menüyü açar.
    """
    if ctx.invoked_subcommand is None:
        interactive_menu()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
