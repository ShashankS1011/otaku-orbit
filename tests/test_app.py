import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests
from streamlit.testing.v1 import AppTest

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
    assert "streamlit[auth]>=1.49,<1.50" in requirements


def test_mobile_css_breakpoint_is_present_in_app_source():
    source = Path(app.__file__).read_text(encoding="utf-8")
    assert "@media (max-width: 768px)" in source


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    database = tmp_path / "test.db"
    monkeypatch.setattr(app, "DB_PATH", database)
    app.init_db()
    return database


def test_database_path_isolated_per_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DB_PATH", tmp_path / "watchlist.db")
    alice_path = app.database_path_for_owner("alice")
    bob_path = app.database_path_for_owner("bob")
    assert alice_path != bob_path
    assert "alice" not in alice_path.name


def test_guest_identity_is_stable_for_one_session_and_rotates_between_sessions(monkeypatch):
    monkeypatch.setattr(app, "authentication_configured", lambda: False)
    app.st.session_state.clear()
    first_session = app.current_owner_id()
    assert app.current_owner_id() == first_session
    app.st.session_state.clear()
    assert app.current_owner_id() != first_session


def test_watchlists_are_isolated_between_owners(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DB_PATH", tmp_path / "watchlist.db")
    app.init_db("alice")
    app.init_db("bob")
    app.save_anime({"id": 1, "title": {"english": "Private title"}}, owner_id="alice")
    assert [row["title"] for row in app.db_rows("alice")] == ["Private title"]
    assert app.db_rows("bob") == []


def test_watchlist_empty_state_renders_in_streamlit_app_test(isolated_db):
    def render_empty_view():
        import app

        app.render_watchlist()

    app_test = AppTest.from_function(render_empty_view).run()
    assert any("watchlist is empty" in item.value.lower() for item in app_test.info)


def test_owner_data_deletion_removes_only_that_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DB_PATH", tmp_path / "watchlist.db")
    app.init_db("alice")
    app.init_db("bob")
    app.save_anime({"id": 1, "title": {"english": "Alice"}}, owner_id="alice")
    app.save_anime({"id": 2, "title": {"english": "Bob"}}, owner_id="bob")
    app.delete_owner_data("alice")
    app.init_db("alice")
    assert app.db_rows("alice") == []
    assert [row["title"] for row in app.db_rows("bob")] == ["Bob"]


def test_display_title_prefers_english_then_romaji():
    assert app.display_title({"title": {"english": "English", "romaji": "Romaji"}}) == "English"
    assert app.display_title({"title": {"romaji": "Romaji"}}) == "Romaji"
    assert app.display_title({"title": {}}) == "Untitled"


def test_clean_description_normalizes_markup_and_whitespace():
    assert app.clean_description(" A<br>  story\nabout heroes. ") == "A story about heroes."
    assert app.clean_description(None) == "No synopsis available."
    assert app.clean_description("<p>Safe</p><script>alert('x')</script><b>text</b>") == "Safe text"


def test_cover_image_prefers_largest_anilist_image():
    assert (
        app.cover_image_url({"coverImage": {"extraLarge": "https://s4.anilist.co/large.jpg", "large": "fallback"}})
        == "https://s4.anilist.co/large.jpg"
    )
    assert (
        app.cover_image_url({"coverImage": {"large": "https://s4.anilist.co/large.jpg"}})
        == "https://s4.anilist.co/large.jpg"
    )
    assert app.cover_image_url({}) is None


def test_anilist_queries_request_extra_large_covers():
    assert "coverImage { extraLarge large }" in app.SEARCH_QUERY
    assert "coverImage { extraLarge large }" in app.DETAIL_QUERY
    assert "coverImage { extraLarge large }" in app.TRENDING_QUERY


def test_cover_urls_are_limited_to_secure_anilist_hosts():
    assert app.is_safe_cover_url("https://s4.anilist.co/file.jpg")
    assert not app.is_safe_cover_url("http://s4.anilist.co/file.jpg")
    assert not app.is_safe_cover_url("https://example.com/file.jpg")


def test_csv_export_neutralizes_spreadsheet_formulas():
    assert app.csv_safe_cell("=cmd|A0") == "'=cmd|A0"
    assert app.csv_safe_cell("  @SUM(A1:A2)") == "'  @SUM(A1:A2)"
    assert app.csv_safe_cell("Safe title") == "Safe title"


def test_csv_export_escapes_user_supplied_formula_fields():
    data = app.export_watchlist_csv([{"anime_id": 1, "title": '=HYPERLINK("https://bad")', "notes": "@SUM(A1:A2)"}])
    assert "'=HYPERLINK" in data
    assert "'@SUM" in data


def test_validate_watchlist_state_rejects_invalid_progress_and_score():
    with pytest.raises(ValueError, match="Episode progress"):
        app.validate_watchlist_state(13, "WATCHING", 12)
    with pytest.raises(ValueError, match="valid watch status"):
        app.validate_watchlist_state(1, "UNKNOWN", 12)
    with pytest.raises(ValueError, match="between 0 and 100"):
        app.validate_watchlist_state(1, "WATCHING", 12, 101)


@pytest.mark.parametrize(
    ("episodes", "duration", "progress", "expected"),
    [
        (12, 24, 0, "12 eps · 4h 48m total"),
        (12, 24, 6, "2h 24m remaining"),
        (2, 30, 1, "30m remaining"),
        (2, None, 0, "2 eps · 48m total"),
        (2, 0, 0, "2 eps · 48m total"),
        (2, 30, 4, "0m remaining"),
        (None, 24, 0, "Estimated watch time unavailable"),
    ],
)
def test_calculate_runtime_display(episodes, duration, progress, expected):
    assert app.calculate_runtime_display(episodes, duration, progress) == expected


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
        "duration": 24,
        "averageScore": 88,
        "genres": ["Action", "Drama"],
    }
    app.save_anime(anime)
    rows = app.db_rows()
    assert rows[0]["title"] == "Test Anime"
    assert rows[0]["episodes"] == 12
    assert rows[0]["duration"] == 24
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

    class Session:
        def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(app, "_request_session", Session)
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
    original = [
        {
            "anime_id": 7,
            "title": "Backup Anime",
            "status": "WATCHING",
            "progress": 4,
            "episodes": 12,
            "duration": 24,
            "genres": "Action",
            "updated_at": "2026-01-01T00:00:00",
        }
    ]
    restored = app.import_watchlist(app.export_watchlist(original))
    assert restored == 1
    assert app.db_rows()[0]["title"] == "Backup Anime"
    assert app.db_rows()[0]["progress"] == 4
    assert app.db_rows()[0]["duration"] == 24


def test_watchlist_backup_has_version_and_accepts_legacy_list(isolated_db):
    current = json.loads(app.export_watchlist([]))
    assert current == {"format_version": app.BACKUP_FORMAT_VERSION, "items": []}
    assert app.import_watchlist('[{"anime_id": 88, "title": "Legacy"}]') == 1
    with pytest.raises(ValueError, match="Unsupported watchlist backup version"):
        app.import_watchlist('{"format_version": 99, "items": []}')


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

    class Session:
        def post(self, *args, **kwargs):
            return flaky_post(*args, **kwargs)

    monkeypatch.setattr(app, "_request_session", Session)
    monkeypatch.setattr(app.time, "sleep", lambda _: None)
    monkeypatch.setattr(app.random, "uniform", lambda low, high: 0)
    assert app.anilist_query("retry-test-query") == [{"id": 1}]
    assert len(calls) == 2


def test_fetch_anime_page_preserves_pagination_metadata(monkeypatch):
    monkeypatch.setattr(
        app,
        "anilist_response",
        lambda *args, **kwargs: {"Page": {"media": [{"id": 1}], "pageInfo": {"hasNextPage": True}}},
    )
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
    assert app.cache_age_label("trending") != "an unknown time"


def test_backup_import_rolls_back_if_a_later_row_is_invalid(isolated_db):
    payload = '[{"anime_id": 1, "title": "Valid"}, {"anime_id": 0, "title": "Invalid"}]'
    with pytest.raises(ValueError, match="invalid id"):
        app.import_watchlist(payload)
    assert app.db_rows() == []


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

    class Session:
        def post(self, *args, **kwargs):
            return post(*args, **kwargs)

    monkeypatch.setattr(app, "_request_session", Session)
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
    assert {"next_airing_at", "next_airing_episode", "user_score", "notes", "duration"}.issubset(columns)


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
    assert app.current_season_and_year(date(2026, 12, 31)) == ("WINTER", 2027)


def test_airing_formatter_respects_explicit_timezone():
    airing = {"nextAiringEpisode": {"airingAt": 1, "episode": 1}}
    assert app.format_airing(airing, "UTC") == "Episode 1 · 01 Jan, 00:00"
    assert app.format_airing(airing, "Asia/Kolkata") == "Episode 1 · 01 Jan, 05:30"


def test_format_trailer_url_youtube():
    assert app.format_trailer_url({"site": "youtube", "id": "abc123xyz"}) == "https://www.youtube.com/watch?v=abc123xyz"
    assert app.format_trailer_url({"site": "dailymotion", "id": "123"}) is None
    assert app.format_trailer_url(None) is None
    assert app.format_trailer_url({}) is None


def test_recommendations_weight_completed_and_high_rated_genres():
    rows = [
        {"genres": "Action, Drama", "status": "COMPLETED", "user_score": 100},
        {"genres": "Comedy", "status": "DROPPED", "user_score": 20},
    ]
    candidates = [
        {"id": 1, "genres": ["Action"], "averageScore": 70},
        {"id": 2, "genres": ["Comedy"], "averageScore": 95},
        {"id": 3, "genres": ["Drama"], "averageScore": 75},
    ]
    ranked = app.rank_recommendations(rows, candidates, {3}, limit=2)
    assert [anime["id"] for anime in ranked] == [1, 2]


def test_update_progress_sets_user_score(isolated_db):
    app.save_anime({"id": 999, "title": {"english": "Score Test"}, "episodes": 12})
    app.update_progress(999, 5, "WATCHING", user_score=85)
    row = app.db_rows()[0]
    assert row["progress"] == 5
    assert row["user_score"] == 85


def test_update_progress_sets_notes(isolated_db):
    app.save_anime({"id": 888, "title": {"english": "Notes Test"}, "episodes": 24})
    app.update_progress(888, 10, "WATCHING", notes="Masterpiece so far")
    row = app.db_rows()[0]
    assert row["notes"] == "Masterpiece so far"


def test_increment_watchlist_progress_and_auto_completion(isolated_db):
    app.save_anime({"id": 777, "title": {"english": "Frieren"}, "episodes": 2}, status="PLANNING")
    prog, status = app.increment_watchlist_progress(777)
    assert prog == 1
    assert status == "WATCHING"

    prog2, status2 = app.increment_watchlist_progress(777)
    assert prog2 == 2
    assert status2 == "COMPLETED"


def test_export_watchlist_csv():
    rows = [
        {
            "anime_id": 101,
            "title": "Steins;Gate",
            "status": "COMPLETED",
            "progress": 24,
            "episodes": 24,
            "duration": 24,
            "score": 91,
            "user_score": 99,
            "genres": "Sci-Fi, Thriller",
            "notes": "El Psy Kongroo",
            "updated_at": "2026-10-27T12:00:00",
        }
    ]
    csv_text = app.export_watchlist_csv(rows)
    assert "Anime ID,Title,Status" in csv_text
    assert "101,Steins;Gate,COMPLETED,24,24,24,91,99" in csv_text
    assert "El Psy Kongroo" in csv_text


def test_rewatching_status_supported(isolated_db):
    assert "REWATCHING" in app.WATCH_STATUSES
    app.save_anime({"id": 201, "title": {"english": "Attack on Titan"}, "episodes": 25}, status="REWATCHING")
    rows = app.db_rows()
    assert rows[0]["status"] == "REWATCHING"


def test_rewatches_and_tags_saved_and_updated(isolated_db):
    app.save_anime(
        {"id": 202, "title": {"english": "Death Note"}, "episodes": 37},
        rewatches=1,
        tags="Mystery, Classic",
    )
    rows = app.db_rows()
    assert rows[0]["rewatches"] == 1
    assert "Classic" in rows[0]["tags"]

    app.update_progress(202, progress=15, status="WATCHING", rewatches=2, tags="Masterpiece, Mystery")
    updated = app.db_rows()
    assert updated[0]["rewatches"] == 2
    assert "Masterpiece" in updated[0]["tags"]


def test_negative_rewatches_raises_value_error():
    with pytest.raises(ValueError, match="Rewatch count cannot be negative"):
        app.validate_watchlist_state(0, "PLANNING", 12, rewatches=-1)


def test_batch_operations(isolated_db):
    app.save_anime({"id": 301, "title": {"english": "Show 1"}}, status="PLANNING")
    app.save_anime({"id": 302, "title": {"english": "Show 2"}}, status="PLANNING")

    app.batch_update_status([301, 302], "WATCHING")
    rows = {r["anime_id"]: r["status"] for r in app.db_rows()}
    assert rows[301] == "WATCHING"
    assert rows[302] == "WATCHING"

    app.batch_add_tag([301, 302], "Binge")
    rows_tags = {r["anime_id"]: r["tags"] for r in app.db_rows()}
    assert "Binge" in rows_tags[301]
    assert "Binge" in rows_tags[302]

    app.batch_remove_anime([301])
    remaining_ids = [r["anime_id"] for r in app.db_rows()]
    assert 301 not in remaining_ids
    assert 302 in remaining_ids


def test_export_watchlist_mal_xml():
    rows = [
        {
            "anime_id": 501,
            "title": "Fullmetal Alchemist: Brotherhood",
            "status": "COMPLETED",
            "progress": 64,
            "user_score": 98,
            "rewatches": 3,
            "notes": "Absolute masterpiece",
        }
    ]
    xml = app.export_watchlist_mal_xml(rows)
    assert "<myanimelist>" in xml
    assert "<series_animedb_id>501</series_animedb_id>" in xml
    assert "<series_title>Fullmetal Alchemist: Brotherhood</series_title>" in xml
    assert "<my_status>Completed</my_status>" in xml
    assert "<my_score>10</my_score>" in xml
    assert "<my_times_watched>3</my_times_watched>"
    assert "<my_comments>Absolute masterpiece</my_comments>" in xml


def test_banner_image_url_extraction():
    assert (
        app.banner_image_url({"bannerImage": "https://s4.anilist.co/banner.jpg"}) == "https://s4.anilist.co/banner.jpg"
    )
    assert app.banner_image_url({"bannerImage": "http://unsafe.com/banner.jpg"}) is None
    assert app.banner_image_url({}) is None


def test_fetch_airing_schedule(monkeypatch):
    recorded = {}

    def fake_response(query, variables):
        recorded.update(variables)
        return {"Page": {"airingSchedules": [{"id": 1, "episode": 5}]}}

    monkeypatch.setattr(app, "anilist_response", fake_response)
    results = app.fetch_airing_schedule(1000, 2000)
    assert recorded["airingAt_greater"] == 1000
    assert recorded["airingAt_lesser"] == 2000
    assert len(results) == 1
    assert results[0]["episode"] == 5


def test_theme_palettes_structure():
    assert "Saiyan Neon" in app.THEME_PALETTES
    assert "Cyberpunk Cyan" in app.THEME_PALETTES
    for palette in app.THEME_PALETTES.values():
        assert "primary" in palette
        assert "glow" in palette
        assert "sidebar" in palette


def test_backup_validation_supports_rewatches_and_tags():
    raw_row = {
        "anime_id": 999,
        "title": "Evangelion",
        "progress": 26,
        "rewatches": 4,
        "tags": "Mecha, Psychological",
        "banner_image": "https://s4.anilist.co/eva.jpg",
    }
    validated = app.validate_backup_row(raw_row, 1)
    assert validated["rewatches"] == 4
    assert validated["tags"] == "Mecha, Psychological"
    assert validated["banner_image"] == "https://s4.anilist.co/eva.jpg"


def test_extract_streaming_links():
    anime = {
        "externalLinks": [
            {"site": "Crunchyroll", "url": "https://crunchyroll.com/show", "type": "STREAMING"},
            {"site": "Netflix", "url": "https://netflix.com/title/123", "type": "STREAMING"},
            {"site": "Twitter", "url": "https://twitter.com/anime", "type": "INFO"},
        ],
        "streamingEpisodes": [
            {"site": "Crunchyroll", "url": "https://crunchyroll.com/ep1"},
            {"site": "VRV", "url": "https://vrv.co/ep1"},
        ],
    }
    links = app.extract_streaming_links(anime)
    urls = [link["url"] for link in links]
    assert "https://crunchyroll.com/show" in urls
    assert "https://netflix.com/title/123" in urls
    assert "https://vrv.co/ep1" in urls
    assert "https://twitter.com/anime" not in urls


def test_extract_characters_and_seiyuu():
    anime = {
        "characters": {
            "edges": [
                {
                    "role": "MAIN",
                    "node": {
                        "id": 1,
                        "name": {"full": "Frieren", "native": "フリーレン"},
                        "image": {"large": "https://s4.anilist.co/frieren.jpg"},
                    },
                    "voiceActors": [
                        {
                            "id": 10,
                            "name": {"full": "Atsumi Tanezaki", "native": "種﨑敦美"},
                            "image": {"large": "https://s4.anilist.co/atsumi.jpg"},
                        }
                    ],
                }
            ]
        }
    }
    cast = app.extract_characters_and_seiyuu(anime)
    assert len(cast) == 1
    assert cast[0]["character"] == "Frieren"
    assert cast[0]["role"] == "Main"
    assert cast[0]["seiyuu"] == "Atsumi Tanezaki"


def test_filter_anime_by_source_and_studio():
    items = [
        {
            "id": 1,
            "source": "MANGA",
            "studios": {"nodes": [{"name": "MAPPA"}]},
            "genres": ["Action"],
            "averageScore": 85,
        },
        {
            "id": 2,
            "source": "LIGHT_NOVEL",
            "studios": {"nodes": [{"name": "CloverWorks"}]},
            "genres": ["Drama"],
            "averageScore": 80,
        },
    ]
    assert len(app.filter_anime(items, source="MANGA")) == 1
    assert app.filter_anime(items, source="MANGA")[0]["id"] == 1
    assert len(app.filter_anime(items, studio="CloverWorks")) == 1
    assert app.filter_anime(items, studio="CloverWorks")[0]["id"] == 2
    assert len(app.filter_anime(items, studio="Bones")) == 0


def test_generate_music_links():
    links = app.generate_music_links("Chainsaw Man")
    assert links["Spotify OP"].startswith("https://open.spotify.com/")
    assert links["Spotify ED"].startswith("https://open.spotify.com/")
    assert links["YouTube Music"].startswith("https://music.youtube.com/")


def test_watch_history_and_streak(isolated_db):
    app.save_anime({"id": 10, "title": {"english": "Steins;Gate"}, "episodes": 24})
    now = app.datetime.now().isoformat()
    app.record_watch_history(10, "Steins;Gate", 1, watched_at=now)
    history = app.fetch_watch_history(days=10)
    assert len(history) >= 1
    assert history[0]["episode"] == 1
    streak = app.calculate_watch_streak(history)
    assert streak >= 1


def test_watch_velocity_and_completion_date():
    history = [
        {"watched_at": "2026-10-30T12:00:00", "episode": 1},
        {"watched_at": "2026-10-30T14:00:00", "episode": 2},
        {"watched_at": "2026-10-29T12:00:00", "episode": 3},
    ]
    velocity = app.calculate_watch_velocity(history)
    assert velocity > 0
    completion = app.estimate_completion_date(10, velocity)
    assert completion is not None


def test_evaluate_achievements():
    rows = [
        {
            "anime_id": 1,
            "status": "COMPLETED",
            "progress": 25,
            "user_score": 90,
            "genres": "Action, Sci-Fi",
            "tags": "Favorite",
        },
        {
            "anime_id": 2,
            "status": "WATCHING",
            "progress": 80,
            "user_score": 85,
            "genres": "Comedy, Romance, Mystery",
            "tags": "Cozy",
        },
    ]
    history = [{"watched_at": "2026-10-30T10:00:00"} for _ in range(6)]
    achievements = app.evaluate_achievements(rows, history)
    unlocked_ids = {a["id"] for a in achievements if a["unlocked"]}
    assert "first_step" in unlocked_ids
    assert "rookie" in unlocked_ids
    assert "centurion" in unlocked_ids
    assert "binge_demon" in unlocked_ids
    assert "polymath" in unlocked_ids
    assert "archivist" in unlocked_ids


def test_generate_airing_ics():
    rows = [
        {
            "anime_id": 101,
            "title": "Demon Slayer",
            "next_airing_at": 1800000000,
            "next_airing_episode": 4,
            "duration": 24,
        }
    ]
    ics = app.generate_airing_ics(rows)
    assert "BEGIN:VCALENDAR" in ics
    assert "Demon Slayer - Episode 4" in ics
    assert "END:VCALENDAR" in ics


def test_get_next_airing_countdown():
    near_future = int(app.time.time()) + 3600
    rows = [{"title": "Jujutsu Kaisen", "next_airing_at": near_future, "next_airing_episode": 12}]
    res = app.get_next_airing_countdown(rows)
    assert res is not None
    assert res["title"] == "Jujutsu Kaisen"
    assert res["episode"] == 12
    assert res["hours"] >= 0


def test_sync_anilist_profile(monkeypatch, isolated_db):
    def fake_response(query, variables):
        return {
            "MediaListCollection": {
                "lists": [
                    {
                        "name": "Completed",
                        "status": "COMPLETED",
                        "entries": [
                            {
                                "status": "COMPLETED",
                                "progress": 12,
                                "score": 95,
                                "repeat": 1,
                                "notes": "Masterpiece",
                                "media": {
                                    "id": 555,
                                    "siteUrl": "https://anilist.co/anime/555",
                                    "title": {"english": "Synced Title"},
                                    "episodes": 12,
                                    "averageScore": 90,
                                },
                            }
                        ],
                    }
                ]
            }
        }

    monkeypatch.setattr(app, "anilist_response", fake_response)
    count = app.sync_anilist_profile("testuser")
    assert count == 1
    rows = app.db_rows()
    assert len(rows) == 1
    assert rows[0]["title"] == "Synced Title"
    assert rows[0]["status"] == "COMPLETED"
    assert rows[0]["user_score"] == 95


def test_manga_tracking_columns(isolated_db):
    with sqlite3.connect(isolated_db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(watchlist)")}
        assert "media_type" in cols
        assert "chapters" in cols
        assert "volumes" in cols


def test_pwa_manifest_file_exists():
    manifest_file = Path(__file__).parents[1] / "manifest.json"
    assert manifest_file.exists()
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert data["display"] == "standalone"
    assert data["short_name"] == "Otaku Orbit"


def test_modular_package_exports():
    import modules
    import modules.api
    import modules.config
    import modules.db
    import modules.services
    import modules.ui

    assert hasattr(modules, "init_db")
    assert hasattr(modules, "anilist_query")
    assert hasattr(modules, "calculate_watch_streak")
    assert hasattr(modules, "render_watchlist")
    assert modules.APP_VERSION == "2.0.0"


def test_composite_database_indices(isolated_db):
    with sqlite3.connect(isolated_db) as conn:
        indices = {row[1] for row in conn.execute("SELECT * FROM sqlite_master WHERE type='index'")}
        assert "idx_watchlist_media_status" in indices
        assert "idx_watch_history_anime" in indices


def test_glassmorphic_styling_in_app_source():
    source = Path(app.__file__).read_text(encoding="utf-8")
    assert "backdrop-filter: blur" in source
    assert "border-radius: 18px" in source
    assert "@media (max-width: 768px)" in source


def test_request_session_user_agent_header():
    session = app._request_session()
    user_agent = session.headers.get("User-Agent", "")
    assert user_agent == f"OtakuOrbit/{app.APP_VERSION}"


def test_format_timestamp_edge_cases():
    ts = 1700000000
    formatted_default = app._format_timestamp(ts)
    assert len(formatted_default) > 0
    formatted_utc = app._format_timestamp(ts, "UTC")
    assert len(formatted_utc) > 0


def test_release_version_consistency_across_files():
    import re

    root = Path(__file__).parents[1]
    app_ver = app.APP_VERSION
    readme = (root / "README.md").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    readme_match = re.search(r"Current version: `([^`]+)`", readme)
    assert readme_match is not None, "README.md missing current version badge"
    assert readme_match.group(1) == app_ver, (
        f"Version mismatch: app.py ({app_ver}) vs README.md ({readme_match.group(1)})"
    )
    assert f"## {app_ver}" in changelog, f"CHANGELOG.md missing release section for {app_ver}"


def test_manifest_and_meta_tags_have_no_indented_code_blocks():
    source = Path(app.__file__).read_text(encoding="utf-8")
    for line in source.splitlines():
        if any(tag in line for tag in ("<link rel=", "<meta name=")):
            assert not line.startswith("    "), f"Tag has 4 leading spaces (renders as code block in Markdown): {line}"


def test_safe_bar_chart_success(monkeypatch):
    called = []
    monkeypatch.setattr(app.st, "bar_chart", lambda data: called.append(data))
    app.safe_bar_chart({"Action": 10, "Adventure": 5})
    assert len(called) == 1
    assert called[0] == {"Action": 10, "Adventure": 5}


def test_safe_bar_chart_fallback_on_altair_exception(monkeypatch):
    def failing_bar_chart(data):
        raise TypeError("TypedDict() got an unexpected keyword argument 'closed'")

    monkeypatch.setattr(app.st, "bar_chart", failing_bar_chart)
    # Must not raise an exception; gracefully renders native fallback
    app.safe_bar_chart({"Action": 10, "Adventure": 5})


def test_render_analytics_resilient_to_chart_failure(monkeypatch, isolated_db):
    def failing_bar_chart(data):
        raise TypeError("TypedDict() got an unexpected keyword argument 'closed'")

    monkeypatch.setattr(app.st, "bar_chart", failing_bar_chart)
    rows = [
        {
            "anime_id": 1,
            "title": "Frieren",
            "genres": "Adventure, Fantasy",
            "user_score": 95,
            "progress": 28,
            "episodes": 28,
            "status": "COMPLETED",
        }
    ]
    # Verify render_analytics executes completely without raising TypeError
    app.render_analytics(rows)


def test_v18_config_constants():
    from modules.config import (
        ANIME_MOODS,
        BINGO_CHALLENGES,
        CUSTOM_SHELVES,
        FRANCHISE_WATCH_ORDERS,
        MEDIA_SUBTYPES,
    )

    assert len(CUSTOM_SHELVES) >= 6
    assert "Masterpiece" in CUSTOM_SHELVES
    assert len(MEDIA_SUBTYPES) >= 6
    assert "TV" in MEDIA_SUBTYPES
    assert "Cozy & Chill" in ANIME_MOODS
    assert len(BINGO_CHALLENGES) == 25
    assert "Fate" in FRANCHISE_WATCH_ORDERS


def test_v18_db_shelves_and_notes(isolated_db):
    from modules.db import (
        batch_update_shelf,
        fetch_episode_notes,
        log_episode_note,
        save_anime,
        update_anime_shelf,
    )

    anime = {
        "id": 888,
        "title": {"english": "Test Anime", "romaji": "Test Anime"},
        "episodes": 12,
        "genres": ["Action"],
        "media_type": "ANIME",
        "format": "TV",
    }
    save_anime(anime, status="WATCHING")

    update_anime_shelf(888, "Masterpiece")
    from modules.db import db_rows

    rows = db_rows()
    saved = next(r for r in rows if r["anime_id"] == 888)
    assert saved.get("shelf") == "Masterpiece"

    batch_update_shelf([888], "Favorites")
    rows = db_rows()
    saved = next(r for r in rows if r["anime_id"] == 888)
    assert saved.get("shelf") == "Favorites"

    log_episode_note(888, 1, "Epic intro fight sequence!")
    notes = fetch_episode_notes(888)
    assert len(notes) == 1
    assert notes[0]["episode"] == 1
    assert "Epic intro" in notes[0]["note"]


def test_v18_db_rewatch_cycles_and_goals(isolated_db):
    from modules.db import (
        fetch_rewatch_cycles,
        fetch_viewing_goal,
        record_rewatch_cycle,
        set_viewing_goal,
    )

    cycle_id = record_rewatch_cycle(101, score=95, notes="Masterpiece rewatch")
    assert cycle_id > 0
    cycles = fetch_rewatch_cycles(101)
    assert len(cycles) == 1
    assert cycles[0]["cycle_number"] == 1
    assert cycles[0]["score"] == 95

    set_viewing_goal(15, "WEEKLY")
    goal = fetch_viewing_goal()
    assert goal is not None
    assert goal["target_count"] == 15
    assert goal["period"] == "WEEKLY"


def test_v18_db_sqlite_backup_and_restore(isolated_db):
    from modules.db import (
        export_sqlite_backup_base64,
        restore_sqlite_backup_base64,
        save_anime,
    )

    anime = {
        "id": 999,
        "title": {"english": "Snapshot Anime", "romaji": "Snapshot Anime"},
        "episodes": 24,
        "genres": ["Sci-Fi"],
        "media_type": "ANIME",
        "format": "TV",
    }
    save_anime(anime, status="COMPLETED")

    b64_str = export_sqlite_backup_base64()
    assert len(b64_str) > 100

    ok = restore_sqlite_backup_base64(b64_str)
    assert ok is True

    from modules.db import db_rows

    rows = db_rows()
    assert any(r["anime_id"] == 999 for r in rows)


def test_v18_pick_random_backlog():
    from modules.services import pick_random_backlog

    items = [
        {"title": "Show A", "status": "PLANNING", "genres": "Action, Sci-Fi", "duration": 24},
        {"title": "Show B", "status": "COMPLETED", "genres": "Comedy", "duration": 24},
        {"title": "Show C", "status": "PLANNING", "genres": "Slice of Life, Comedy", "duration": 20},
    ]

    picked = pick_random_backlog(items, status="PLANNING")
    assert picked is not None
    assert picked["title"] in ["Show A", "Show C"]

    picked_mood = pick_random_backlog(items, status="PLANNING", mood="Cozy & Chill")
    assert picked_mood is not None
    assert picked_mood["title"] == "Show C"


def test_v18_taste_match_and_mood_filters():
    from modules.services import calculate_taste_match_score, filter_by_mood

    library = [
        {"genres": "Action, Adventure, Fantasy", "user_score": 90},
        {"genres": "Action, Sci-Fi", "user_score": 85},
    ]

    candidate_good = {"genres": ["Action", "Adventure"]}
    candidate_bad = {"genres": ["Romance", "Music"]}

    score_good = calculate_taste_match_score(candidate_good, library)
    score_bad = calculate_taste_match_score(candidate_bad, library)
    assert score_good > score_bad

    catalogue = [
        {"title": {"romaji": "Chill Camp"}, "genres": ["Slice of Life", "Comedy"]},
        {"title": {"romaji": "Explosion Attack"}, "genres": ["Action", "Supernatural"]},
    ]
    cozy = filter_by_mood(catalogue, "Cozy & Chill")
    assert len(cozy) == 1
    assert cozy[0]["title"]["romaji"] == "Chill Camp"


def test_v18_franchise_watch_order_and_staff():
    from modules.services import extract_staff_and_directors, get_franchise_watch_order

    order = get_franchise_watch_order("Fate/stay night: Unlimited Blade Works")
    assert order is not None
    assert len(order["release"]) >= 3
    assert len(order["chronological"]) >= 3
    assert "tip" in order

    anime_payload = {
        "staff": {
            "edges": [
                {"role": "Director", "node": {"name": {"full": "Tetsuro Araki"}}},
                {"role": "Series Composition", "node": {"name": {"full": "Yasuko Kobayashi"}}},
            ]
        }
    }
    staff = extract_staff_and_directors(anime_payload)
    assert len(staff) == 2
    assert staff[0]["name"] == "Tetsuro Araki"


def test_v18_theme_previews_and_accent_colors():
    from modules.services import derive_artwork_accent_color, get_theme_video_links

    links = get_theme_video_links("Frieren: Beyond Journey's End")
    assert "YouTube Search" in links
    assert "AnimeThemes" in links

    color = derive_artwork_accent_color("https://example.com/cover.jpg")
    assert color.startswith("#")
    assert len(color) == 7


def test_v18_seiyuu_matrix_and_spoiler_mask():
    from modules.services import apply_spoiler_mask, build_seiyuu_character_matrix

    library_rows = [
        {"title": "Anime A", "characters_json": '[{"character": "Char 1", "voice_actor": "Mamoru Miyano"}]'},
        {"title": "Anime B", "characters_json": '[{"character": "Char 2", "voice_actor": "Mamoru Miyano"}]'},
    ]

    matrix = build_seiyuu_character_matrix(library_rows)
    assert "Mamoru Miyano" in matrix
    assert len(matrix["Mamoru Miyano"]) == 2

    raw_text = "The protagonist dies at the ending and was betrayed."
    masked = apply_spoiler_mask(raw_text)
    assert "spoiler" in masked.lower()
    assert "orbit-spoiler-box" in masked
    assert "SPOILER BLOCKED" in masked


def test_v18_passport_and_tierlist_svg():
    from modules.services import generate_otaku_passport_svg, generate_tier_list_svg

    rows = [
        {
            "title": "Anime A",
            "status": "COMPLETED",
            "progress": 12,
            "episodes": 12,
            "genres": "Action",
            "user_score": 95,
        },
        {
            "title": "Anime B",
            "status": "COMPLETED",
            "progress": 24,
            "episodes": 24,
            "genres": "Action",
            "user_score": 85,
        },
    ]

    passport_svg = generate_otaku_passport_svg("TestUser", rows)
    assert "<svg" in passport_svg
    assert "TestUser" in passport_svg
    assert "OTAKU ORBIT PASSPORT" in passport_svg

    tier_svg = generate_tier_list_svg(rows)
    assert "<svg" in tier_svg
    assert "TIER LIST" in tier_svg


def test_v18_bingo_and_user_taste_compatibility():
    from modules.services import calculate_user_taste_compatibility, evaluate_bingo_card

    rows = [
        {"title": "Anime A", "status": "COMPLETED", "genres": "Action", "episodes": 12},
    ]
    history = [{"watched_at": "2026-10-01"}]

    bingo = evaluate_bingo_card(rows, history)
    assert len(bingo) == 25
    assert any(b["completed"] for b in bingo)

    friend_rows = [
        {"title": "Anime A", "genres": "Action, Adventure"},
        {"title": "Anime Friend Only", "genres": "Action, Sci-Fi"},
    ]
    compat = calculate_user_taste_compatibility(rows, friend_rows)
    assert "compatibility_pct" in compat
    assert compat["compatibility_pct"] > 0
    assert "recommendations" in compat


def test_v18_kitsu_and_simkl_export_import(isolated_db):
    from modules.services import (
        export_kitsu_json,
        export_simkl_csv,
        import_kitsu_json,
        import_simkl_csv,
    )

    rows = [
        {
            "anime_id": 1234,
            "title": "Steins;Gate",
            "status": "COMPLETED",
            "progress": 24,
            "episodes": 24,
            "user_score": 95,
        }
    ]

    kitsu_str = export_kitsu_json(rows)
    assert "Steins;Gate" in kitsu_str
    count_kitsu = len(import_kitsu_json(kitsu_str))
    assert count_kitsu >= 1

    simkl_csv = export_simkl_csv(rows)
    assert "Steins;Gate" in simkl_csv
    count_simkl = len(import_simkl_csv(simkl_csv))
    assert count_simkl >= 1


def test_v18_discord_webhook_and_service_worker():
    from modules.services import (
        generate_discord_webhook_payload,
        generate_service_worker_js,
        prepare_anilist_sync_payload,
    )

    payload = generate_discord_webhook_payload("Frieren", 28, 28, 100)
    assert "embeds" in payload
    assert "Frieren" in payload["embeds"][0]["title"]

    sw_js = generate_service_worker_js()
    assert "otaku-orbit-cache" in sw_js
    assert "addEventListener" in sw_js

    sync_payload = prepare_anilist_sync_payload(123, "COMPLETED", 24, 90)
    assert "SaveMediaListEntry" in sync_payload["query"]
    assert sync_payload["variables"]["mediaId"] == 123


def test_v19_filler_guides_and_canon():
    from modules.services import get_filler_guide, get_next_canon_episode, is_episode_filler

    guide = get_filler_guide("Naruto")
    assert guide is not None
    assert guide["total"] == 220
    assert guide["filler_count"] > 80
    assert guide["filler_percentage"] > 35.0

    assert is_episode_filler("Naruto", 101) is True
    assert is_episode_filler("Naruto", 1) is False
    assert is_episode_filler("Unknown Series", 5) is False

    next_canon = get_next_canon_episode("Naruto", 101)
    assert next_canon == 107

    guide_bleach = get_filler_guide("Bleach")
    assert guide_bleach is not None
    assert is_episode_filler("Bleach", 64) is True


def test_v19_vibe_search_and_trope_matcher():
    from modules.services import match_anime_by_trope, search_by_vibe

    catalogue = [
        {
            "id": 1,
            "title": {"english": "Cyberpunk Edgerunners", "romaji": "Cyberpunk Edgerunners"},
            "description": "A street kid trying to survive in a technology and body modification-obsessed city of the future.",
            "genres": ["Action", "Sci-Fi", "Psychological"],
        },
        {
            "id": 2,
            "title": {"english": "Yuru Camp", "romaji": "Yuru Camp"},
            "description": "Cozy camping outdoors in peaceful nature with warm hotpot soup.",
            "genres": ["Slice of Life", "Comedy"],
        },
    ]

    results_cyber = search_by_vibe("dark futuristic cyberpunk city technology", catalogue)
    assert len(results_cyber) >= 1
    assert results_cyber[0]["id"] == 1

    results_camp = search_by_vibe("cozy peaceful warm camping", catalogue)
    assert len(results_camp) >= 1
    assert results_camp[0]["id"] == 2

    rivalry_matches = match_anime_by_trope("Rivalry Duo", catalogue)
    assert any(a["id"] == 1 for a in rivalry_matches)


def test_v19_backlog_priority_and_sequel_radar():
    from modules.services import calculate_backlog_priority, detect_franchise_sequels

    rows = [
        {"title": "Show Short", "status": "PLANNING", "user_score": 90, "episodes": 12},
        {"title": "Show Long", "status": "PLANNING", "user_score": 85, "episodes": 100},
        {"title": "Show Mid", "status": "PLANNING", "user_score": 70, "episodes": 24},
    ]

    prioritized = calculate_backlog_priority(rows)
    assert prioritized[0]["title"] == "Show Short"

    completed = [
        {"title": "Attack on Titan Season 1", "status": "COMPLETED"},
        {"title": "Steins;Gate", "status": "COMPLETED"},
    ]
    catalogue = [
        {"title": {"english": "Attack on Titan Season 2", "romaji": "Attack on Titan Season 2"}},
        {"title": {"english": "Steins;Gate 0", "romaji": "Steins;Gate 0"}},
        {"title": {"english": "Unrelated Anime", "romaji": "Unrelated Anime"}},
    ]
    detected = detect_franchise_sequels(completed, catalogue)
    assert len(detected) >= 2


def test_v19_ambient_glow_and_custom_theme():
    from modules.services import create_custom_theme_palette, generate_ambient_glow_css

    css = generate_ambient_glow_css("#00f0ff")
    assert "<style>" in css
    assert "#00f0ff" in css
    assert "radial-gradient" in css

    theme = create_custom_theme_palette("#ff007f", "rgba(255,0,127,0.3)", "#00ffcc", "#0a0a14")
    assert theme["primary"] == "#ff007f"
    assert theme["metric"] == "#00ffcc"
    assert "rgba" in theme["glow"]


def test_v19_cinematic_modal_and_mini_dock():
    from modules.services import (
        generate_cinematic_modal_html,
        get_mini_dock_state,
        get_sound_effects_data_uris,
    )

    anime = {
        "id": 101,
        "title": {"english": "Cinematic Test", "romaji": "Cinematic Test"},
        "bannerImage": "https://example.com/banner.jpg",
        "averageScore": 92,
        "episodes": 24,
        "format": "TV",
        "description": "An epic journey through deep space and starlight.",
    }
    html_code = generate_cinematic_modal_html(anime)
    assert "Cinematic Test" in html_code
    assert "92%" in html_code

    rows = [
        {"anime_id": 101, "title": "In Progress Anime", "status": "WATCHING", "progress": 5, "episodes": 12},
    ]
    dock = get_mini_dock_state(rows)
    assert dock is not None
    assert dock["title"] == "In Progress Anime"
    assert dock["progress"] == 5
    assert dock["next_episode"] == 6

    sounds = get_sound_effects_data_uris()
    assert "click" in sounds
    assert "data:audio/wav;base64" in sounds["click"]


def test_v19_anime_wrapped_and_fantasy_league():
    from modules.services import (
        evaluate_fantasy_score,
        generate_anime_wrapped_data,
        generate_anime_wrapped_svg,
    )

    rows = [
        {
            "title": "Anime A",
            "status": "COMPLETED",
            "progress": 12,
            "episodes": 12,
            "genres": "Action, Shounen",
            "duration": 24,
        },
        {"title": "Anime B", "status": "COMPLETED", "progress": 24, "episodes": 24, "genres": "Action", "duration": 24},
    ]
    history = [
        {"watched_at": "2026-10-24T12:00:00"},
        {"watched_at": "2026-10-24T14:00:00"},
    ]

    wrapped_data = generate_anime_wrapped_data(rows, history)
    assert wrapped_data["total_episodes"] == 36
    assert wrapped_data["completed_count"] == 2
    assert wrapped_data["top_genre"] == "Action"
    assert "Shonen Champion" in wrapped_data["archetype"]["title"]

    svg_wrapped = generate_anime_wrapped_svg(wrapped_data, "TestHero")
    assert "<svg" in svg_wrapped
    assert "TESTHERO" in svg_wrapped
    assert "OTAKU ORBIT WRAPPED" in svg_wrapped

    predictions = [
        {"anime_id": 1, "predicted_rank": 1},
        {"anime_id": 2, "predicted_rank": 3},
    ]
    actual_ranks = {1: 1, 2: 4}
    score = evaluate_fantasy_score(predictions, actual_ranks)
    assert score == 160


def test_v19_bujo_tracker_and_tier_templates():
    from modules.services import (
        generate_bujo_tracker_html,
        generate_bujo_tracker_markdown,
        get_tier_list_template,
    )

    rows = [
        {"title": "Frieren", "status": "COMPLETED", "progress": 28, "episodes": 28, "user_score": 100},
    ]
    bujo_md = generate_bujo_tracker_markdown(rows)
    assert "# 📓 Otaku Orbit Bullet Journal" in bujo_md
    assert "Frieren" in bujo_md
    assert "★★★★★" in bujo_md

    bujo_html = generate_bujo_tracker_html(rows)
    assert "<!DOCTYPE html>" in bujo_html
    assert "Frieren" in bujo_html

    template = get_tier_list_template("Opening Themes (OST)")
    assert "S" in template
    assert "Legendary Banger" in template["S"]


def test_v19_watch_party_sync_and_studio_loyalty():
    from modules.services import (
        calculate_studio_loyalty_index,
        generate_watch_party_sync_link,
        parse_watch_party_sync_link,
    )

    link = generate_watch_party_sync_link(555, "Chainsaw Man", 12, 120)
    assert "party=1" in link
    assert "anime_id=555" in link

    parsed = parse_watch_party_sync_link(link)
    assert parsed["is_party"] is True
    assert parsed["anime_id"] == 555
    assert parsed["episode"] == 12
    assert parsed["timestamp_sec"] == 120

    rows = [
        {"title": "Demon Slayer by Ufotable", "progress": 26, "user_score": 95},
        {"title": "Fate UBW (Ufotable)", "progress": 25, "user_score": 90},
    ]
    loyalty = calculate_studio_loyalty_index(rows)
    assert "Ufotable" in loyalty
    assert loyalty["Ufotable"]["titles"] == 2
    assert loyalty["Ufotable"]["episodes"] == 51
    assert loyalty["Ufotable"]["avg_score"] == 92.5


def test_v19_seiyuu_screen_time_and_drop_off():
    from modules.services import (
        calculate_drop_off_statistics,
        calculate_era_distribution,
        calculate_seiyuu_screen_time,
    )

    rows = [
        {
            "title": "Anime Mamoru",
            "progress": 24,
            "duration": 24,
            "characters_json": '[{"seiyuu": "Mamoru Miyano", "character": "Light"}]',
        }
    ]
    st_data = calculate_seiyuu_screen_time(rows)
    assert len(st_data) >= 1
    assert st_data[0]["actor"] == "Mamoru Miyano"
    assert st_data[0]["minutes"] == 576

    dropped_rows = [
        {"title": "Dropped Quick", "status": "DROPPED", "progress": 2},
        {"title": "Dropped Mid", "status": "DROPPED", "progress": 7},
        {"title": "Finished", "status": "COMPLETED", "progress": 12},
    ]
    drop_stats = calculate_drop_off_statistics(dropped_rows)
    assert drop_stats["dropped_count"] == 2
    assert drop_stats["rule_of_three_pct"] == 50.0

    era_rows = [
        {"title": "Modern Show", "next_airing_at": 1700000000},
    ]
    eras = calculate_era_distribution(era_rows)
    assert "2020s Next-Gen Era" in eras


def test_v19_pacing_alert_and_custom_webhook():
    from datetime import datetime

    from modules.services import evaluate_pacing_alert, generate_custom_webhook_payload

    history_ahead = [{"watched_at": datetime.now().isoformat()} for _ in range(15)]
    alert_ahead = evaluate_pacing_alert(history_ahead, weekly_goal=10)
    assert alert_ahead["status"] == "ahead"
    assert alert_ahead["watched_this_week"] == 15

    alert_behind = evaluate_pacing_alert([], weekly_goal=10)
    assert alert_behind["status"] == "behind"

    payload = generate_custom_webhook_payload(
        "EPISODE_COMPLETED", {"title": "Frieren", "progress": 28, "user_score": 100}
    )
    assert payload["event"] == "EPISODE_COMPLETED"
    assert payload["anime"]["title"] == "Frieren"
    assert payload["anime"]["score"] == 100


def test_v19_multi_profile_and_api_tokens(isolated_db):
    from modules.db import (
        create_user_profile,
        delete_user_profile,
        fetch_api_token,
        fetch_fantasy_predictions,
        list_user_profiles,
        record_fantasy_prediction,
        save_api_token,
    )

    profiles = list_user_profiles()
    assert "Default" in profiles

    created = create_user_profile("Family SFW")
    assert created is True
    assert "Family SFW" in list_user_profiles()

    deleted = delete_user_profile("Family SFW")
    assert deleted is True

    save_api_token("anilist", "test_oauth_token_12345")
    fetched = fetch_api_token("anilist")
    assert fetched == "test_oauth_token_12345"

    pred_id = record_fantasy_prediction("FALL", 2026, 999, "Chainsaw Man S2", predicted_rank=1)
    assert pred_id > 0
    preds = fetch_fantasy_predictions("FALL", 2026)
    assert len(preds) == 1
    assert preds[0]["anime_title"] == "Chainsaw Man S2"


def test_v19_direct_sync_gist_and_rss():
    from modules.services import (
        generate_direct_sync_request,
        generate_watchlist_rss_feed,
        prepare_gist_backup_payload,
    )

    sync_req = generate_direct_sync_request("anilist", "token123", "UPDATE", {"id": 10})
    assert sync_req["method"] == "POST"
    assert "Bearer token123" in sync_req["headers"]["Authorization"]

    gist = prepare_gist_backup_payload([{"title": "Anime Test", "status": "COMPLETED"}])
    assert "files" in gist
    assert "otaku_orbit_backup.json" in gist["files"]

    rss = generate_watchlist_rss_feed([{"anime_id": 1, "title": "RSS Show", "progress": 1, "next_airing_episode": 2}])
    assert "<?xml" in rss
    assert '<rss version="2.0">' in rss
    assert "RSS Show - Episode 2" in rss


def test_v20_daily_trivia_and_ost_quiz(isolated_db):
    import app
    from modules.db import fetch_trivia_streak, record_trivia_score
    from modules.services import (
        evaluate_ost_quiz_answer,
        evaluate_trivia_answer,
        generate_daily_trivia_question,
        generate_ost_quiz_question,
    )

    app.init_db("test_owner")
    t = generate_daily_trivia_question()
    assert "question" in t
    assert "options" in t
    res_correct = evaluate_trivia_answer(t["id"], t["answer"])
    assert res_correct["correct"] is True
    assert res_correct["points"] == 50

    res_incorrect = evaluate_trivia_answer(t["id"], "Completely Wrong Option 999")
    assert res_incorrect["correct"] is False
    assert res_incorrect["points"] == 0

    score_res = record_trivia_score(50, True, owner_id="test_owner")
    assert score_res["current_streak"] == 1
    assert score_res["total_score"] == 50

    streak = fetch_trivia_streak(owner_id="test_owner")
    assert streak["current_streak"] == 1
    assert streak["total_score"] == 50

    ost = generate_ost_quiz_question()
    assert "song_title" in ost
    assert "options" in ost
    ost_res = evaluate_ost_quiz_answer(ost["song_title"], ost["answer"])
    assert ost_res["correct"] is True
    assert ost_res["points"] == 50


def test_v20_daily_quests_and_completion(isolated_db):
    import app
    from modules.db import fetch_daily_quest_states, record_quest_progress
    from modules.services import check_quest_completion, generate_daily_quests

    app.init_db("test_owner")
    quests = generate_daily_quests()
    assert len(quests) >= 3

    record_quest_progress("quest_watch_ep", 1, owner_id="test_owner")
    states = fetch_daily_quest_states(owner_id="test_owner")
    assert any(s["quest_id"] == "quest_watch_ep" for s in states)

    assert check_quest_completion("quest_watch_ep", current_progress=1) is True


def test_v20_binge_planner_and_speed_calculator():
    from modules.services import (
        calculate_speed_adjusted_runtime,
        plan_binge_schedule,
    )

    rows = [
        {"title": "Show 1", "duration": 24, "progress": 0, "episodes": 12, "status": "WATCHING"},
        {"title": "Show 2", "duration": 24, "progress": 0, "episodes": 12, "status": "WATCHING"},
    ]
    binge = plan_binge_schedule(rows, available_minutes=120)
    assert binge["planned_episodes"] == 5
    assert binge["total_minutes"] == 120

    speed = calculate_speed_adjusted_runtime(120, 1.5)
    assert speed["adjusted_minutes"] == 80
    assert speed["minutes_saved"] == 40
    assert speed["playback_speed"] == 1.5


def test_v20_manga_sync_and_watchlist_decay():
    from modules.services import (
        audit_watchlist_decay,
        get_manga_chapter_sync,
    )

    sync = get_manga_chapter_sync("Frieren: Beyond Journey's End", current_episode=28)
    assert sync is not None
    assert sync["estimated_chapter"] == 58
    assert "manga" in sync["note"].lower()

    none_sync = get_manga_chapter_sync("Nonexistent Anime Title XYZ", current_episode=1)
    assert none_sync is None

    stagnant_rows = [
        {
            "title": "Stagnant Show",
            "updated_at": "2020-01-01 00:00:00",
            "status": "PLANNING",
            "progress": 0,
            "duration": 24,
            "episodes": 12,
        },
        {
            "title": "Active Show",
            "updated_at": "2026-10-31 00:00:00",
            "status": "PLANNING",
            "progress": 0,
            "duration": 24,
            "episodes": 12,
        },
    ]
    decay = audit_watchlist_decay(stagnant_rows, decay_days=60)
    assert decay["stale_count"] == 1
    assert decay["stale_titles"][0]["title"] == "Stagnant Show"


def test_v20_lofi_player_and_trailer_embed():
    from modules.services import (
        generate_trailer_theater_embed,
        render_lofi_player_html,
    )

    player = render_lofi_player_html(stream_index=0)
    assert "<iframe" in player
    assert "youtube.com/embed" in player

    theater = generate_trailer_theater_embed("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Never Gonna Give You Up")
    assert "dQw4w9WgXcQ" in theater
    assert "allowfullscreen" in theater


def test_v20_wallpaper_poster_and_quotes():
    from modules.services import (
        generate_wallpaper_poster_svg,
        get_character_quote,
    )

    svg = generate_wallpaper_poster_svg(
        {"title": "Frieren", "score": 91, "genres": "Fantasy, Adventure"}, orientation="landscape"
    )
    assert "<svg" in svg
    assert "FRIEREN" in svg

    quote = get_character_quote("Frieren")
    assert "character" in quote
    assert "quote" in quote


def test_v20_arc_progression_and_genre_radar():
    from modules.services import (
        calculate_genre_radar_metrics,
        generate_arc_progression_data,
    )

    arc = generate_arc_progression_data("Hunter x Hunter")
    assert len(arc) > 0
    assert "name" in arc[0]

    radar = calculate_genre_radar_metrics(
        [
            {"genres": "Action, Fantasy", "score": 90},
            {"genres": "Fantasy, Adventure", "score": 85},
        ]
    )
    assert "Fantasy" in radar
    assert radar["Fantasy"]["user_pct"] == 50.0


def test_v20_time_milestones_and_voice_actors():
    from modules.services import (
        build_voice_actor_network,
        calculate_time_equivalence_milestones,
    )

    milestones = calculate_time_equivalence_milestones(total_hours=120)
    assert len(milestones) > 0
    assert any(
        "flight" in m["milestone"].lower() or "book" in m["milestone"].lower() or "orbit" in m["milestone"].lower()
        for m in milestones
    )

    network = build_voice_actor_network(
        [
            {"title": "Show A", "characters_json": json.dumps([{"voice_actor": "Aoi Yuuki", "character": "Maomao"}])},
            {"title": "Show B", "characters_json": json.dumps([{"voice_actor": "Aoi Yuuki", "character": "Tanya"}])},
        ]
    )
    assert "nodes" in network
    assert "links" in network
    assert any(n["name"] == "Aoi Yuuki" for n in network["nodes"])


def test_v20_headless_api_and_cloud_sync(isolated_db):
    import app
    from modules.services import (
        generate_indexeddb_mirror_js,
        generate_web_share_html,
        handle_headless_request,
        prepare_s3_backup_payload,
    )

    app.init_db("test_owner")
    health = handle_headless_request("GET /api/v1/health")
    assert health["status"] == 200
    assert health["data"]["version"] == "2.0.0"

    watchlist_req = handle_headless_request("GET", "/api/v1/watchlist", owner_id="test_owner")
    assert watchlist_req["status"] == 200
    assert isinstance(watchlist_req["data"], list)

    s3_payload = prepare_s3_backup_payload([{"title": "S3 Show"}], bucket="otaku-backups")
    assert s3_payload["bucket"] == "otaku-backups"
    assert "key" in s3_payload
    assert "body" in s3_payload

    idb_js = generate_indexeddb_mirror_js([{"title": "IDB Show"}])
    assert "indexedDB" in idb_js
    assert "IDB Show" in idb_js

    share_html = generate_web_share_html("Otaku Orbit", "My Anime List", "https://otaku-orbit.streamlit.app/")
    assert "navigator.share" in share_html
