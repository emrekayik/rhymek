from typing import Any, Dict, List, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    RichLog,
)
from textual.widgets.option_list import Option

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
    load_songs_from_jsonl,
)


class RhymekApp(App):
    """rhymek TUI: Turkish Songs NLP & Lyrics Manager"""

    CSS = """
    Screen {
        background: $surface;
    }

    #sidebar {
        width: 38;
        background: $panel;
        border-right: heavy $primary;
        padding: 1;
    }

    #main_content {
        padding: 1;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #artist_list {
        height: 1fr;
        border: solid $primary-muted;
        margin-bottom: 1;
    }

    .sidebar-actions {
        height: auto;
        margin-top: 1;
    }

    #top_bar {
        height: auto;
        background: $panel;
        padding: 1;
        border-bottom: solid $accent;
        margin-bottom: 1;
    }

    #artist_header {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    .action-controls {
        height: auto;
        align: left middle;
    }

    .action-controls Label {
        margin-right: 1;
        padding-top: 1;
    }

    .action-controls Input {
        width: 10;
        margin-right: 1;
    }

    .action-controls Button {
        margin-right: 1;
    }

    #songs_table {
        height: 14;
        border: solid $secondary;
        margin-bottom: 1;
    }

    #status_log {
        height: 1fr;
        border: solid $accent-muted;
        background: $surface-darken-1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Çıkış", show=True),
        Binding("r", "refresh_all", "Yenile", show=True),
        Binding("f", "fetch_selected", "Şarkı Çek", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.artists: List[Dict[str, Any]] = []
        self.selected_artist: Optional[Dict[str, Any]] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            # Sol Panel (Sidebar): Sanatçılar ve Yönetim
            with Vertical(id="sidebar"):
                yield Label("🎤 Kayıtlı Sanatçılar", classes="panel-title")
                yield OptionList(id="artist_list")
                yield Input(placeholder="Sanatçı adı ara / ekle...", id="artist_input")
                with Horizontal(classes="sidebar-actions"):
                    yield Button("➕ Ekle", id="btn_add", variant="primary")
                    yield Button("🗑️ Sil", id="btn_delete", variant="error")

            # Sağ Panel (Main): Şarkı Listesi ve İndirme Kontrolleri
            with Vertical(id="main_content"):
                with Vertical(id="top_bar"):
                    yield Label("Lütfen bir sanatçı seçin", id="artist_header")
                    with Horizontal(classes="action-controls"):
                        yield Label("Şarkı Sayısı:")
                        yield Input(value="10", id="max_songs_input", max_length=3)
                        yield Button("⬇️ Şarkıları Çek", id="btn_fetch", variant="primary")
                        yield Button("🌐 Tümünü Çek", id="btn_fetch_all", variant="success")

                yield Label("🎵 JSONL Kayıtlı Şarkılar (data/songs.jsonl)", classes="panel-title")
                yield DataTable(id="songs_table")

                yield Label("📜 Canlı İşlem Günlüğü (Log)", classes="panel-title")
                yield RichLog(id="status_log", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#songs_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Şarkı Başlığı", "Albüm", "Tarih")

        log = self.query_one("#status_log", RichLog)
        log.write("[bold green]✓ rhymek TUI başlatıldı.[/] Genius API ve yerel veri hazır.")

        self.refresh_artists()

    def refresh_artists(self) -> None:
        """Sanatçı listesini dosyadan okur ve OptionList'e doldurur."""
        self.artists = load_artists()
        opt_list = self.query_one("#artist_list", OptionList)
        opt_list.clear_options()

        if not self.artists:
            self.selected_artist = None
            self.query_one("#artist_header", Label).update("Lütfen bir sanatçı seçin")
            self.query_one("#songs_table", DataTable).clear()
            opt_list.add_option(Option("Henüz sanatçı yok", id="none", disabled=True))
            return

        songs = load_songs_from_jsonl()
        for idx, artist in enumerate(self.artists):
            name = artist.get("name", "Bilinmeyen")
            a_id = artist.get("id", "?")
            # İndirilen şarkı sayısını hesapla
            count = len(get_downloaded_songs_for_artist(name, cached_songs=songs))
            badge = f"({count} şarkı)" if count > 0 else "(yok)"
            opt_list.add_option(Option(f"{name} {badge} [ID: {a_id}]", id=str(idx)))

        # İlk sanatçıyı seç
        if self.artists:
            opt_list.highlighted = 0
            self.select_artist(self.artists[0])

    def select_artist(self, artist: Dict[str, Any]) -> None:
        """Seçili sanatçıyı ayarlar ve şarkı tablosunu günceller."""
        self.selected_artist = artist
        header = self.query_one("#artist_header", Label)
        header.update(f"🎤 {artist['name']} [dim](Genius ID: {artist['id']})[/dim]")
        self.load_songs_table(artist["name"])

    def load_songs_table(self, artist_name: str) -> None:
        """Seçili sanatçının yerel diskteki şarkılarını tabloya yükler."""
        table = self.query_one("#songs_table", DataTable)
        table.clear()

        songs = get_downloaded_songs_for_artist(artist_name)
        if not songs:
            table.add_row("-", "Henüz indirilmiş şarkı yok", "-", "-")
            return

        for song in songs:
            table.add_row(
                str(song.get("id") or "-"),
                str(song.get("title") or "-"),
                str(song.get("album") or "-"),
                str(song.get("release_date") or song.get("year") or "-"),
            )

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_id and event.option_id.isdigit():
            idx = int(event.option_id)
            if 0 <= idx < len(self.artists):
                self.select_artist(self.artists[idx])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn_add":
            self.action_add_artist()
        elif btn_id == "btn_delete":
            self.action_delete_artist()
        elif btn_id == "btn_fetch":
            self.action_fetch_selected()
        elif btn_id == "btn_fetch_all":
            self.action_fetch_all()

    def action_refresh_all(self) -> None:
        self.refresh_artists()
        log = self.query_one("#status_log", RichLog)
        log.write("[dim]↻ Sanatçı listesi ve tablolar yenilendi.[/dim]")

    def action_delete_artist(self) -> None:
        if not self.selected_artist:
            return
        name = self.selected_artist["name"]
        a_id = self.selected_artist["id"]
        remove_artist(a_id)
        log = self.query_one("#status_log", RichLog)
        log.write(f"[red]🗑️ '{name}' listeden silindi.[/red]")
        self.refresh_artists()

    def action_add_artist(self) -> None:
        inp = self.query_one("#artist_input", Input)
        query = inp.value.strip()
        if not query:
            return
        inp.value = ""
        self.search_and_add_artist_worker(query)

    @work(thread=True)
    def search_and_add_artist_worker(self, query: str) -> None:
        """Genius API üzerinden arka planda sanatçı arar ve ekler."""
        log = self.query_one("#status_log", RichLog)
        log.write(f"[cyan]🔍 Genius'ta '{query}' aranıyor...[/cyan]")
        try:
            hits = search_genius_artists(query, max_results=1)
            if not hits:
                log.write(f"[yellow]⚠️ '{query}' için sonuç bulunamadı.[/yellow]")
                return
            best = hits[0]
            added = add_artist(best["name"], artist_id=best["id"])
            log.write(f"[bold green]✓ Eklendi:[/] {added['name']} (ID: {added['id']})")
            self.app.call_from_thread(self.refresh_artists)
        except Exception as e:
            log.write(f"[red]❌ Ekleme hatası:[/] {e}")

    def action_fetch_selected(self) -> None:
        if not self.selected_artist:
            return
        max_s_str = self.query_one("#max_songs_input", Input).value.strip()
        max_songs = int(max_s_str) if max_s_str.isdigit() else 10
        self.fetch_artist_worker(self.selected_artist, max_songs)

    @work(thread=True)
    def fetch_artist_worker(self, artist: Dict[str, Any], max_songs: int) -> None:
        """Arka planda sanatçının şarkılarını çeker."""
        log = self.query_one("#status_log", RichLog)
        log.write(f"[bold cyan]🚀 '{artist['name']}' için şarkılar çekilmeye başlanıyor (Limit: {max_songs})...[/bold cyan]")

        def logger_callback(msg: str) -> None:
            log.write(msg)

        try:
            fetch_songs_for_artist(
                artist_id=artist["id"],
                artist_name=artist["name"],
                max_songs=max_songs,
                progress_callback=logger_callback,
            )
            # Arayüzü güncelle
            self.app.call_from_thread(self.load_songs_table, artist["name"])
            self.app.call_from_thread(self.refresh_artists)
        except Exception as e:
            log.write(f"[red]❌ İndirme sırasında hata oluştu:[/] {e}")

    def action_fetch_all(self) -> None:
        max_s_str = self.query_one("#max_songs_input", Input).value.strip()
        max_songs = int(max_s_str) if max_s_str.isdigit() else 10
        self.fetch_all_worker(max_songs)

    @work(thread=True)
    def fetch_all_worker(self, max_songs: int) -> None:
        """Arka planda tüm sanatçıların şarkılarını çeker."""
        log = self.query_one("#status_log", RichLog)
        log.write(f"[bold magenta]🌐 Tüm sanatçılar için şarkılar indiriliyor (Her biri için max: {max_songs})...[/bold magenta]")

        def logger_callback(msg: str) -> None:
            log.write(msg)

        try:
            fetch_all_artists_songs(
                max_songs_per_artist=max_songs,
                progress_callback=logger_callback,
            )
            if self.selected_artist:
                self.app.call_from_thread(self.load_songs_table, self.selected_artist["name"])
            self.app.call_from_thread(self.refresh_artists)
        except Exception as e:
            log.write(f"[red]❌ Toplu indirme hatası:[/] {e}")


def launch_tui() -> None:
    app = RhymekApp()
    app.run()


if __name__ == "__main__":
    launch_tui()
