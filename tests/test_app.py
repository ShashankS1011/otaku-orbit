import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests

import app


def test_app_version_uses_semantic_versioning():
    parts = app.APP_VERSION.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_support_link_points_to_discord_thread():
    assert app.SUPPORT_LINK == "https://discord.com/channels/@me/1252520070043668561/1562171196617785464"


def test_live_app_link_points_to_streamlit_deployment():
    assert app.APP_URL == "https://otaku-orbit.streamlit.app/"


def test_external_links_are_https_urls():
    for link in (app.APP_URL, app.SUPPORT_LINK):
        parsed = urlparse(link)
        assert parsed.scheme == "https"
        assert parsed.netloc


def test_streamlit_version_is_pinned_for_older_mobile_browsers():
    requirements = Path(__file__).parents[1].joinpath("requirements.txt").read_text()
    assert "streamlit>=1.49,<1.50" in requirements


def test_mobile_css_breakpoint_is_present_in_app_source():
    source = Path(app.__file__).read_text()
    assert "@media (max-width: 768px)" in source


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr(app, "DB_PATH", database)
    app.init_db()
    return database


def test_display_title_prefers_english_then_romaji():
    assert app.display_title({"title": {"english": "English", "romaji": "Romaji"}}) == "English"
    assert app.display_title({"title": {"romaji": "Romaji"}}) == "Romaji"
    assert app.display_title({"title": {}}) == "Untitled"


def test_clean_description_normalizes_markup_and_whitespace():
    assert app.clean_description(" A<br>  story\nabout heroes. ") == "A story about heroes."
    assert app.clean_description(None) == "No synopsis available."


def test_display_title_handles_missing_title_object():
    assert app.display_title({}) == "Untitled"


def test_format_airing_handles_missing_episode_data():
    assert app.format_airing({}) == "No upcoming episode"
    assert app.format_airing({"nextAiringEpisode": {"episode": 4}}) == "No upcoming episode"
    assert app.format_airing({"nextAiringEpisode": {"airingAt": "bad", "episode": 4}}) == "No upcoming episode"


def test_format_row_airing_handles_missing_airing_timestamp():
    assert app.format_row_airing({"title": "No airing"}) is None
    assert app.format_row_airing({"next_airing_at": "bad", "next_airing_episode": 4}) is None


def test_watchlist_round_trip(isolated_db):
    anime = {
        "id": 123,
        "title": {"english": "Test Anime"},
        "coverImage": {"large": "https://example.com/cover.jpg"},
        "episodes": 12,
        "averageScore": 88,
        "genres": ["Action", "Drama"],
    }
    app.save_anime(anime)
    rows = app.db_rows()
    assert rows[0]["title"] == "Test Anime"
    assert rows[0]["episodes"] == 12
    assert rows[0]["genres"] == "Action, Drama"
    app.update_progress(123, 3, "WATCHING")
    assert app.db_rows()[0]["progress"] == 3
    app.remove_anime(123)
    assert app.db_rows() == []


def test_anilist_query_surfaces_graphql_errors(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"errors": [{"message": "bad query"}]}

    monkeypatch.setattr(app.requests, "post", lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError, match="bad query"):
        app.anilist_query("query { nope }")


def test_filter_anime_respects_genre_score_and_adult_flag():
    results = [
        {"id": 1, "genres": ["Action"], "format": "TV", "averageScore": 90, "isAdult": False},
        {"id": 2, "genres": ["Drama"], "format": "MOVIE", "averageScore": 70, "isAdult": False},
        {"id": 3, "genres": ["Action"], "format": "TV", "averageScore": 95, "isAdult": True},
    ]
    filtered = app.filter_anime(results, "Action", "TV", 80)
    assert [anime["id"] for anime in filtered] == [1]
    assert [anime["id"] for anime in app.filter_anime(results, "Action", "TV", 80, True)] == [1, 3]


def test_watchlist_backup_can_be_restored(isolated_db):
    original = [{"anime_id": 7, "title": "Backup Anime", "status": "WATCHING", "progress": 4,
                 "episodes": 12, "genres": "Action", "updated_at": "2026-01-01T00:00:00"}]
    restored = app.import_watchlist(app.export_watchlist(original))
    assert restored == 1
    assert app.db_rows()[0]["title"] == "Backup Anime"
    assert app.db_rows()[0]["progress"] == 4


def test_anilist_query_retries_transient_request_error(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"Page": {"media": [{"id": 1}]}}}

    def flaky_post(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise requests.RequestException("temporary failure")
        return Response()

    monkeypatch.setattr(app.requests, "post", flaky_post)
    monkeypatch.setattr(app.time, "sleep", lambda _: None)
    assert app.anilist_query("retry-test-query") == [{"id": 1}]
    assert len(calls) == 2


def test_fetch_anime_page_preserves_pagination_metadata(monkeypatch):
    monkeypatch.setattr(app, "anilist_response", lambda *args, **kwargs: {
        "Page": {"media": [{"id": 1}], "pageInfo": {"hasNextPage": True}}
    })
    results, has_next = app.fetch_anime_page("frieren", page=2)
    assert results == [{"id": 1}]
    assert has_next is True


def test_load_with_fallback_returns_previous_session_result(monkeypatch):
    app.st.session_state.clear()
    result, from_cache = app.load_with_fallback("trending", lambda: ["cached later"])
    assert result == ["cached later"]
    assert from_cache is False

    def unavailable():
        raise requests.RequestException("offline")

    result, from_cache = app.load_with_fallback("trending", unavailable)
    assert result == ["cached later"]
    assert from_cache is True


def test_import_watchlist_rejects_invalid_backup_entry(isolated_db):
    with pytest.raises(ValueError, match="invalid score"):
        app.import_watchlist('[{"anime_id": 7, "title": "Broken", "score": 101}]')


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ('{"anime_id": 7}', "must contain a list"),
        ('[{"anime_id": 0, "title": "Broken"}]', "invalid id"),
        ('[{"anime_id": 7, "title": "Broken", "progress": -1}]', "invalid id"),
        ('[{"anime_id": 7, "title": "Broken", "episodes": -1}]', "invalid episode count"),
    ],
)
def test_import_watchlist_rejects_malformed_payloads(isolated_db, payload, message):
    with pytest.raises(ValueError, match=message):
        app.import_watchlist(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("next_airing_at", "bad", "invalid airing timestamp"),
        ("next_airing_at", 0, "invalid airing timestamp"),
        ("next_airing_episode", "bad", "invalid airing episode"),
        ("next_airing_episode", 0, "invalid airing episode"),
    ],
)
def test_import_watchlist_rejects_invalid_airing_metadata(isolated_db, field, value, message):
    payload = [{"anime_id": 7, "title": "Broken", field: value}]
    with pytest.raises(ValueError, match=message):
        app.import_watchlist(json.dumps(payload))


def test_anilist_query_raises_on_http_error_without_retrying(monkeypatch):
    calls = []

    class Response:
        status_code = 400

        def raise_for_status(self):
            raise requests.HTTPError("bad request")

    def post(*args, **kwargs):
        calls.append(1)
        return Response()

    monkeypatch.setattr(app.requests, "post", post)
    with pytest.raises(requests.HTTPError, match="bad request"):
        app.anilist_query("bad-request")
    assert len(calls) == 1


def test_init_db_migrates_legacy_airing_columns(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    monkeypatch.setattr(app, "DB_PATH", database)
    with sqlite3.connect(database) as connection:
        connection.execute("""CREATE TABLE watchlist (
            anime_id INTEGER PRIMARY KEY, title TEXT NOT NULL, image TEXT,
            status TEXT NOT NULL, progress INTEGER NOT NULL, episodes INTEGER,
            score INTEGER, genres TEXT, updated_at TEXT NOT NULL
        )""")
    app.init_db()
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(watchlist)")}
    assert {"next_airing_at", "next_airing_episode"}.issubset(columns)


def test_fetch_anime_page_passes_is_adult_variable(monkeypatch):
    recorded = {}

    def fake_response(query, variables):
        recorded.update(variables)
        return {"Page": {"media": [], "pageInfo": {"hasNextPage": False}}}

    monkeypatch.setattr(app, "anilist_response", fake_response)
    app.fetch_anime_page("hero", is_adult=True)
    assert recorded.get("isAdult") is True

    app.fetch_anime_page("hero", is_adult=False)
    assert recorded.get("isAdult") is False


def test_current_season_and_year_mapping():
    from datetime import date
    assert app.current_season_and_year(date(2026, 1, 15)) == ("WINTER", 2026)
    assert app.current_season_and_year(date(2026, 4, 1)) == ("SPRING", 2026)
    assert app.current_season_and_year(date(2026, 7, 20)) == ("SUMMER", 2026)
    assert app.current_season_and_year(date(2026, 10, 5)) == ("FALL", 2026)
    assert app.current_season_and_year(date(2026, 12, 31)) == ("WINTER", 2026)


def test_format_trailer_url_youtube():
    assert app.format_trailer_url({"site": "youtube", "id": "abc123xyz"}) == "https://www.youtube.com/watch?v=abc123xyz"
    assert app.format_trailer_url({"site": "dailymotion", "id": "123"}) is None
    assert app.format_trailer_url(None) is None
    assert app.format_trailer_url({}) is None
