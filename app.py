from __future__ import annotations

import sqlite3
import json
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
import streamlit as st


APP_NAME = "Otaku Orbit"
AUTHOR_CREDIT = "Made by Shashank — with the spirit of Plus Ultra ✦"
API_URL = "https://graphql.anilist.co"
DB_PATH = Path(__file__).with_name("anime_companion.db")
REQUEST_ATTEMPTS = 3
WATCH_STATUSES = ["WATCHING", "PLANNING", "COMPLETED", "DROPPED"]

SEARCH_QUERY = """
query ($search: String, $season: MediaSeason, $seasonYear: Int, $page: Int) {
  Page(page: $page, perPage: 24) {
    pageInfo { hasNextPage }
    media(search: $search, season: $season, seasonYear: $seasonYear,
          type: ANIME, sort: POPULARITY_DESC) {
      id title { romaji english native } coverImage { large }
      description(asHtml: false) episodes duration status
      averageScore popularity genres season seasonYear format isAdult
      nextAiringEpisode { airingAt episode }
      studios(isMain: true) { nodes { name } }
    }
  }
}
"""

TRENDING_QUERY = """
query { Page(page: 1, perPage: 24) {
  media(type: ANIME, sort: TRENDING_DESC) {
    id title { romaji english native } coverImage { large }
    description(asHtml: false) episodes duration status averageScore popularity genres
    season seasonYear format isAdult nextAiringEpisode { airingAt episode }
    studios(isMain: true) { nodes { name } }
  }
} }
"""


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS watchlist (
            anime_id INTEGER PRIMARY KEY, title TEXT NOT NULL, image TEXT,
            status TEXT NOT NULL DEFAULT 'PLANNING', progress INTEGER NOT NULL DEFAULT 0,
            episodes INTEGER, score INTEGER, genres TEXT, updated_at TEXT NOT NULL
        )""")


def db_rows() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM watchlist ORDER BY updated_at DESC")]


def save_anime(anime: dict[str, Any], status: str = "PLANNING", progress: int = 0) -> None:
    title = display_title(anime)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""INSERT INTO watchlist
            (anime_id, title, image, status, progress, episodes, score, genres, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(anime_id) DO UPDATE SET title=excluded.title, image=excluded.image,
            status=excluded.status, progress=excluded.progress, episodes=excluded.episodes,
            score=excluded.score, genres=excluded.genres, updated_at=excluded.updated_at""",
            (anime["id"], title, anime.get("coverImage", {}).get("large"), status, progress,
             anime.get("episodes"), anime.get("averageScore"), ", ".join(anime.get("genres", [])),
             datetime.now().isoformat(timespec="seconds")))


def update_progress(anime_id: int, progress: int, status: str) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("UPDATE watchlist SET progress=?, status=?, updated_at=? WHERE anime_id=?",
                           (progress, status, datetime.now().isoformat(timespec="seconds"), anime_id))


def remove_anime(anime_id: int) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM watchlist WHERE anime_id=?", (anime_id,))


def export_watchlist(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, indent=2, ensure_ascii=False)


def import_watchlist(payload: str) -> int:
    imported = json.loads(payload)
    if not isinstance(imported, list):
        raise ValueError("A watchlist backup must contain a list of titles.")
    restored = 0
    with sqlite3.connect(DB_PATH) as connection:
        for row in imported:
            if not isinstance(row, dict) or not row.get("anime_id") or not row.get("title"):
                continue
            connection.execute("""INSERT INTO watchlist
                (anime_id, title, image, status, progress, episodes, score, genres, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(anime_id) DO UPDATE SET title=excluded.title, image=excluded.image,
                status=excluded.status, progress=excluded.progress, episodes=excluded.episodes,
                score=excluded.score, genres=excluded.genres, updated_at=excluded.updated_at""",
                (int(row["anime_id"]), str(row["title"]), row.get("image"),
                 row.get("status", "PLANNING") if row.get("status") in WATCH_STATUSES else "PLANNING",
                 max(0, int(row.get("progress", 0))), row.get("episodes"), row.get("score"),
                 row.get("genres", ""), row.get("updated_at", datetime.now().isoformat(timespec="seconds"))))
            restored += 1
    return restored


@st.cache_data(ttl=900, show_spinner=False)
def anilist_query(query: str, variables: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    request_body = {"query": query, "variables": variables or {}}
    response: requests.Response | None = None
    for attempt in range(REQUEST_ATTEMPTS):
        try:
            response = requests.post(API_URL, json=request_body,
                                     headers={"User-Agent": "OtakuOrbit/1.0"}, timeout=15)
            response.raise_for_status()
            break
        except requests.RequestException:
            if attempt == REQUEST_ATTEMPTS - 1:
                raise
            time.sleep(0.35 * (2 ** attempt))
    if response is None:
        raise requests.RequestException("AniList did not return a response")
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "AniList returned an error"))
    data = payload.get("data", {})
    return data.get("Page", {}).get("media", [])


def fetch_anime(search: str = "", season: str | None = None, year: int | None = None) -> list[dict[str, Any]]:
    variables: dict[str, Any] = {"search": search or None, "page": 1}
    if season:
        variables["season"], variables["seasonYear"] = season, year
    return anilist_query(SEARCH_QUERY, variables)


def filter_anime(results: list[dict[str, Any]], genre: str = "All genres",
                 format_name: str = "All formats", minimum_score: int = 0,
                 include_adult: bool = False) -> list[dict[str, Any]]:
    filtered = []
    for anime in results:
        if not include_adult and anime.get("isAdult"):
            continue
        if genre != "All genres" and genre not in anime.get("genres", []):
            continue
        if format_name != "All formats" and anime.get("format") != format_name:
            continue
        if (anime.get("averageScore") or 0) < minimum_score:
            continue
        filtered.append(anime)
    return filtered


def render_filters(results: list[dict[str, Any]], key_prefix: str) -> list[dict[str, Any]]:
    genres = sorted({genre for anime in results for genre in anime.get("genres", [])})
    formats = sorted({anime.get("format") for anime in results if anime.get("format")})
    with st.expander("Filter results", expanded=False):
        first, second, third, fourth = st.columns(4)
        genre = first.selectbox("Genre", ["All genres", *genres], key=f"genre-{key_prefix}")
        format_name = second.selectbox("Format", ["All formats", *formats], key=f"format-{key_prefix}")
        minimum_score = third.slider("Minimum score", 0, 90, 0, 5, key=f"score-{key_prefix}")
        include_adult = fourth.checkbox("Include mature titles", key=f"adult-{key_prefix}")
    filtered = filter_anime(results, genre, format_name, minimum_score, include_adult)
    st.caption(f"Showing {len(filtered)} of {len(results)} titles")
    return filtered


def display_title(anime: dict[str, Any]) -> str:
    title = anime.get("title", {})
    return title.get("english") or title.get("romaji") or title.get("native") or "Untitled"


def clean_description(text: str | None) -> str:
    if not text:
        return "No synopsis available."
    return " ".join(text.replace("<br>", " ").split())


def format_airing(anime: dict[str, Any]) -> str:
    airing = anime.get("nextAiringEpisode")
    if not airing:
        return "No upcoming episode"
    when = datetime.fromtimestamp(airing["airingAt"]).strftime("%d %b, %H:%M")
    return f"Episode {airing['episode']} · {when}"


def render_card(anime: dict[str, Any], saved_ids: set[int], key_prefix: str) -> None:
    title = display_title(anime)
    image, details = st.columns([1, 2.2], gap="medium")
    with image:
        if anime.get("coverImage", {}).get("large"):
            st.image(anime["coverImage"]["large"], use_container_width=True)
    with details:
        st.subheader(title)
        score = anime.get("averageScore")
        meta = f"{anime.get('format', 'ANIME')}  ·  {anime.get('status', 'UNKNOWN')}  ·  {score or '—'}/100"
        st.caption(meta)
        st.write(clean_description(anime.get("description"))[:420] + "…")
        genres = anime.get("genres", [])
        if genres:
            st.caption(" · ".join(genres))
        if anime.get("nextAiringEpisode"):
            st.info(format_airing(anime))
        if anime["id"] in saved_ids:
            st.success("In your watchlist")
        else:
            if st.button("＋ Add to watchlist", key=f"add-{key_prefix}-{anime['id']}", use_container_width=True):
                save_anime(anime)
                st.rerun()


def render_watchlist() -> None:
    rows = db_rows()
    st.title("Your watchlist")
    if not rows:
        st.info("Your watchlist is empty. Discover something new from the sidebar.")
        return
    counts = {status: sum(row["status"] == status for row in rows) for status in ["WATCHING", "PLANNING", "COMPLETED", "DROPPED"]}
    cols = st.columns(4)
    for column, (label, value) in zip(cols, counts.items()):
        column.metric(label.title(), value)
    st.divider()
    active = [row for row in rows if row["status"] == "WATCHING"]
    if active:
        st.subheader("Continue watching")
        st.caption("Your next episodes are always at the top of the orbit.")
        for row in active[:3]:
            total = row["episodes"] or 0
            progress = row["progress"]
            remaining = max(total - progress, 0) if total else "?"
            st.write(f"**{row['title']}** · episode {progress + 1} next · {remaining} remaining")
        st.divider()
    st.subheader("All saved titles")
    search = st.text_input("Filter your watchlist", placeholder="Search saved titles…")
    status_filter = st.selectbox("Status", ["All statuses", *WATCH_STATUSES])
    visible_rows = [row for row in rows
                    if (not search or search.lower() in row["title"].lower())
                    and (status_filter == "All statuses" or row["status"] == status_filter)]
    for row in visible_rows:
        left, right = st.columns([3, 2])
        with left:
            st.subheader(row["title"])
            total = row["episodes"] or 0
            progress = row["progress"]
            st.progress(min(progress / total, 1.0) if total else 0.0, text=f"Episode {progress}/{total or '?'}")
            st.caption(f"Score: {row['score'] or '—'}  ·  {row['genres'] or 'Genre unknown'}")
        with right:
            status = st.selectbox("Status", WATCH_STATUSES,
                                  index=WATCH_STATUSES.index(row["status"]),
                                  key=f"status-{row['anime_id']}")
            new_progress = st.number_input("Episodes watched", min_value=0, max_value=row["episodes"] or 9999,
                                           value=row["progress"], key=f"progress-{row['anime_id']}")
            a, b = st.columns(2)
            if a.button("Save", key=f"save-{row['anime_id']}", use_container_width=True):
                update_progress(row["anime_id"], int(new_progress), status)
                st.rerun()
            if b.button("Remove", key=f"remove-{row['anime_id']}", use_container_width=True):
                remove_anime(row["anime_id"])
                st.rerun()
        st.divider()
    if not visible_rows:
        st.info("No saved titles match those filters.")
    with st.expander("Backup your watchlist"):
        st.caption("Export a portable JSON backup or restore one on another device.")
        st.download_button("Download backup", export_watchlist(rows), "otaku-orbit-watchlist.json",
                           "application/json", use_container_width=True)
        uploaded = st.file_uploader("Restore JSON backup", type="json")
        if uploaded is not None and st.button("Restore backup", use_container_width=True):
            try:
                count = import_watchlist(uploaded.getvalue().decode("utf-8"))
                st.success(f"Restored {count} title(s).")
                st.rerun()
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
                st.error(f"Could not restore that backup: {error}")


def render_stats(rows: list[dict[str, Any]]) -> None:
    st.title("Your anime statistics")
    if not rows:
        st.info("Add a few anime to see your personal statistics.")
        return
    completed_episodes = sum(row["progress"] for row in rows)
    minutes = sum((row["episodes"] or 0) * 24 for row in rows)
    watched_minutes = sum(min(row["progress"], row["episodes"] or row["progress"]) * 24 for row in rows)
    cols = st.columns(4)
    cols[0].metric("Titles", len(rows))
    cols[1].metric("Episodes watched", completed_episodes)
    cols[2].metric("Time watched", f"{watched_minutes // 60}h")
    cols[3].metric("Time in backlog", f"{max(minutes - watched_minutes, 0) // 60}h")
    genre_counts: dict[str, int] = {}
    for row in rows:
        for genre in filter(None, row["genres"].split(", ")):
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    if genre_counts:
        st.subheader("Your genre profile")
        st.bar_chart(dict(sorted(genre_counts.items(), key=lambda item: item[1], reverse=True)[:10]))


def render_recommendations(rows: list[dict[str, Any]], saved_ids: set[int]) -> None:
    st.title("Picked for you")
    if not rows:
        st.info("Save a few anime first and your recommendations will learn your taste.")
        return
    preferred = {genre.strip() for row in rows for genre in row["genres"].split(",") if genre.strip()}
    st.write("Based on the genres in your watchlist: " + ", ".join(sorted(preferred)) + ".")
    try:
        candidates = anilist_query(TRENDING_QUERY)
    except requests.RequestException:
        st.error("Could not load recommendations right now. Please try again shortly.")
        return
    ranked = sorted(
        (anime for anime in candidates if anime["id"] not in saved_ids),
        key=lambda anime: (len(preferred.intersection(anime.get("genres", []))),
                           anime.get("averageScore") or 0, anime.get("popularity") or 0),
        reverse=True,
    )
    for anime in ranked[:8]:
        with st.container(border=True):
            render_card(anime, saved_ids, "recommendation")


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="✦", layout="wide", initial_sidebar_state="expanded")
    init_db()
    st.markdown("""<style>
    .block-container {max-width: 1320px; padding-top: 2rem; padding-bottom: 5rem;}
    [data-testid="stMetricValue"] {color: #f4b8ff;}
    [data-testid="stSidebar"] {background: linear-gradient(180deg, #17132a 0%, #0e1020 100%);}
    [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    div[data-testid="stVerticalBlockBorderWrapper"] {border-color: rgba(244,184,255,.18); border-radius: 18px;}
    .orbit-hero {padding: 1.4rem 1.6rem; margin-bottom: 1.4rem; border: 1px solid rgba(244,184,255,.2); border-radius: 22px; background: radial-gradient(circle at 85% 15%, rgba(111,76,255,.32), transparent 38%), linear-gradient(120deg, #211939, #151526);}
    .orbit-kicker {font-size: .76rem; letter-spacing: .18em; text-transform: uppercase; color: #f4b8ff; font-weight: 700;}
    .orbit-hero h1 {margin: .2rem 0 .4rem; font-size: clamp(2rem, 5vw, 3.5rem);}
    .orbit-muted {color: #aaa8bd; max-width: 700px;}
    .orbit-credit {position: fixed; bottom: 12px; left: 0; right: 0; text-align: center; color: #858297; font-size: .75rem; z-index: 999;}
    </style>""", unsafe_allow_html=True)
    rows = db_rows()
    saved_ids = {row["anime_id"] for row in rows}
    with st.sidebar:
        st.markdown("# ✦ Otaku Orbit")
        st.caption("Your personal anime command centre")
        page = st.radio("Navigate", ["Discover", "For you", "Seasonal", "Watchlist", "Statistics"], label_visibility="collapsed")
        st.divider()
        st.metric("Saved titles", len(rows))
        st.caption("Data is stored locally on this device.")
    st.markdown(f'<div class="orbit-credit">{AUTHOR_CREDIT}</div>', unsafe_allow_html=True)

    if page == "Watchlist":
        render_watchlist()
        return
    if page == "Statistics":
        render_stats(rows)
        return
    if page == "For you":
        render_recommendations(rows, saved_ids)
        return
    if page == "Discover":
        st.markdown('<div class="orbit-hero"><div class="orbit-kicker">Anime discovery, upgraded</div><h1>Find your next obsession</h1><div class="orbit-muted">Search AniList, save what catches your eye, and let your watchlist become your personal anime map.</div></div>', unsafe_allow_html=True)
        query = st.text_input("Search anime", placeholder="Try Frieren, One Piece, Cowboy Bebop…")
        if query:
            try:
                results = fetch_anime(query)
            except requests.RequestException:
                st.error("AniList is unavailable right now. Check your connection and try again.")
                results = []
            except RuntimeError as error:
                st.error(str(error))
                results = []
        else:
            st.subheader("Trending now")
            try:
                results = anilist_query(TRENDING_QUERY)
            except requests.RequestException:
                st.warning("AniList is unavailable. Search again when you are back online.")
                results = []
        results = render_filters(results, "discover")
        for anime in results:
            with st.container(border=True):
                render_card(anime, saved_ids, "discover")
    else:
        now = date.today()
        season_names = [("WINTER", "Winter"), ("SPRING", "Spring"), ("SUMMER", "Summer"), ("FALL", "Fall")]
        month = now.month
        season = "WINTER" if month in (12, 1, 2) else "SPRING" if month in (3, 4, 5) else "SUMMER" if month in (6, 7, 8) else "FALL"
        st.title(f"{season.title()} {now.year}")
        st.write("Keep up with the shows everyone will be talking about this season.")
        try:
            results = fetch_anime(season=season, year=now.year)
        except requests.RequestException:
            st.error("Could not load the seasonal lineup. Please try again shortly.")
            results = []
        results = render_filters(results, "seasonal")
        for anime in results:
            with st.container(border=True):
                render_card(anime, saved_ids, "seasonal")


if __name__ == "__main__":
    main()
