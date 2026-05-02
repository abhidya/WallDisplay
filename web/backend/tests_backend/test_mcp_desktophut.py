from pathlib import Path

from web.backend.models.video import VideoModel
from web.backend.services.desktophut_service import DesktopHutService, index_video_directory, sanitize_filename


class FakeResponse:
    def __init__(self, text="", content=b""):
        self.text = text
        self.content = content

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1024):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None, stream=False):
        self.calls.append({"url": url, "params": params, "timeout": timeout, "stream": stream})
        if stream:
            return FakeResponse(content=b"fake mp4")
        return FakeResponse(text="""
        <div class="wallpaper-card" data-id="fish-1" data-preview="/videos/fish-1.mp4">
          <img alt="Blue fish reef live wallpaper" />
          <p class="card-title">Blue Fish Reef</p>
        </div>
        <div class="wallpaper-card" data-id="girl-1" data-preview="/videos/girl-1.mp4">
          <img alt="Girl portrait" />
          <p class="card-title">Girl Portrait</p>
        </div>
        <div class="wallpaper-card" data-id="space-1" data-preview="/videos/space-1.mp4">
          <img alt="Space tunnel" />
          <p class="card-title">Space Tunnel</p>
        </div>
        """)


def test_desktophut_search_filters_query_and_exclude_tag():
    service = DesktopHutService(session=FakeSession())

    results = service.search_videos("fish", limit=10)

    assert [item["id"] for item in results] == ["fish-1"]
    assert results[0]["preview_url"] == "https://www.desktophut.com/videos/fish-1.mp4"


def test_desktophut_download_search_is_bounded(tmp_path):
    service = DesktopHutService(session=FakeSession())

    result = service.download_search("fish", output_root=str(tmp_path), max_videos=1)

    assert result["downloaded_count"] == 1
    assert result["error_count"] == 0
    downloaded = Path(result["downloaded"][0]["file_path"])
    assert downloaded.exists()
    assert downloaded.read_bytes() == b"fake mp4"
    assert downloaded.name == "Blue_Fish_Reef.mp4"


def test_index_video_directory_adds_category(test_db, tmp_path):
    media_dir = tmp_path / "fish"
    media_dir.mkdir()
    video_path = media_dir / "reef.mp4"
    video_path.write_bytes(b"fake mp4")

    result = index_video_directory(test_db, str(media_dir), "fish")

    assert result["success"] is True
    assert result["indexed_count"] == 1
    stored = test_db.query(VideoModel).filter(VideoModel.path == str(video_path)).first()
    assert stored is not None
    assert stored.category == "fish"


def test_sanitize_filename_keeps_safe_name():
    assert sanitize_filename(" Blue Fish: Reef?! ") == "Blue_Fish_Reef"
