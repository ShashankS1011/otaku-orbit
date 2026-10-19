import pytest
import requests

import app


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
