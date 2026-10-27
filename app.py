from __future__ import annotations

import csv
import io
import json
import logging
import os
import random
import sqlite3
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
import streamlit as st


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


APP_NAME = "Otaku Orbit"
APP_VERSION = "1.3.0"
APP_URL = "https://otaku-orbit.streamlit.app/"
SUPPORT_LINK = "https://discord.com/channels/@me/1252520070043668561/1562171196617785464"
AUTHOR_CREDIT = "Made by Shashank — powered by Saiyan spirit"
API_URL = os.getenv("ANILIST_API_URL", "https://graphql.anilist.co")
DB_PATH = Path(os.getenv("OTAKU_ORBIT_DB_PATH", Path(__file__).with_name("anime_companion.db")))
REQUEST_ATTEMPTS = max(1, _env_int("OTAKU_ORBIT_REQUEST_ATTEMPTS", 3))
REQUEST_TIMEOUT = max(1.0, _env_float("OTAKU_ORBIT_REQUEST_TIMEOUT", 15.0))
API_CACHE_TTL = max(60, _env_int("OTAKU_ORBIT_CACHE_TTL", 900))
WATCH_STATUSES = ["WATCHING", "PLANNING", "COMPLETED", "DROPPED"]
logger = logging.getLogger("otaku_orbit")


class AniListRateLimitError(requests.RequestException):
    """Raised when AniList asks the app to slow down."""

SEARCH_QUERY = """
query ($search: String, $season: MediaSeason, $seasonYear: Int, $page: Int, $isAdult: Boolean) {
  Page(page: $page, perPage: 24) {
    pageInfo { hasNextPage }
    media(search: $search, season: $season, seasonYear: $seasonYear, isAdult: $isAdult,
          type: ANIME, sort: POPULARITY_DESC) {
      id siteUrl title { romaji english native } coverImage { large } trailer { id site }
      description(asHtml: false) episodes duration status
      averageScore popularity genres season seasonYear format isAdult
      nextAiringEpisode { airingAt episode }
      studios(isMain: true) { nodes { name } }
    }
  }
}
"""

DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id siteUrl title { romaji english native } coverImage { large } trailer { id site }
    description(asHtml: false) episodes duration status averageScore genres
    season seasonYear format isAdult nextAiringEpisode { airingAt episode }
    studios(isMain: true) { nodes { name } }
    characters(sort: ROLE, perPage: 8) { nodes { name { full } } }
    staff(sort: RELEVANCE, perPage: 8) { nodes { name { full } primaryOccupations } }
  }
}
"""

TRENDING_QUERY = """
query { Page(page: 1, perPage: 24) {
  media(type: ANIME, sort: TRENDING_DESC) {
    id siteUrl title { romaji english native } coverImage { large } trailer { id site }
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
            episodes INTEGER, score INTEGER, genres TEXT, next_airing_at INTEGER,
            next_airing_episode INTEGER, user_score INTEGER, notes TEXT, updated_at TEXT NOT NULL
        )""")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(watchlist)")}
        if "next_airing_at" not in columns:
            connection.execute("ALTER TABLE watchlist ADD COLUMN next_airing_at INTEGER")
        if "next_airing_episode" not in columns:
            connection.execute("ALTER TABLE watchlist ADD COLUMN next_airing_episode INTEGER")
        if "user_score" not in columns:
            connection.execute("ALTER TABLE watchlist ADD COLUMN user_score INTEGER")
        if "notes" not in columns:
            connection.execute("ALTER TABLE watchlist ADD COLUMN notes TEXT")


def db_rows() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM watchlist ORDER BY updated_at DESC")]


def save_anime(anime: dict[str, Any], status: str = "PLANNING", progress: int = 0) -> None:
    title = display_title(anime)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""INSERT INTO watchlist
            (anime_id, title, image, status, progress, episodes, score, genres,
             next_airing_at, next_airing_episode, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(anime_id) DO UPDATE SET title=excluded.title, image=excluded.image,
            status=excluded.status, progress=excluded.progress, episodes=excluded.episodes,
            score=excluded.score, genres=excluded.genres, next_airing_at=excluded.next_airing_at,
            next_airing_episode=excluded.next_airing_episode, updated_at=excluded.updated_at""",
            (anime["id"], title, anime.get("coverImage", {}).get("large"), status, progress,
             anime.get("episodes"), anime.get("averageScore"), ", ".join(anime.get("genres", [])),
             (anime.get("nextAiringEpisode") or {}).get("airingAt"),
             (anime.get("nextAiringEpisode") or {}).get("episode"),
             datetime.now().isoformat(timespec="seconds")))


def update_progress(anime_id: int, progress: int, status: str, user_score: int | None = None, notes: str | None = None) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        if user_score is not None:
            connection.execute(
                "UPDATE watchlist SET progress=?, status=?, user_score=?, notes=coalesce(?, notes), updated_at=? WHERE anime_id=?",
                (progress, status, user_score, notes, datetime.now().isoformat(timespec="seconds"), anime_id),
            )
        else:
            connection.execute("UPDATE watchlist SET progress=?, status=?, notes=coalesce(?, notes), updated_at=? WHERE anime_id=?",
                           (progress, status, notes, datetime.now().isoformat(timespec="seconds"), anime_id))


def increment_watchlist_progress(anime_id: int) -> tuple[int, str]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT progress, episodes, status FROM watchlist WHERE anime_id=?", (anime_id,)).fetchone()
        if not row:
            raise ValueError(f"Anime ID {anime_id} not found in watchlist.")
        progress = int(row["progress"]) + 1
        total = row["episodes"]
        status = row["status"]
        if total and progress >= total:
            progress = total
            status = "COMPLETED"
        elif status == "PLANNING":
            status = "WATCHING"
        connection.execute(
            "UPDATE watchlist SET progress=?, status=?, updated_at=? WHERE anime_id=?",
            (progress, status, datetime.now().isoformat(timespec="seconds"), anime_id),
        )
        return progress, status


def remove_anime(anime_id: int) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM watchlist WHERE anime_id=?", (anime_id,))


def export_watchlist(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, indent=2, ensure_ascii=False)


def export_watchlist_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Anime ID", "Title", "Status", "Progress", "Episodes", "AniList Score", "User Score", "Genres", "Notes", "Updated At"])
    for row in rows:
        writer.writerow([
            row.get("anime_id"),
            row.get("title"),
            row.get("status"),
            row.get("progress"),
            row.get("episodes") or "",
            row.get("score") or "",
            row.get("user_score") or "",
            row.get("genres") or "",
            row.get("notes") or "",
            row.get("updated_at") or "",
        ])
    return output.getvalue()


def validate_backup_row(row: Any, index: int) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError(f"Backup entry {index} must be an object.")
    try:
        anime_id = int(row["anime_id"])
        title = str(row["title"]).strip()
        progress = int(row.get("progress", 0))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Backup entry {index} has invalid id, title, or progress.") from error
    if anime_id <= 0 or not title or progress < 0:
        raise ValueError(f"Backup entry {index} has invalid id, title, or progress.")
    episodes = row.get("episodes")
    if episodes is not None:
        try:
            episodes = int(episodes)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Backup entry {index} has an invalid episode count.") from error
        if episodes < 0:
            raise ValueError(f"Backup entry {index} has an invalid episode count.")
    score = row.get("score")
    if score is not None:
        try:
            score = int(score)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Backup entry {index} has an invalid score.") from error
        if not 0 <= score <= 100:
            raise ValueError(f"Backup entry {index} has an invalid score.")
    next_airing_at = row.get("next_airing_at")
    if next_airing_at is not None:
        try:
            next_airing_at = int(next_airing_at)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Backup entry {index} has an invalid airing timestamp.") from error
        if next_airing_at <= 0:
            raise ValueError(f"Backup entry {index} has an invalid airing timestamp.")
    next_airing_episode = row.get("next_airing_episode")
    if next_airing_episode is not None:
        try:
            next_airing_episode = int(next_airing_episode)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Backup entry {index} has an invalid airing episode.") from error
        if next_airing_episode <= 0:
            raise ValueError(f"Backup entry {index} has an invalid airing episode.")
    user_score = row.get("user_score")
    if user_score is not None:
        try:
            user_score = int(user_score)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Backup entry {index} has an invalid personal user score.") from error
        if not 0 <= user_score <= 100:
            raise ValueError(f"Backup entry {index} has an invalid personal user score.")
    return {
        "anime_id": anime_id,
        "title": title,
        "image": row.get("image"),
        "status": row.get("status", "PLANNING") if row.get("status") in WATCH_STATUSES else "PLANNING",
        "progress": progress,
        "episodes": episodes,
        "score": score,
        "genres": str(row.get("genres", "")),
        "next_airing_at": next_airing_at,
        "next_airing_episode": next_airing_episode,
        "user_score": user_score,
        "notes": str(row.get("notes") or "").strip(),
        "updated_at": row.get("updated_at", datetime.now().isoformat(timespec="seconds")),
    }


def import_watchlist(payload: str) -> int:
    if len(payload.encode("utf-8")) > 2_000_000:
        raise ValueError("That backup is larger than the 2 MB safety limit.")
    imported = json.loads(payload)
    if not isinstance(imported, list):
        raise ValueError("A watchlist backup must contain a list of titles.")
    restored = 0
    with sqlite3.connect(DB_PATH) as connection:
        for index, raw_row in enumerate(imported, start=1):
            row = validate_backup_row(raw_row, index)
            connection.execute("""INSERT INTO watchlist
                (anime_id, title, image, status, progress, episodes, score, genres,
                 next_airing_at, next_airing_episode, user_score, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(anime_id) DO UPDATE SET title=excluded.title, image=excluded.image,
                status=excluded.status, progress=excluded.progress, episodes=excluded.episodes,
                score=excluded.score, genres=excluded.genres, next_airing_at=excluded.next_airing_at,
                next_airing_episode=excluded.next_airing_episode, user_score=coalesce(excluded.user_score, watchlist.user_score), notes=coalesce(excluded.notes, watchlist.notes), updated_at=excluded.updated_at""",
                (row["anime_id"], row["title"], row["image"], row["status"], row["progress"],
                 row["episodes"], row["score"], row["genres"], row["next_airing_at"],
                 row["next_airing_episode"], row["user_score"], row.get("notes", ""), row["updated_at"]))
            restored += 1
    return restored


@st.cache_data(ttl=API_CACHE_TTL, show_spinner=False)
def anilist_response(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    request_body = {"query": query, "variables": variables or {}}
    response: requests.Response | None = None
    for attempt in range(REQUEST_ATTEMPTS):
        try:
            response = requests.post(API_URL, json=request_body,
                                     headers={"User-Agent": f"OtakuOrbit/{APP_VERSION}"}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            break
        except requests.RequestException as error:
            status_code = getattr(response, "status_code", None)
            if status_code == 429:
                logger.warning("AniList rate limit reached on attempt %s", attempt + 1)
                raise AniListRateLimitError(
                    "AniList is rate-limiting requests. Please wait a minute and try again."
                ) from error
            retryable_status = status_code is None or status_code == 429 or status_code >= 500
            if attempt == REQUEST_ATTEMPTS - 1 or not retryable_status:
                logger.error("AniList request failed after %s attempt(s): %s", attempt + 1, error)
                raise
            logger.info("Retrying AniList request after transient failure: attempt %s", attempt + 2)
            time.sleep(0.35 * (2 ** attempt))
    if response is None:
        raise requests.RequestException("AniList did not return a response")
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "AniList returned an error"))
    return payload.get("data", {})


def anilist_query(query: str, variables: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = anilist_response(query, variables)
    if data.get("Media"):
        return [data["Media"]]
    return data.get("Page", {}).get("media", [])


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_anime_detail(anime_id: int) -> dict[str, Any] | None:
    payload = anilist_query(DETAIL_QUERY, {"id": anime_id})
    return payload[0] if payload else None


def current_season_and_year(today: date | None = None) -> tuple[str, int]:
    today = today or date.today()
    month = today.month
    season = "WINTER" if month in (12, 1, 2) else "SPRING" if month in (3, 4, 5) else "SUMMER" if month in (6, 7, 8) else "FALL"
    return season, today.year


def fetch_anime(search: str = "", season: str | None = None, year: int | None = None,
                page: int = 1, is_adult: bool | None = False) -> list[dict[str, Any]]:
    results, _ = fetch_anime_page(search, season, year, page, is_adult=is_adult)
    return results


def fetch_anime_page(search: str = "", season: str | None = None, year: int | None = None,
                     page: int = 1, is_adult: bool | None = False) -> tuple[list[dict[str, Any]], bool]:
    variables: dict[str, Any] = {"search": search or None, "page": page, "isAdult": is_adult if is_adult is not None else False}
    if season:
        variables["season"], variables["seasonYear"] = season, year
    data = anilist_response(SEARCH_QUERY, variables)
    page_data = data.get("Page", {})
    return page_data.get("media", []), bool(page_data.get("pageInfo", {}).get("hasNextPage"))


def load_with_fallback(cache_key: str, loader: Callable[[], Any]) -> tuple[Any, bool]:
    """Load remote data and fall back to this session's last successful result."""
    offline_cache = st.session_state.setdefault("offline_cache", {})
    try:
        result = loader()
    except (requests.RequestException, RuntimeError):
        if cache_key not in offline_cache:
            raise
        logger.warning("Using cached result for %s after a remote request failed", cache_key)
        return offline_cache[cache_key], True
    offline_cache[cache_key] = result
    return result, False


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


def calculate_runtime_display(episodes: int | None, duration_mins: int | None = None, progress: int = 0) -> str:
    if not episodes or episodes <= 0:
        return "Runtime unknown"
    duration = duration_mins if duration_mins and duration_mins > 0 else 24
    total_minutes = episodes * duration
    hours = total_minutes // 60
    mins = total_minutes % 60
    runtime_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    if 0 < progress < episodes:
        remaining_minutes = max(0, (episodes - progress) * duration)
        rem_hours = remaining_minutes // 60
        rem_mins = remaining_minutes % 60
        rem_str = f"{rem_hours}h {rem_mins}m" if rem_hours > 0 else f"{rem_mins}m"
        return f"{runtime_str} total ({rem_str} left)"
    return f"{runtime_str} total"


def format_airing(anime: dict[str, Any]) -> str:
    airing = anime.get("nextAiringEpisode")
    if not airing:
        return "No upcoming episode"
    try:
        airing_at = int(airing["airingAt"])
        episode = int(airing["episode"])
        if airing_at <= 0 or episode <= 0:
            return "No upcoming episode"
        when = datetime.fromtimestamp(airing_at).strftime("%d %b, %H:%M")
    except (KeyError, TypeError, ValueError, OSError, OverflowError):
        return "No upcoming episode"
    return f"Episode {episode} · {when}"


def format_row_airing(row: dict[str, Any]) -> str | None:
    if not row.get("next_airing_at"):
        return None
    try:
        airing_at = int(row["next_airing_at"])
        if airing_at <= 0:
            return None
        when = datetime.fromtimestamp(airing_at).strftime("%d %b, %H:%M")
    except (KeyError, TypeError, ValueError, OSError, OverflowError):
        return None
    episode = row.get("next_airing_episode", "?")
    try:
        episode = int(episode)
        if episode <= 0:
            episode = "?"
    except (TypeError, ValueError):
        episode = "?"
    return f"Episode {episode} · {when}"


def format_trailer_url(trailer: dict[str, Any] | None) -> str | None:
    if not trailer or not isinstance(trailer, dict):
        return None
    site = str(trailer.get("site", "")).lower()
    trailer_id = trailer.get("id")
    if site == "youtube" and trailer_id:
        return f"https://www.youtube.com/watch?v={trailer_id}"
    return None


@st.dialog("Anime details")
def show_anime_details(anime_id: int) -> None:
    try:
        anime = fetch_anime_detail(anime_id)
    except (requests.RequestException, RuntimeError) as error:
        st.error(f"Could not load details: {error}")
        return
    if not anime:
        st.info("No details were found for this title.")
        return
    st.subheader(display_title(anime))
    if anime.get("coverImage", {}).get("large"):
        st.image(anime["coverImage"]["large"], width=220)
    st.caption(f"{anime.get('format', 'ANIME')} · {anime.get('status', 'UNKNOWN')} · {anime.get('averageScore') or '—'}/100")
    st.write(clean_description(anime.get("description")))
    st.write(f"**Episodes:** {anime.get('episodes') or 'Unknown'} · **Duration:** {anime.get('duration') or 'Unknown'} min · **Est. watch time:** {calculate_runtime_display(anime.get('episodes'), anime.get('duration'))}")
    studios = [studio["name"] for studio in anime.get("studios", {}).get("nodes", [])]
    if studios:
        st.write("**Studio:** " + ", ".join(studios))
    characters = [item["name"]["full"] for item in anime.get("characters", {}).get("nodes", [])]
    if characters:
        st.caption("Characters: " + ", ".join(characters))
    staff = [item["name"]["full"] for item in anime.get("staff", {}).get("nodes", [])]
    if staff:
        st.caption("Staff: " + ", ".join(staff))
    site_url = anime.get("siteUrl") or f"https://anilist.co/anime/{anime_id}"
    trailer_url = format_trailer_url(anime.get("trailer"))
    btn_cols = st.columns(2 if trailer_url else 1)
    btn_cols[0].link_button("View on AniList", site_url, use_container_width=True)
    if trailer_url:
        btn_cols[1].link_button("Watch Trailer", trailer_url, use_container_width=True)


def render_card(anime: dict[str, Any], saved_ids: set[int], key_prefix: str) -> None:
    title = display_title(anime)
    compact = st.session_state.get("compact_cards", False)
    image, details = st.columns([0.7, 2.5] if compact else [1, 2.2], gap="medium")
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
        if st.button(f"Details: {title}", key=f"details-{key_prefix}-{anime['id']}",
                     help=f"Open full details for {title}", use_container_width=True):
            show_anime_details(anime["id"])
        if anime["id"] in saved_ids:
            st.success("In your watchlist")
        else:
            if st.button(f"Add {title} to watchlist", key=f"add-{key_prefix}-{anime['id']}",
                         help=f"Save {title} to your watchlist", use_container_width=True):
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
    sort_order = st.selectbox("Sort saved titles", ["Recently updated", "Title", "Score", "Progress"],
                              key="watchlist-sort")
    if sort_order == "Recently updated":
        rows.sort(key=lambda row: row.get("updated_at") or "", reverse=True)
    elif sort_order == "Title":
        rows.sort(key=lambda row: row["title"].lower())
    elif sort_order == "Score":
        rows.sort(key=lambda row: row["score"] or 0, reverse=True)
    elif sort_order == "Progress":
        rows.sort(key=lambda row: row["progress"], reverse=True)
    active = [row for row in rows if row["status"] == "WATCHING"]
    goal = st.session_state.get("daily_goal", 3)
    if active:
        st.subheader("Continue watching")
        st.caption(f"Your next episodes are always at the top of the orbit. Goal: {goal} episode(s) per day.")
        for row in active[:3]:
            total = row["episodes"] or 0
            progress = row["progress"]
            remaining = max(total - progress, 0) if total else "?"
            st.write(f"**{row['title']}** · episode {progress + 1} next · {remaining} remaining")
        st.divider()
    reminders = [(row["title"], format_row_airing(row)) for row in rows if format_row_airing(row)]
    if reminders:
        st.subheader("Upcoming airing reminders")
        for title, airing in reminders[:5]:
            st.info(f"**{title}** · {airing}")
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
            user_score_display = f"{row['user_score']}/100" if row.get("user_score") else "Not rated"
            time_left = calculate_runtime_display(row["episodes"], 24, progress=progress)
            st.caption(f"AniList: {row['score'] or '—'}  ·  My score: {user_score_display}  ·  {time_left}  ·  {row['genres'] or 'Genre unknown'}")
            if row.get("notes"):
                st.caption(f"Notes: {row['notes']}")
        with right:
            status = st.selectbox("Status", WATCH_STATUSES,
                                  index=WATCH_STATUSES.index(row["status"]),
                                  key=f"status-{row['anime_id']}")
            new_progress = st.number_input("Episodes watched", min_value=0, max_value=row["episodes"] or 9999,
                                           value=row["progress"], key=f"progress-{row['anime_id']}")
            my_score = st.number_input("My rating (0-100)", min_value=0, max_value=100,
                                       value=int(row.get("user_score") or 0), key=f"userscore-{row['anime_id']}")
            notes_val = st.text_input("Notes", value=row.get("notes") or "", placeholder="Thoughts, reviews…", key=f"notes-{row['anime_id']}")
            a, b, c = st.columns([1, 1, 1])
            if a.button("+1 Ep", key=f"inc-{row['anime_id']}", use_container_width=True):
                increment_watchlist_progress(row["anime_id"])
                st.rerun()
            if b.button("Save", key=f"save-{row['anime_id']}", use_container_width=True):
                update_progress(row["anime_id"], int(new_progress), status, user_score=int(my_score) if my_score > 0 else None, notes=notes_val.strip())
                st.rerun()
            if c.button("Remove", key=f"remove-{row['anime_id']}", use_container_width=True):
                remove_anime(row["anime_id"])
                st.rerun()
        st.divider()
    if not visible_rows:
        st.info("No saved titles match those filters.")
    with st.expander("Backup your watchlist"):
        st.caption("Export a portable backup or restore one on another device.")
        d_col1, d_col2 = st.columns(2)
        d_col1.download_button("Download JSON", export_watchlist(rows), "otaku-orbit-watchlist.json", "application/json", use_container_width=True)
        d_col2.download_button("Download CSV", export_watchlist_csv(rows), "otaku-orbit-watchlist.csv", "text/csv", use_container_width=True)


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
    except (requests.RequestException, RuntimeError) as error:
        st.error(f"Could not load recommendations right now: {error}")
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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    st.set_page_config(page_title=APP_NAME, page_icon="O", layout="wide", initial_sidebar_state="expanded")
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
    @media (max-width: 768px) {
        .block-container {padding: 1rem .75rem 4rem;}
        .orbit-hero {padding: 1rem; border-radius: 16px;}
        .orbit-hero h1 {font-size: 2rem; line-height: 1.1;}
        .orbit-credit {font-size: .68rem; padding: 0 .5rem;}
    }
    </style>""", unsafe_allow_html=True)
    rows = db_rows()
    saved_ids = {row["anime_id"] for row in rows}
    with st.sidebar:
        st.markdown("# Otaku Orbit")
        st.caption(f"Your personal anime command centre | v{APP_VERSION}")
        st.link_button("Open live app", APP_URL, use_container_width=True)
        st.link_button("Open community support", SUPPORT_LINK, use_container_width=True)
        page = st.radio("Navigate", ["Discover", "For you", "Seasonal", "Watchlist", "Statistics"], label_visibility="collapsed")
        st.divider()
        st.metric("Saved titles", len(rows))
        st.session_state["daily_goal"] = st.number_input("Daily episode goal", min_value=1, max_value=20,
                                                           value=st.session_state.get("daily_goal", 3))
        st.session_state["compact_cards"] = st.toggle("Compact cards", value=st.session_state.get("compact_cards", False))
        with st.expander("System status"):
            st.caption(f"AniList endpoint: {API_URL}")
            st.caption(f"Request cache: {API_CACHE_TTL} seconds")
            st.caption(f"Local database: {DB_PATH.name}")
            st.caption("Storage mode: local SQLite")
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
        query = st.text_input("Search anime", placeholder="Try Frieren, One Piece, or Cowboy Bebop")
        if query:
            search_state = st.session_state.setdefault("discover_search", {
                "query": "", "results": [], "page": 0, "has_next": True,
            })
            if search_state["query"] != query:
                search_state.update({"query": query, "results": [], "page": 0, "has_next": True})
            try:
                if not search_state["results"]:
                    (first_page, has_next), from_cache = load_with_fallback(
                        f"search:{query}:1", lambda: fetch_anime_page(query, page=1)
                    )
                    search_state.update({"results": first_page, "page": 1, "has_next": has_next})
                    if from_cache:
                        st.info("Showing cached results because AniList is currently unavailable.")
                results = search_state["results"]
                if search_state["has_next"] and st.button("Load more results",
                                                           help="Fetch the next page of search results"):
                    next_page = search_state["page"] + 1
                    (next_results, has_next), _ = load_with_fallback(
                        f"search:{query}:{next_page}", lambda: fetch_anime_page(query, page=next_page)
                    )
                    search_state["results"] = [*search_state["results"], *next_results]
                    search_state.update({"page": next_page, "has_next": has_next})
                    st.rerun()
            except requests.RequestException as error:
                st.error(str(error))
                results = []
            except RuntimeError as error:
                st.error(str(error))
                results = []
        else:
            st.subheader("Trending now")
            try:
                results, from_cache = load_with_fallback("trending", lambda: anilist_query(TRENDING_QUERY))
                if from_cache:
                    st.info("AniList is unavailable, so these are your cached trending results.")
            except (requests.RequestException, RuntimeError) as error:
                st.warning(f"AniList is unavailable and no cached trending results exist yet: {error}")
                results = []
        if st.button("Surprise me", help="Show one random title from the current results") and results:
            results = [random.choice(results)]
            st.info("A random pick from the anime universe.")
        results = render_filters(results, "discover")
        for anime in results:
            with st.container(border=True):
                render_card(anime, saved_ids, "discover")
    else:
        curr_season, curr_year = current_season_and_year()
        season_cols = st.columns([1, 1, 2])
        season_names = ["WINTER", "SPRING", "SUMMER", "FALL"]
        season = season_cols[0].selectbox("Season", season_names, index=season_names.index(curr_season), key="seasonal-season")
        years = list(range(curr_year + 1, curr_year - 6, -1))
        year = season_cols[1].selectbox("Year", years, index=years.index(curr_year) if curr_year in years else 1, key="seasonal-year")
        st.title(f"{season.title()} {year}")
        st.write(f"Explore the anime lineup for {season.title()} {year}.")
        try:
            results = fetch_anime(season=season, year=year)
        except (requests.RequestException, RuntimeError) as error:
            st.error(f"Could not load the seasonal lineup: {error}")
            results = []
        results = render_filters(results, "seasonal")
        for anime in results:
            with st.container(border=True):
                render_card(anime, saved_ids, "seasonal")


if __name__ == "__main__":
    main()
