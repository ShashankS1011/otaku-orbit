import sqlite3

import pytest

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
