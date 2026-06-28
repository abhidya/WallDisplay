from pathlib import Path

from web.backend.models.media_source import MediaSourceEntry
from web.backend.models.video import VideoModel
from web.backend.services.desktophut_service import DesktopHutService, index_video_directory, sanitize_filename


class FakeResponse:
    def __init__(self, text="", content=b"", status_code=200, headers=None):
        self.text = text
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
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


class CachedSourceSession:
    def __init__(self, page_status=200, robots_text="User-agent: *\nAllow: /\n", sitemap_index=False):
        self.calls = []
        self.page_status = page_status
        self.robots_text = robots_text
        self.sitemap_index = sitemap_index

    def get(self, url, params=None, timeout=None, stream=False, headers=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout, "stream": stream, "headers": headers or {}})
        if url.endswith("/robots.txt"):
            return FakeResponse(text=self.robots_text)
        if url.endswith("/sitemap.xml"):
            if headers and headers.get("If-None-Match") == '"sitemap-v1"':
                return FakeResponse(status_code=304, headers={"ETag": '"sitemap-v1"'})
            if self.sitemap_index:
                return FakeResponse(text="""
                <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <sitemap><loc>https://www.desktophut.com/post-sitemap.xml</loc></sitemap>
                </sitemapindex>
                """, headers={"ETag": '"sitemap-v1"'})
            return FakeResponse(text="""
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://www.desktophut.com/fish-live-wallpaper</loc></url>
              <url><loc>https://www.desktophut.com/fish-live-wallpaper</loc></url>
            </urlset>
            """, headers={"ETag": '"sitemap-v1"', "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"})
        if url.endswith("/post-sitemap.xml"):
            return FakeResponse(text="""
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://www.desktophut.com/fish-live-wallpaper</loc></url>
            </urlset>
            """)
        if stream:
            return FakeResponse(content=b"fake mp4")
        return FakeResponse(text="""
        <html>
          <head>
            <meta property="og:title" content="Blue Fish Reef Live Wallpaper" />
            <meta property="og:image" content="/thumbs/fish.jpg" />
            <meta property="og:video" content="/videos/fish.mp4" />
            <meta property="article:tag" content="fish" />
          </head>
          <body><h1>Fallback Title</h1></body>
        </html>
        """, status_code=self.page_status, headers={"ETag": '"page-v1"'})


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


def test_desktophut_robots_disallow_blocks_refresh(test_db):
    session = CachedSourceSession(robots_text="User-agent: *\nDisallow: /sitemap.xml\n")
    service = DesktopHutService(test_db, session=session, request_delay_seconds=0)

    result = service.refresh_cache()

    assert result["success"] is False
    assert "robots.txt" in result["error"]
    assert test_db.query(MediaSourceEntry).count() == 0


def test_desktophut_sitemap_metadata_cached_and_deduped(test_db):
    session = CachedSourceSession()
    service = DesktopHutService(test_db, session=session, request_delay_seconds=0)

    result = service.refresh_cache(max_pages=10)

    assert result["success"] is True
    assert result["items_seen"] == 1
    entry = test_db.query(MediaSourceEntry).one()
    assert entry.title == "Blue Fish Reef Live Wallpaper"
    assert entry.thumbnail_url == "https://www.desktophut.com/thumbs/fish.jpg"
    assert entry.media_url == "https://www.desktophut.com/videos/fish.mp4"


def test_desktophut_sitemap_index_expands_nested_sitemap(test_db):
    session = CachedSourceSession(sitemap_index=True)
    service = DesktopHutService(test_db, session=session, request_delay_seconds=0)

    result = service.refresh_cache(max_pages=10)

    assert result["success"] is True
    assert test_db.query(MediaSourceEntry).count() == 1
    assert any(call["url"].endswith("/post-sitemap.xml") for call in session.calls)


def test_desktophut_cache_hit_avoids_page_network(test_db):
    session = CachedSourceSession()
    service = DesktopHutService(test_db, session=session, request_delay_seconds=0)

    service.refresh_cache(max_pages=1)
    calls_after_first = len(session.calls)
    service.refresh_cache(max_pages=1, force=False)

    assert len(session.calls) == calls_after_first + 1  # conditional sitemap only; robots is cached
    assert session.calls[-1]["headers"]["If-None-Match"] == '"sitemap-v1"'


def test_desktophut_force_refresh_uses_conditional_page_request(test_db):
    session = CachedSourceSession()
    service = DesktopHutService(test_db, session=session, request_delay_seconds=0)

    service.refresh_cache(max_pages=1)
    service.refresh_cache(max_pages=1, force=True)

    page_calls = [call for call in session.calls if call["url"].endswith("/fish-live-wallpaper")]
    assert page_calls[-1]["headers"]["If-None-Match"] == '"page-v1"'


def test_desktophut_backoff_on_429(test_db):
    service = DesktopHutService(test_db, session=CachedSourceSession(page_status=429), request_delay_seconds=0)

    result = service.refresh_cache(max_pages=1)

    assert result["source"]["backoff_until"] is not None


def test_desktophut_failed_fetch_does_not_retry_immediately(test_db):
    session = CachedSourceSession(page_status=500)
    service = DesktopHutService(test_db, session=session, request_delay_seconds=0)

    service.refresh_cache(max_pages=1)
    page_calls_after_failure = len([call for call in session.calls if call["url"].endswith("/fish-live-wallpaper")])
    service.refresh_cache(max_pages=1)

    failed = test_db.query(MediaSourceEntry).one()
    assert failed.cache_status == "failed"
    assert failed.next_retry_at is not None
    page_calls_after_retry = len([call for call in session.calls if call["url"].endswith("/fish-live-wallpaper")])
    assert page_calls_after_retry == page_calls_after_failure


def test_desktophut_api_smoke(test_client):
    status = test_client.get("/api/media-sources/desktophut/status")
    entries = test_client.get("/api/media-sources/desktophut/entries")

    assert status.status_code == 200
    assert entries.status_code == 200
    assert entries.json()["entries"] == []


def test_desktophut_import_uses_video_library_path(test_db, tmp_path):
    entry = MediaSourceEntry(
        provider="desktophut",
        canonical_url="https://www.desktophut.com/fish",
        page_url="https://www.desktophut.com/fish",
        title="Blue Fish Reef",
        thumbnail_url="https://www.desktophut.com/thumb.jpg",
        media_url="https://www.desktophut.com/videos/fish.mp4",
        cache_key="fish",
        cache_status="fresh",
    )
    test_db.add(entry)
    test_db.commit()
    test_db.refresh(entry)

    result = DesktopHutService(test_db, session=CachedSourceSession(), request_delay_seconds=0).import_entry(entry.id, upload_dir=str(tmp_path))

    assert result["success"] is True
    stored = test_db.query(VideoModel).filter(VideoModel.source_type == "desktophut").one()
    assert Path(stored.path).exists()
    assert Path(stored.path).read_bytes() == b"fake mp4"
    assert entry.import_status == "imported"
