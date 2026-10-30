from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import logging
import math
import os
import random
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def offline_mode_enabled() -> bool:
    return os.getenv("OTAKU_ORBIT_OFFLINE_MODE", "").strip().lower() in {"1", "true", "yes"}


APP_NAME = "Otaku Orbit"
APP_VERSION = "1.6.0"
APP_URL = "https://otaku-orbit.streamlit.app/"
SUPPORT_LINK = "https://discord.com/channels/@me/1252520070043668561/1562171196617785464"
AUTHOR_CREDIT = "Made by Shashank — powered by Saiyan spirit"
API_URL = os.getenv("ANILIST_API_URL", "https://graphql.anilist.co")
DB_PATH = Path(os.getenv("OTAKU_ORBIT_DB_PATH", Path(__file__).with_name("anime_companion.db")))
REQUEST_ATTEMPTS = max(1, _env_int("OTAKU_ORBIT_REQUEST_ATTEMPTS", 3))
REQUEST_TIMEOUT = max(1.0, _env_float("OTAKU_ORBIT_REQUEST_TIMEOUT", 15.0))
API_CACHE_TTL = max(60, _env_int("OTAKU_ORBIT_CACHE_TTL", 900))
WATCH_STATUSES = ["WATCHING", "REWATCHING", "PLANNING", "COMPLETED", "DROPPED"]
MANGA_STATUSES = ["READING", "REREADING", "PLAN_TO_READ", "COMPLETED", "DROPPED"]
BACKUP_FORMAT_VERSION = 1
SUPPORTED_TIMEZONES = ["UTC", "Asia/Kolkata", "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]
THEME_PALETTES = {
    "Saiyan Neon": {
        "primary": "#f4b8ff",
        "glow": "rgba(111,76,255,.32)",
        "metric": "#f4b8ff",
        "sidebar": "linear-gradient(180deg, #17132a 0%, #0e1020 100%)",
    },
    "Cyberpunk Cyan": {
        "primary": "#00f0ff",
        "glow": "rgba(0,180,255,.32)",
        "metric": "#00f0ff",
        "sidebar": "linear-gradient(180deg, #101c2e 0%, #0a0e17 100%)",
    },
    "Sunset Flame": {
        "primary": "#ff8447",
        "glow": "rgba(255,46,147,.32)",
        "metric": "#ff8447",
        "sidebar": "linear-gradient(180deg, #24111e 0%, #140a12 100%)",
    },
    "Emerald Matrix": {
        "primary": "#00ff88",
        "glow": "rgba(0,255,136,.32)",
        "metric": "#00ff88",
        "sidebar": "linear-gradient(180deg, #102419 0%, #0a140f 100%)",
    },
}

ACHIEVEMENTS = [
    {"id": "first_step", "title": "First Step", "desc": "Add your first anime to your library", "icon": "🌱"},
    {"id": "rookie", "title": "Rookie Explorer", "desc": "Complete your first anime series", "icon": "🥉"},
    {"id": "centurion", "title": "Otaku Centurion", "desc": "Watch 100 or more total episodes", "icon": "🥇"},
    {"id": "binge_demon", "title": "Binge Sprinter", "desc": "Log 5 or more episodes in a single day", "icon": "⚡"},
    {"id": "time_leaper", "title": "Time Leaper", "desc": "Log at least 1 rewatch cycle", "icon": "🔁"},
    {"id": "critic", "title": "Elite Critic", "desc": "Rate 5 or more anime with personal scores", "icon": "🌟"},
    {"id": "polymath", "title": "Genre Polymath", "desc": "Explore 5 or more distinct anime genres", "icon": "🧭"},
    {"id": "archivist", "title": "Archivist", "desc": "Organize your collection with custom tags", "icon": "🏷️"},
]

logger = logging.getLogger("otaku_orbit")
_http_thread_state = threading.local()


class AniListRateLimitError(requests.RequestException):
    """Raised when AniList asks the app to slow down."""


def _request_session() -> requests.Session:
    session = getattr(_http_thread_state, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": f"OtakuOrbit/{APP_VERSION}"})
        _http_thread_state.session = session
    return session


def authentication_configured() -> bool:
    try:
        return bool(st.secrets.get("auth"))
    except Exception:
        return False


def current_owner_id() -> str | None:
    """Return a stable OIDC owner ID or a random per-session guest ID."""
    if authentication_configured():
        user = st.user
        if not getattr(user, "is_logged_in", False):
            return None
        subject = user.get("sub") or user.get("email")
        if not subject:
            return None
        issuer = user.get("iss", "")
        digest = hashlib.sha256(f"{issuer}:{subject}".encode("utf-8")).hexdigest()
        return f"account-{digest}"
    session_id = st.session_state.setdefault("_otaku_orbit_session_id", uuid.uuid4().hex)
    return f"guest-{session_id}"


def database_path_for_owner(owner_id: str | None = None) -> Path:
    if owner_id is None:
        return DB_PATH
    digest = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:24]
    return DB_PATH.with_name(f"{DB_PATH.stem}.{digest}{DB_PATH.suffix}")


def delete_owner_data(owner_id: str) -> None:
    path = database_path_for_owner(owner_id)
    if path.exists():
        connection = sqlite3.connect(path, timeout=15)
        try:
            connection.execute("DELETE FROM watchlist")
            connection.execute("DELETE FROM watch_history")
            connection.commit()
            connection.execute("VACUUM")
        finally:
            connection.close()


SEARCH_QUERY = """
query ($search: String, $season: MediaSeason, $seasonYear: Int, $page: Int, $isAdult: Boolean, $type: MediaType) {
  Page(page: $page, perPage: 24) {
    pageInfo { hasNextPage }
    media(search: $search, season: $season, seasonYear: $seasonYear, isAdult: $isAdult,
          type: $type, sort: POPULARITY_DESC) {
      id siteUrl title { romaji english native } coverImage { extraLarge large } bannerImage trailer { id site }
      description(asHtml: false) episodes chapters volumes duration status
      averageScore popularity genres season seasonYear format isAdult source
      nextAiringEpisode { airingAt episode }
      studios(isMain: true) { nodes { name } }
    }
  }
}
"""

DETAIL_QUERY = """
query ($id: Int, $type: MediaType) {
  Media(id: $id, type: $type) {
    id siteUrl title { romaji english native } coverImage { extraLarge large } bannerImage trailer { id site }
    description(asHtml: false) episodes chapters volumes duration status averageScore genres
    season seasonYear format isAdult source nextAiringEpisode { airingAt episode }
    studios(isMain: true) { nodes { name } }
    externalLinks { id site url type icon color }
    streamingEpisodes { title thumbnail url site }
    characters(sort: ROLE, perPage: 6) {
      edges {
        role
        node { id name { full native } image { large medium } }
        voiceActors(language: JAPANESE, sort: RELEVANCE) { id name { full native } image { large medium } languageV2 }
      }
      nodes { name { full } }
    }
    staff(sort: RELEVANCE, perPage: 8) { nodes { name { full } primaryOccupations } }
    relations {
      edges {
        relationType(version: 2)
        node {
          id
          title { romaji english native }
          format
          status
          coverImage { extraLarge large }
        }
      }
    }
    recommendations(sort: RATING_DESC, perPage: 6) {
      nodes {
        mediaRecommendation {
          id
          title { romaji english native }
          coverImage { extraLarge large }
          averageScore
          format
        }
      }
    }
  }
}
"""

TRENDING_QUERY = """
query ($type: MediaType) { Page(page: 1, perPage: 24) {
  media(type: $type, sort: TRENDING_DESC) {
    id siteUrl title { romaji english native } coverImage { extraLarge large } bannerImage trailer { id site }
    description(asHtml: false) episodes chapters volumes duration status averageScore popularity genres
    season seasonYear format isAdult source nextAiringEpisode { airingAt episode }
    studios(isMain: true) { nodes { name } }
  }
} }
"""

AIRING_SCHEDULE_QUERY = """
query ($airingAt_greater: Int, $airingAt_lesser: Int) {
  Page(page: 1, perPage: 50) {
    airingSchedules(airingAt_greater: $airingAt_greater, airingAt_lesser: $airingAt_lesser, sort: TIME) {
      id
      airingAt
      episode
      media {
        id siteUrl title { romaji english native } coverImage { extraLarge large } bannerImage trailer { id site }
        description(asHtml: false) episodes chapters volumes duration status averageScore popularity genres format isAdult source
      }
    }
  }
}
"""


def init_db(owner_id: str | None = None) -> None:
    database_path = database_path_for_owner(owner_id)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path, timeout=15) as connection:
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("""CREATE TABLE IF NOT EXISTS watchlist (
            anime_id INTEGER PRIMARY KEY, title TEXT NOT NULL, image TEXT,
            status TEXT NOT NULL DEFAULT 'PLANNING', progress INTEGER NOT NULL DEFAULT 0,
            episodes INTEGER, duration INTEGER, score INTEGER, genres TEXT, next_airing_at INTEGER,
            next_airing_episode INTEGER, user_score INTEGER, notes TEXT, updated_at TEXT NOT NULL,
            rewatches INTEGER NOT NULL DEFAULT 0, tags TEXT DEFAULT '', banner_image TEXT,
            media_type TEXT DEFAULT 'ANIME', chapters INTEGER, volumes INTEGER
        )""")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(watchlist)")}
        for col_name, col_type in [
            ("next_airing_at", "INTEGER"),
            ("next_airing_episode", "INTEGER"),
            ("user_score", "INTEGER"),
            ("notes", "TEXT"),
            ("duration", "INTEGER"),
            ("rewatches", "INTEGER NOT NULL DEFAULT 0"),
            ("tags", "TEXT DEFAULT ''"),
            ("banner_image", "TEXT"),
            ("media_type", "TEXT DEFAULT 'ANIME'"),
            ("chapters", "INTEGER"),
            ("volumes", "INTEGER"),
        ]:
            if col_name not in columns:
                connection.execute(f"ALTER TABLE watchlist ADD COLUMN {col_name} {col_type}")  # nosec B608
        connection.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_status ON watchlist(status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_updated ON watchlist(updated_at DESC)")

        connection.execute("""CREATE TABLE IF NOT EXISTS watch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            episode INTEGER NOT NULL,
            watched_at TEXT NOT NULL
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_watch_history_date ON watch_history(watched_at DESC)")


def db_rows(owner_id: str | None = None) -> list[dict[str, Any]]:
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM watchlist ORDER BY updated_at DESC")]


def record_watch_history(
    anime_id: int,
    title: str,
    episode: int,
    owner_id: str | None = None,
    watched_at: str | None = None,
) -> None:
    timestamp = watched_at or datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        connection.execute(
            "INSERT INTO watch_history (anime_id, title, episode, watched_at) VALUES (?, ?, ?, ?)",
            (anime_id, title, episode, timestamp),
        )


def fetch_watch_history(days: int = 60, owner_id: str | None = None) -> list[dict[str, Any]]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        connection.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM watch_history WHERE watched_at >= ? ORDER BY watched_at DESC",
                (cutoff,),
            )
        ]


def calculate_watch_streak(history: list[dict[str, Any]]) -> int:
    if not history:
        return 0
    active_dates = sorted(
        {r["watched_at"][:10] for r in history if r.get("watched_at")},
        reverse=True,
    )
    if not active_dates:
        return 0
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if active_dates[0] not in (today, yesterday):
        return 0
    streak = 1
    curr = datetime.fromisoformat(active_dates[0]).date()
    for d_str in active_dates[1:]:
        prev = datetime.fromisoformat(d_str).date()
        diff = (curr - prev).days
        if diff == 1:
            streak += 1
            curr = prev
        elif diff == 0:
            continue
        else:
            break
    return streak


def calculate_watch_velocity(history: list[dict[str, Any]]) -> float:
    if not history:
        return 1.5
    active_days = len({r["watched_at"][:10] for r in history if r.get("watched_at")})
    return max(0.5, round(len(history) / max(1, active_days), 1))


def estimate_completion_date(remaining_episodes: int, velocity: float) -> str | None:
    if remaining_episodes <= 0 or velocity <= 0:
        return None
    days_needed = math.ceil(remaining_episodes / velocity)
    target = date.today() + timedelta(days=days_needed)
    return target.strftime("%d %b %Y")


def evaluate_achievements(rows: list[dict[str, Any]], history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_eps = sum(r.get("progress", 0) for r in rows)
    completed_count = sum(r.get("status") == "COMPLETED" for r in rows)
    rewatch_count = sum((r.get("rewatches") or 0) > 0 or r.get("status") == "REWATCHING" for r in rows)
    rated_count = sum(bool(r.get("user_score")) for r in rows)
    distinct_genres = len({g.strip() for r in rows for g in (r.get("genres") or "").split(",") if g.strip()})
    tagged_count = sum(bool((r.get("tags") or "").strip()) for r in rows)

    counts_by_day: dict[str, int] = {}
    for h in history:
        day = h.get("watched_at", "")[:10]
        if day:
            counts_by_day[day] = counts_by_day.get(day, 0) + 1
    max_day_eps = max(counts_by_day.values()) if counts_by_day else 0

    status_map = {
        "first_step": len(rows) >= 1,
        "rookie": completed_count >= 1,
        "centurion": total_eps >= 100,
        "binge_demon": max_day_eps >= 5,
        "time_leaper": rewatch_count >= 1,
        "critic": rated_count >= 5,
        "polymath": distinct_genres >= 5,
        "archivist": tagged_count >= 1,
    }

    return [{**ach, "unlocked": status_map.get(ach["id"], False)} for ach in ACHIEVEMENTS]


def cover_image_url(anime: dict[str, Any]) -> str | None:
    """Prefer AniList's largest cover rendition and fall back to its large rendition."""
    cover = anime.get("coverImage")
    if not isinstance(cover, dict):
        return None
    url = cover.get("extraLarge") or cover.get("large") or cover.get("medium")
    return url if is_safe_cover_url(url) else None


def banner_image_url(anime: dict[str, Any]) -> str | None:
    url = anime.get("bannerImage")
    return url if is_safe_cover_url(url) else None


def is_safe_cover_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and bool(re.fullmatch(r"s[1-4]\.anilist\.co", parsed.hostname, re.IGNORECASE))
    )


def validate_watchlist_state(
    progress: int,
    status: str,
    episodes: int | None,
    user_score: int | None = None,
    rewatches: int = 0,
) -> None:
    valid_statuses = set(WATCH_STATUSES).union(MANGA_STATUSES)
    if status not in valid_statuses:
        raise ValueError("Choose a valid watch status.")
    if progress < 0 or (episodes is not None and episodes > 0 and progress > episodes):
        raise ValueError("Episode progress must be between zero and the known episode count.")
    if user_score is not None and not 0 <= user_score <= 100:
        raise ValueError("Your score must be between 0 and 100.")
    if rewatches < 0:
        raise ValueError("Rewatch count cannot be negative.")


def save_anime(
    anime: dict[str, Any],
    status: str = "PLANNING",
    progress: int = 0,
    owner_id: str | None = None,
    rewatches: int = 0,
    tags: str = "",
    media_type: str = "ANIME",
) -> None:
    title = display_title(anime)
    episodes = anime.get("episodes") or anime.get("chapters")
    validate_watchlist_state(progress, status, episodes, rewatches=rewatches)
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        connection.execute(
            """INSERT INTO watchlist
            (anime_id, title, image, status, progress, episodes, duration, score, genres,
             next_airing_at, next_airing_episode, rewatches, tags, banner_image, media_type,
             chapters, volumes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(anime_id) DO UPDATE SET title=excluded.title, image=excluded.image,
            status=excluded.status, progress=excluded.progress, episodes=excluded.episodes, duration=excluded.duration,
            score=excluded.score, genres=excluded.genres, next_airing_at=excluded.next_airing_at,
            next_airing_episode=excluded.next_airing_episode, rewatches=excluded.rewatches, tags=excluded.tags,
            banner_image=excluded.banner_image, media_type=excluded.media_type, chapters=excluded.chapters,
            volumes=excluded.volumes, updated_at=excluded.updated_at""",
            (
                anime["id"],
                title,
                cover_image_url(anime),
                status,
                progress,
                episodes,
                anime.get("duration"),
                anime.get("averageScore"),
                ", ".join(anime.get("genres", [])),
                (anime.get("nextAiringEpisode") or {}).get("airingAt"),
                (anime.get("nextAiringEpisode") or {}).get("episode"),
                rewatches,
                tags,
                banner_image_url(anime),
                media_type,
                anime.get("chapters"),
                anime.get("volumes"),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def update_progress(
    anime_id: int,
    progress: int,
    status: str,
    user_score: int | None = None,
    notes: str | None = None,
    rewatches: int | None = None,
    tags: str | None = None,
    owner_id: str | None = None,
) -> None:
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        row = connection.execute(
            "SELECT episodes, rewatches, progress, title FROM watchlist WHERE anime_id=?", (anime_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Anime ID {anime_id} not found in watchlist.")
        current_rewatches = row[1] if row[1] is not None else 0
        old_progress = row[2] if row[2] is not None else 0
        title = row[3] or "Anime"
        validate_watchlist_state(
            progress, status, row[0], user_score, rewatches=rewatches if rewatches is not None else current_rewatches
        )
        if notes is not None and len(notes) > 5000:
            raise ValueError("Notes must be 5,000 characters or fewer.")
        if tags is not None and len(tags) > 500:
            raise ValueError("Tags must be 500 characters or fewer.")
        now_ts = datetime.now().isoformat(timespec="seconds")
        set_clauses = ["progress=?", "status=?", "notes=coalesce(?, notes)", "updated_at=?"]
        params: list[Any] = [progress, status, notes, now_ts]
        if user_score is not None:
            set_clauses.append("user_score=?")
            params.append(user_score)
        if rewatches is not None:
            set_clauses.append("rewatches=?")
            params.append(rewatches)
        if tags is not None:
            set_clauses.append("tags=?")
            params.append(tags)
        params.append(anime_id)
        connection.execute(f"UPDATE watchlist SET {', '.join(set_clauses)} WHERE anime_id=?", params)  # nosec B608

        if progress > old_progress:
            connection.execute(
                "INSERT INTO watch_history (anime_id, title, episode, watched_at) VALUES (?, ?, ?, ?)",
                (anime_id, title, progress, now_ts),
            )


def batch_update_status(anime_ids: list[int], status: str, owner_id: str | None = None) -> None:
    if not anime_ids or status not in WATCH_STATUSES:
        return
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        now = datetime.now().isoformat(timespec="seconds")
        placeholders = ",".join("?" * len(anime_ids))
        connection.execute(
            f"UPDATE watchlist SET status=?, updated_at=? WHERE anime_id IN ({placeholders})",  # nosec B608
            [status, now, *anime_ids],
        )


def batch_remove_anime(anime_ids: list[int], owner_id: str | None = None) -> None:
    if not anime_ids:
        return
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        placeholders = ",".join("?" * len(anime_ids))
        connection.execute(f"DELETE FROM watchlist WHERE anime_id IN ({placeholders})", anime_ids)  # nosec B608


def batch_add_tag(anime_ids: list[int], tag: str, owner_id: str | None = None) -> None:
    clean_tag = tag.strip().replace(",", "")
    if not anime_ids or not clean_tag:
        return
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        connection.row_factory = sqlite3.Row
        placeholders = ",".join("?" * len(anime_ids))
        rows = connection.execute(
            f"SELECT anime_id, tags FROM watchlist WHERE anime_id IN ({placeholders})",  # nosec B608
            anime_ids,
        ).fetchall()
        now = datetime.now().isoformat(timespec="seconds")
        for row in rows:
            existing = {t.strip() for t in (row["tags"] or "").split(",") if t.strip()}
            existing.add(clean_tag)
            updated_tags = ", ".join(sorted(existing))
            connection.execute(
                "UPDATE watchlist SET tags=?, updated_at=? WHERE anime_id=?",
                (updated_tags, now, row["anime_id"]),
            )


def increment_watchlist_progress(anime_id: int, owner_id: str | None = None) -> tuple[int, str]:
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT progress, episodes, status, title FROM watchlist WHERE anime_id=?", (anime_id,)
        ).fetchone()
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
        now_ts = datetime.now().isoformat(timespec="seconds")
        connection.execute(
            "UPDATE watchlist SET progress=?, status=?, updated_at=? WHERE anime_id=?",
            (progress, status, now_ts, anime_id),
        )
        connection.execute(
            "INSERT INTO watch_history (anime_id, title, episode, watched_at) VALUES (?, ?, ?, ?)",
            (anime_id, row["title"], progress, now_ts),
        )
        return progress, status


def remove_anime(anime_id: int, owner_id: str | None = None) -> None:
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        connection.execute("DELETE FROM watchlist WHERE anime_id=?", (anime_id,))


def export_watchlist(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"format_version": BACKUP_FORMAT_VERSION, "items": rows}, indent=2, ensure_ascii=False)


def csv_safe_cell(value: Any) -> Any:
    """Neutralize spreadsheet formulas in user-controlled text cells."""
    if isinstance(value, str) and value.lstrip(" \t\r\n")[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def export_watchlist_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Anime ID",
            "Title",
            "Status",
            "Progress",
            "Episodes",
            "Duration (min)",
            "AniList Score",
            "User Score",
            "Rewatches",
            "Tags",
            "Genres",
            "Notes",
            "Updated At",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.get("anime_id"),
                csv_safe_cell(row.get("title")),
                row.get("status"),
                row.get("progress"),
                row.get("episodes") or "",
                row.get("duration") or "",
                row.get("score") or "",
                row.get("user_score") or "",
                row.get("rewatches", 0),
                csv_safe_cell(row.get("tags") or ""),
                csv_safe_cell(row.get("genres") or ""),
                csv_safe_cell(row.get("notes") or ""),
                row.get("updated_at") or "",
            ]
        )
    return output.getvalue()


def export_watchlist_mal_xml(rows: list[dict[str, Any]]) -> str:
    status_map = {
        "WATCHING": "Watching",
        "REWATCHING": "Watching",
        "COMPLETED": "Completed",
        "PLANNING": "Plan to Watch",
        "DROPPED": "Dropped",
    }
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<myanimelist>",
        "  <myinfo>",
        "    <user_export_type>1</user_export_type>",
        "  </myinfo>",
    ]
    for row in rows:
        title = html.escape(str(row.get("title", "")))
        anime_id = row.get("anime_id", 0)
        progress = row.get("progress", 0)
        status = status_map.get(str(row.get("status", "")), "Plan to Watch")
        score = row.get("user_score") or 0
        score_10 = round(score / 10) if score > 0 else 0
        rewatches = row.get("rewatches") or 0
        notes = html.escape(str(row.get("notes") or ""))
        xml_parts.append("  <anime>")
        xml_parts.append(f"    <series_animedb_id>{anime_id}</series_animedb_id>")
        xml_parts.append(f"    <series_title>{title}</series_title>")
        xml_parts.append(f"    <my_watched_episodes>{progress}</my_watched_episodes>")
        xml_parts.append(f"    <my_status>{status}</my_status>")
        xml_parts.append(f"    <my_score>{score_10}</my_score>")
        xml_parts.append(f"    <my_times_watched>{rewatches}</my_times_watched>")
        xml_parts.append(f"    <my_comments>{notes}</my_comments>")
        xml_parts.append("    <update_on_import>1</update_on_import>")
        xml_parts.append("  </anime>")
    xml_parts.append("</myanimelist>")
    return "\n".join(xml_parts)


def generate_airing_ics(rows: list[dict[str, Any]]) -> str:
    """Generate RFC 5545 iCalendar data for upcoming airing episodes in watchlist."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Otaku Orbit//Anime Airing Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Otaku Orbit Airing Schedule",
    ]
    now_utc = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    for row in rows:
        airing_at = row.get("next_airing_at")
        if not airing_at or airing_at <= 0:
            continue
        episode = row.get("next_airing_episode", 1)
        title = row.get("title", "Anime")
        dt_start = datetime.fromtimestamp(airing_at, ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
        duration_min = row.get("duration") or 24
        dt_end = datetime.fromtimestamp(airing_at + duration_min * 60, ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
        uid = f"otaku-orbit-{row.get('anime_id', 0)}-ep{episode}-{airing_at}@otaku-orbit"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now_utc}",
                f"DTSTART:{dt_start}",
                f"DTEND:{dt_end}",
                f"SUMMARY:{title} - Episode {episode}",
                f"DESCRIPTION:Broadcast of {title} Episode {episode}.",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def get_next_airing_countdown(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    now = int(time.time())
    airing_candidates = []
    for row in rows:
        airing_at = row.get("next_airing_at")
        if airing_at and airing_at > now and (airing_at - now) <= 172800:
            airing_candidates.append((airing_at, row))
    if not airing_candidates:
        return None
    airing_candidates.sort(key=lambda x: x[0])
    closest_ts, anime_row = airing_candidates[0]
    diff_seconds = closest_ts - now
    hours, rem = divmod(diff_seconds, 3600)
    minutes = rem // 60
    return {
        "title": anime_row.get("title"),
        "episode": anime_row.get("next_airing_episode"),
        "airing_at": closest_ts,
        "hours": hours,
        "minutes": minutes,
    }


def extract_streaming_links(anime: dict[str, Any]) -> list[dict[str, Any]]:
    links = []
    seen = set()
    streaming_sites = {
        "crunchyroll",
        "netflix",
        "hulu",
        "hidive",
        "disney+",
        "amazon",
        "prime video",
        "bilibili",
        "youtube",
        "funimation",
        "vrv",
    }
    for item in anime.get("externalLinks", []):
        site = item.get("site", "")
        url = item.get("url", "")
        l_type = item.get("type", "")
        if url and (site.lower() in streaming_sites or l_type == "STREAMING") and url not in seen:
            seen.add(url)
            links.append({"site": site, "url": url, "color": item.get("color")})
    for ep in anime.get("streamingEpisodes", []):
        site = ep.get("site") or "Watch Online"
        url = ep.get("url", "")
        if url and url not in seen:
            seen.add(url)
            links.append({"site": site, "url": url, "color": None})
    return links


def extract_characters_and_seiyuu(anime: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    char_data = anime.get("characters", {})
    for edge in char_data.get("edges", []):
        node = edge.get("node")
        if not node:
            continue
        c_name = node.get("name", {}).get("full") or "Unknown"
        c_native = node.get("name", {}).get("native") or ""
        c_img = (node.get("image") or {}).get("large") or (node.get("image") or {}).get("medium")
        role = (edge.get("role") or "MAIN").replace("_", " ").title()
        vas = edge.get("voiceActors", [])
        va = vas[0] if vas else None
        va_name = va.get("name", {}).get("full") if va else None
        va_img = (
            (va.get("image") or {}).get("large")
            if va and is_safe_cover_url((va.get("image") or {}).get("large"))
            else None
        )
        results.append(
            {
                "character": c_name,
                "character_native": c_native,
                "char_img": c_img if is_safe_cover_url(c_img) else None,
                "role": role,
                "seiyuu": va_name,
                "seiyuu_img": va_img,
            }
        )
    return results


def generate_music_links(title: str) -> dict[str, str]:
    q_op = quote(f"{title} anime opening theme")
    q_ed = quote(f"{title} anime ending theme")
    q_ost = quote(f"{title} original soundtrack")
    return {
        "Spotify OP": f"https://open.spotify.com/search/{q_op}",
        "Spotify ED": f"https://open.spotify.com/search/{q_ed}",
        "YouTube Music": f"https://music.youtube.com/search?q={q_ost}",
    }


ANILIST_STATUS_MAP = {
    "CURRENT": "WATCHING",
    "COMPLETED": "COMPLETED",
    "PLANNING": "PLANNING",
    "DROPPED": "DROPPED",
    "PAUSED": "PAUSED",
    "REPEATING": "REWATCHING",
}


def sync_anilist_profile(username: str, media_type: str = "ANIME", owner_id: str | None = None) -> int:
    query = """
    query ($userName: String, $type: MediaType) {
      MediaListCollection(userName: $userName, type: $type) {
        lists {
          entries {
            status
            progress
            score(format: POINT_100)
            repeat
            notes
            media {
              id
              siteUrl
              title { romaji english native }
              coverImage { extraLarge large }
              bannerImage
              episodes
              duration
              averageScore
              genres
              nextAiringEpisode { airingAt episode }
            }
          }
        }
      }
    }
    """
    data = anilist_response(query, {"userName": username, "type": media_type})
    collection = data.get("MediaListCollection", {})
    lists = collection.get("lists", [])
    synced = 0
    for lst in lists:
        for entry in lst.get("entries", []):
            media = entry.get("media")
            if not media:
                continue
            anilist_status = entry.get("status", "PLANNING")
            status = ANILIST_STATUS_MAP.get(anilist_status, "PLANNING")
            progress = entry.get("progress") or 0
            score = entry.get("score")
            repeat = entry.get("repeat") or 0
            notes = entry.get("notes") or ""
            save_anime(media, status=status, progress=progress, owner_id=owner_id, rewatches=repeat)
            if score or notes:
                update_progress(
                    media["id"],
                    progress,
                    status,
                    user_score=int(score) if score else None,
                    notes=notes,
                    rewatches=repeat,
                    owner_id=owner_id,
                )
            synced += 1
    return synced


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
    duration = row.get("duration")
    if duration is not None:
        try:
            duration = int(duration)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Backup entry {index} has an invalid episode duration.") from error
        if duration <= 0:
            raise ValueError(f"Backup entry {index} has an invalid episode duration.")
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
    rewatches = row.get("rewatches", 0)
    if rewatches is not None:
        try:
            rewatches = int(rewatches)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Backup entry {index} has an invalid rewatch count.") from error
        if rewatches < 0:
            raise ValueError(f"Backup entry {index} has an invalid rewatch count.")
    else:
        rewatches = 0
    status = row.get("status", "PLANNING") if row.get("status") in WATCH_STATUSES else "PLANNING"
    try:
        validate_watchlist_state(progress, status, episodes, user_score, rewatches=rewatches)
    except ValueError as error:
        raise ValueError(f"Backup entry {index} has invalid status or progress.") from error
    notes = str(row.get("notes") or "").strip()
    if len(notes) > 5000:
        raise ValueError(f"Backup entry {index} has notes longer than 5,000 characters.")
    tags = str(row.get("tags") or "").strip()
    if len(tags) > 500:
        raise ValueError(f"Backup entry {index} has tags longer than 500 characters.")
    banner_img = row.get("banner_image")
    return {
        "anime_id": anime_id,
        "title": title,
        "image": row.get("image") if is_safe_cover_url(row.get("image")) else None,
        "status": status,
        "progress": progress,
        "episodes": episodes,
        "duration": duration,
        "score": score,
        "genres": str(row.get("genres", "")),
        "next_airing_at": next_airing_at,
        "next_airing_episode": next_airing_episode,
        "user_score": user_score,
        "rewatches": rewatches,
        "tags": tags,
        "banner_image": banner_img if is_safe_cover_url(banner_img) else None,
        "notes": notes,
        "updated_at": row.get("updated_at", datetime.now().isoformat(timespec="seconds")),
    }


def import_watchlist(payload: str, owner_id: str | None = None) -> int:
    if len(payload.encode("utf-8")) > 2_000_000:
        raise ValueError("That backup is larger than the 2 MB safety limit.")
    backup = json.loads(payload)
    if isinstance(backup, dict) and "format_version" in backup:
        version = backup.get("format_version")
        if version != BACKUP_FORMAT_VERSION:
            raise ValueError(f"Unsupported watchlist backup version: {version}.")
        imported = backup.get("items")
    else:
        imported = backup  # Legacy version-zero backups were bare lists.
    if not isinstance(imported, list):
        raise ValueError("A watchlist backup must contain a list of titles.")
    if len(imported) > 10_000:
        raise ValueError("A watchlist backup cannot contain more than 10,000 titles.")
    restored = 0
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        for index, raw_row in enumerate(imported, start=1):
            row = validate_backup_row(raw_row, index)
            connection.execute(
                """INSERT INTO watchlist
                (anime_id, title, image, status, progress, episodes, duration, score, genres,
                 next_airing_at, next_airing_episode, user_score, notes, rewatches, tags, banner_image, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(anime_id) DO UPDATE SET title=excluded.title, image=excluded.image,
                status=excluded.status, progress=excluded.progress, episodes=excluded.episodes, duration=excluded.duration,
                score=excluded.score, genres=excluded.genres, next_airing_at=excluded.next_airing_at,
                next_airing_episode=excluded.next_airing_episode, user_score=coalesce(excluded.user_score, watchlist.user_score),
                notes=coalesce(excluded.notes, watchlist.notes), rewatches=excluded.rewatches, tags=excluded.tags,
                banner_image=excluded.banner_image, updated_at=excluded.updated_at""",
                (
                    row["anime_id"],
                    row["title"],
                    row["image"],
                    row["status"],
                    row["progress"],
                    row["episodes"],
                    row["duration"],
                    row["score"],
                    row["genres"],
                    row["next_airing_at"],
                    row["next_airing_episode"],
                    row["user_score"],
                    row.get("notes", ""),
                    row.get("rewatches", 0),
                    row.get("tags", ""),
                    row.get("banner_image"),
                    row["updated_at"],
                ),
            )
            restored += 1
    return restored


@st.cache_data(ttl=API_CACHE_TTL, show_spinner=False)
def anilist_response(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    request_body = {"query": query, "variables": variables or {}}
    response: requests.Response | None = None
    for attempt in range(REQUEST_ATTEMPTS):
        try:
            response = _request_session().post(API_URL, json=request_body, timeout=REQUEST_TIMEOUT)
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
            backoff = min(8.0, 0.35 * (2**attempt))
            time.sleep(backoff + random.uniform(0.0, backoff * 0.25))
    if response is None:
        raise requests.RequestException("AniList did not return a response")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("AniList returned an invalid response format.")
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "AniList returned an error"))
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise RuntimeError("AniList returned an invalid data payload.")
    return data


def anilist_query(query: str, variables: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = anilist_response(query, variables)
    if data.get("Media"):
        return [data["Media"]]
    return data.get("Page", {}).get("media", [])


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_anime_detail(anime_id: int, media_type: str = "ANIME") -> dict[str, Any] | None:
    payload = anilist_query(DETAIL_QUERY, {"id": anime_id, "type": media_type})
    return payload[0] if payload else None


def current_season_and_year(today: date | None = None) -> tuple[str, int]:
    today = today or date.today()
    month = today.month
    season = (
        "WINTER"
        if month in (12, 1, 2)
        else "SPRING"
        if month in (3, 4, 5)
        else "SUMMER"
        if month in (6, 7, 8)
        else "FALL"
    )
    return season, today.year + (1 if month == 12 else 0)


def fetch_anime(
    search: str = "",
    season: str | None = None,
    year: int | None = None,
    page: int = 1,
    is_adult: bool | None = False,
    media_type: str = "ANIME",
) -> list[dict[str, Any]]:
    results, _ = fetch_anime_page(search, season, year, page, is_adult=is_adult, media_type=media_type)
    return results


def fetch_anime_page(
    search: str = "",
    season: str | None = None,
    year: int | None = None,
    page: int = 1,
    is_adult: bool | None = False,
    media_type: str = "ANIME",
) -> tuple[list[dict[str, Any]], bool]:
    variables: dict[str, Any] = {
        "search": search or None,
        "page": page,
        "isAdult": is_adult if is_adult is not None else False,
        "type": media_type,
    }
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
        logger.warning("Serving session-cached data after a remote request failed")
        return offline_cache[cache_key], True
    offline_cache[cache_key] = result
    st.session_state.setdefault("offline_cache_updated_at", {})[cache_key] = datetime.now().isoformat(
        timespec="seconds"
    )
    return result, False


def cache_age_label(cache_key: str) -> str:
    cached_at = st.session_state.get("offline_cache_updated_at", {}).get(cache_key)
    if not cached_at:
        return "an unknown time"
    try:
        age_seconds = max(0, int((datetime.now() - datetime.fromisoformat(cached_at)).total_seconds()))
    except (TypeError, ValueError):
        return "an unknown time"
    if age_seconds < 60:
        return "less than a minute ago"
    if age_seconds < 3600:
        return f"{age_seconds // 60} minute(s) ago"
    return f"{age_seconds // 3600} hour(s) ago"


def filter_anime(
    results: list[dict[str, Any]],
    genre: str = "All genres",
    format_name: str = "All formats",
    minimum_score: int = 0,
    include_adult: bool = False,
    source: str = "All sources",
    studio: str = "All studios",
) -> list[dict[str, Any]]:
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
        if source != "All sources" and anime.get("source") != source:
            continue
        if studio != "All studios":
            studios = [s.get("name") for s in anime.get("studios", {}).get("nodes", []) if s.get("name")]
            if studio not in studios:
                continue
        filtered.append(anime)
    return filtered


def render_filters(results: list[dict[str, Any]], key_prefix: str) -> list[dict[str, Any]]:
    genres = sorted({genre for anime in results for genre in anime.get("genres", [])})
    formats = sorted({anime.get("format") for anime in results if anime.get("format")})
    sources = sorted({anime.get("source") for anime in results if anime.get("source")})
    studios = sorted(
        {s["name"] for anime in results for s in anime.get("studios", {}).get("nodes", []) if s.get("name")}
    )
    with st.expander("Filter results", expanded=False):
        c1, c2, c3 = st.columns(3)
        genre = c1.selectbox("Genre", ["All genres", *genres], key=f"genre-{key_prefix}")
        format_name = c2.selectbox("Format", ["All formats", *formats], key=f"format-{key_prefix}")
        source_val = c3.selectbox("Source Material", ["All sources", *sources], key=f"source-{key_prefix}")

        c4, c5, c6 = st.columns(3)
        studio_val = c4.selectbox("Studio", ["All studios", *studios], key=f"studio-{key_prefix}")
        minimum_score = c5.slider("Minimum score", 0, 90, 0, 5, key=f"score-{key_prefix}")
        include_adult = c6.checkbox("Include mature titles", key=f"adult-{key_prefix}")
    filtered = filter_anime(
        results,
        genre,
        format_name,
        minimum_score,
        include_adult,
        source=source_val,
        studio=studio_val,
    )
    st.caption(f"Showing {len(filtered)} of {len(results)} titles")
    return filtered


def display_title(anime: dict[str, Any]) -> str:
    title = anime.get("title", {})
    return title.get("english") or title.get("romaji") or title.get("native") or "Untitled"


def clean_description(text: str | None) -> str:
    if not text:
        return "No synopsis available."
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|blockquote|h[1-6])\s*>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def rank_recommendations(
    rows: list[dict[str, Any]], candidates: list[dict[str, Any]], saved_ids: set[int], limit: int = 8
) -> list[dict[str, Any]]:
    """Rank unseen titles using watchlist genres weighted by completion and personal ratings."""
    genre_weights: dict[str, float] = {}
    for row in rows:
        rating = (row.get("user_score") or row.get("score") or 60) / 100
        status_weight = {"COMPLETED": 1.5, "WATCHING": 1.2, "PLANNING": 0.75, "DROPPED": 0.25}.get(
            row.get("status"), 0.75
        )
        weight = status_weight * max(0.25, rating)
        for genre in filter(None, str(row.get("genres", "")).split(", ")):
            genre_weights[genre] = genre_weights.get(genre, 0.0) + weight
    ranked = sorted(
        (anime for anime in candidates if anime.get("id") not in saved_ids),
        key=lambda anime: (
            sum(genre_weights.get(genre, 0.0) for genre in anime.get("genres", [])),
            anime.get("averageScore") or 0,
            anime.get("popularity") or 0,
        ),
        reverse=True,
    )
    return ranked[:limit]


def calculate_runtime_display(episodes: int | None, duration: int | None, progress: int = 0) -> str:
    """Format an anime's total or remaining runtime, defaulting to 24 minutes per episode."""
    if episodes is None or episodes <= 0:
        return "Estimated watch time unavailable"
    episode_minutes = duration if duration is not None and duration > 0 else 24
    remaining_episodes = max(episodes - max(progress, 0), 0)
    minutes = episodes * episode_minutes if progress <= 0 else remaining_episodes * episode_minutes
    hours, leftover_minutes = divmod(minutes, 60)
    formatted = (
        f"{hours}h {leftover_minutes}m"
        if hours and leftover_minutes
        else (f"{hours}h" if hours else f"{leftover_minutes}m")
    )
    if progress > 0:
        return f"{formatted} remaining"
    return f"{episodes} eps · {formatted} total"


def _format_timestamp(timestamp: int, timezone_name: str | None = None) -> str:
    if timezone_name is None:
        return datetime.fromtimestamp(timestamp).strftime("%d %b, %H:%M")
    return datetime.fromtimestamp(timestamp, ZoneInfo(timezone_name)).strftime("%d %b, %H:%M")


def format_airing(anime: dict[str, Any], timezone_name: str | None = None) -> str:
    airing = anime.get("nextAiringEpisode")
    if not airing:
        return "No upcoming episode"
    try:
        airing_at = int(airing["airingAt"])
        episode = int(airing["episode"])
        if airing_at <= 0 or episode <= 0:
            return "No upcoming episode"
        when = _format_timestamp(airing_at, timezone_name)
    except (KeyError, TypeError, ValueError, OSError, OverflowError, ZoneInfoNotFoundError):
        return "No upcoming episode"
    return f"Episode {episode} · {when}"


def format_row_airing(row: dict[str, Any], timezone_name: str | None = None) -> str | None:
    if not row.get("next_airing_at"):
        return None
    try:
        airing_at = int(row["next_airing_at"])
        if airing_at <= 0:
            return None
        when = _format_timestamp(airing_at, timezone_name)
    except (KeyError, TypeError, ValueError, OSError, OverflowError, ZoneInfoNotFoundError):
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


def fetch_airing_schedule(start_timestamp: int, end_timestamp: int) -> list[dict[str, Any]]:
    variables = {"airingAt_greater": start_timestamp, "airingAt_lesser": end_timestamp}
    data = anilist_response(AIRING_SCHEDULE_QUERY, variables)
    return data.get("Page", {}).get("airingSchedules", [])


@st.dialog("Anime details")
def show_anime_details(anime_id: int) -> None:
    media_type = st.session_state.get("global_media_type", "ANIME")
    try:
        anime = fetch_anime_detail(anime_id, media_type=media_type)
    except (requests.RequestException, RuntimeError) as error:
        st.error(f"Could not load details: {error}")
        return
    if not anime:
        st.info("No details were found for this title.")
        return
    banner_url = banner_image_url(anime)
    if banner_url:
        st.image(banner_url, use_container_width=True)
    title = display_title(anime)
    st.subheader(title)
    cover_col, info_col = st.columns([1, 2], gap="medium")
    with cover_col:
        cover_url = cover_image_url(anime)
        if cover_url:
            st.image(cover_url, caption=f"Cover art for {title}", use_container_width=True)
    with info_col:
        score = anime.get("averageScore")
        source = anime.get("source") or "Original"
        st.caption(
            f"**Format:** {anime.get('format', 'ANIME')} · **Status:** {anime.get('status', 'UNKNOWN')} · **Score:** {score or '—'}/100 · **Source:** {source}"
        )
        st.write(clean_description(anime.get("description")))
        ep_count = anime.get("episodes") or anime.get("chapters")
        count_label = "Episodes" if media_type == "ANIME" else "Chapters"
        st.write(f"**{count_label}:** {ep_count or 'Unknown'} · **Duration:** {anime.get('duration') or 'Unknown'} min")
        st.caption(f"Estimated watch time: {calculate_runtime_display(anime.get('episodes'), anime.get('duration'))}")
        studios = [studio["name"] for studio in anime.get("studios", {}).get("nodes", []) if studio.get("name")]
        if studios:
            st.write("**Studio:** " + ", ".join(studios))

    characters_and_seiyuu = extract_characters_and_seiyuu(anime)
    if characters_and_seiyuu:
        st.divider()
        st.subheader("Characters & Voice Cast (Seiyuu)")
        cast_cols = st.columns(min(len(characters_and_seiyuu[:4]), 4))
        for col, item in zip(cast_cols, characters_and_seiyuu[:4]):
            with col:
                with st.container(border=True):
                    if item.get("char_img"):
                        st.image(item["char_img"], use_container_width=True)
                    st.markdown(f"**{item['character']}**")
                    st.caption(f"Role: {item['role']}")
                    if item.get("seiyuu"):
                        st.caption(f"🎙️ VA: {item['seiyuu']}")

    streaming_links = extract_streaming_links(anime)
    if streaming_links:
        st.divider()
        st.subheader("Where to Stream Legally")
        stream_cols = st.columns(min(len(streaming_links[:4]), 4))
        for col, s_link in zip(stream_cols, streaming_links[:4]):
            col.link_button(f"▶ {s_link['site']}", s_link["url"], use_container_width=True)

    music_links = generate_music_links(title)
    st.divider()
    st.subheader("OST & Theme Songs")
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.link_button("🎵 Opening on Spotify", music_links["Spotify OP"], use_container_width=True)
    m_col2.link_button("🎵 Ending on Spotify", music_links["Spotify ED"], use_container_width=True)
    m_col3.link_button("▶️ YouTube Music OST", music_links["YouTube Music"], use_container_width=True)

    relations = [
        edge for edge in anime.get("relations", {}).get("edges", []) if edge.get("node") and edge.get("relationType")
    ]
    if relations:
        st.divider()
        st.subheader("Related Titles")
        rel_cols = st.columns(min(len(relations[:4]), 4))
        for col, edge in zip(rel_cols, relations[:4]):
            rel_node = edge["node"]
            rel_type = edge.get("relationType", "").replace("_", " ").title()
            with col:
                rel_cover = cover_image_url(rel_node)
                if rel_cover:
                    st.image(rel_cover, use_container_width=True)
                st.caption(f"**{rel_type}**\n{display_title(rel_node)}")

    recs = [
        node.get("mediaRecommendation")
        for node in anime.get("recommendations", {}).get("nodes", [])
        if node.get("mediaRecommendation")
    ]
    if recs:
        st.divider()
        st.subheader("Fans Also Liked")
        rec_cols = st.columns(min(len(recs[:4]), 4))
        for col, rec in zip(rec_cols, recs[:4]):
            with col:
                rec_cover = cover_image_url(rec)
                if rec_cover:
                    st.image(rec_cover, use_container_width=True)
                rec_score = f"★ {rec.get('averageScore')}" if rec.get("averageScore") else ""
                st.caption(f"{display_title(rec)} {rec_score}")

    site_url = anime.get("siteUrl") or f"https://anilist.co/anime/{anime_id}"
    trailer_url = format_trailer_url(anime.get("trailer"))
    btn_cols = st.columns(2 if trailer_url else 1)
    btn_cols[0].link_button("View on AniList", site_url, use_container_width=True)
    if trailer_url:
        btn_cols[1].link_button("Watch Trailer", trailer_url, use_container_width=True)


def render_card(anime: dict[str, Any], saved_ids: set[int], key_prefix: str, owner_id: str | None = None) -> None:
    title = display_title(anime)
    compact = st.session_state.get("compact_cards", False)
    image, details = st.columns([0.9, 2.3] if compact else [1, 2.2], gap="medium")
    with image:
        cover_url = cover_image_url(anime)
        if cover_url:
            st.image(cover_url, caption=f"Cover art for {title}", use_container_width=True)
    with details:
        st.subheader(title)
        score = anime.get("averageScore")
        source = anime.get("source") or "Original"
        meta = (
            f"{anime.get('format', 'ANIME')}  ·  {anime.get('status', 'UNKNOWN')}  ·  {score or '—'}/100  ·  {source}"
        )
        st.caption(meta)
        st.write(clean_description(anime.get("description"))[:420] + "…")
        genres = anime.get("genres", [])
        if genres:
            st.caption(" · ".join(genres))
        if anime.get("nextAiringEpisode"):
            st.info(format_airing(anime, st.session_state.get("display_timezone", "Asia/Kolkata")))
        if st.button(
            f"Details: {title}",
            key=f"details-{key_prefix}-{anime['id']}",
            help=f"Open full details for {title}",
            use_container_width=True,
        ):
            show_anime_details(anime["id"])
        if anime["id"] in saved_ids:
            st.success("In your watchlist")
        else:
            if st.button(
                f"Add {title} to watchlist",
                key=f"add-{key_prefix}-{anime['id']}",
                help=f"Save {title} to your watchlist",
                use_container_width=True,
            ):
                save_anime(anime, owner_id=owner_id)
                st.rerun()


def render_poster_grid(
    results: list[dict[str, Any]],
    saved_ids: set[int],
    key_prefix: str,
    owner_id: str | None = None,
    columns_per_row: int = 4,
) -> None:
    if not results:
        st.info("No titles match the current filters.")
        return
    for i in range(0, len(results), columns_per_row):
        cols = st.columns(columns_per_row)
        for col, anime in zip(cols, results[i : i + columns_per_row]):
            with col:
                with st.container(border=True):
                    title = display_title(anime)
                    cover_url = cover_image_url(anime)
                    if cover_url:
                        st.image(
                            cover_url, caption=title[:30] + ("…" if len(title) > 30 else ""), use_container_width=True
                        )
                    score = anime.get("averageScore")
                    score_badge = f"★ {score}" if score else "Unrated"
                    st.caption(f"{anime.get('format', 'TV')} · {score_badge}")
                    btn_a, btn_b = st.columns(2)
                    if btn_a.button("Details", key=f"pdet-{key_prefix}-{anime['id']}", use_container_width=True):
                        show_anime_details(anime["id"])
                    if anime["id"] in saved_ids:
                        btn_b.caption("✓ In List")
                    else:
                        if btn_b.button("+ Add", key=f"padd-{key_prefix}-{anime['id']}", use_container_width=True):
                            save_anime(anime, owner_id=owner_id)
                            st.rerun()


def render_airing_calendar(rows: list[dict[str, Any]], saved_ids: set[int], owner_id: str | None = None) -> None:
    st.title("Airing Calendar")
    st.caption("Track new anime episodes releasing this week in your timezone.")
    timezone_name = st.session_state.get("display_timezone", "Asia/Kolkata")
    now_ts = int(time.time())
    start_ts = now_ts - 7200
    end_ts = now_ts + 7 * 86400

    ics_content = generate_airing_ics(rows)
    st.download_button(
        "📅 Export Airing Schedule (.ics)",
        ics_content,
        "otaku_orbit_airing.ics",
        "text/calendar",
        help="Subscribe in Apple Calendar, Google Calendar, or Outlook",
    )

    if offline_mode_enabled():
        st.info("Offline mode is enabled; airing schedule requests are disabled.")
        return
    try:
        schedules, from_cache = load_with_fallback(
            f"airing_schedule:{start_ts // 86400}",
            lambda: fetch_airing_schedule(start_ts, end_ts),
        )
        if from_cache:
            st.info(f"Showing cached airing schedule from {cache_age_label(f'airing_schedule:{start_ts // 86400}')}.")
    except (requests.RequestException, RuntimeError) as error:
        st.error(f"Could not load airing schedule: {error}")
        return
    if not schedules:
        st.info("No upcoming episodes scheduled for this week.")
        return
    watchlist_only = st.toggle("Show only anime in my watchlist", value=False, key="calendar_watchlist_only")
    filtered_schedules = []
    for item in schedules:
        media = item.get("media") or {}
        if watchlist_only and media.get("id") not in saved_ids:
            continue
        filtered_schedules.append(item)
    if not filtered_schedules:
        st.info("No airing episodes found matching the filter.")
        return
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in filtered_schedules:
        airing_at = item.get("airingAt", 0)
        dt = datetime.fromtimestamp(airing_at, tz)
        day_key = dt.strftime("%A, %d %b")
        today_str = datetime.now(tz).strftime("%A, %d %b")
        day_label = f"🔥 Today ({day_key})" if day_key == today_str else day_key
        grouped.setdefault(day_label, []).append(item)
    for day_label, items in grouped.items():
        st.subheader(day_label)
        cols_per_row = 3
        for i in range(0, len(items), cols_per_row):
            row_cols = st.columns(cols_per_row)
            for col, item in zip(row_cols, items[i : i + cols_per_row]):
                media = item.get("media") or {}
                anime_id = media.get("id")
                episode = item.get("episode")
                airing_at = item.get("airingAt", 0)
                dt = datetime.fromtimestamp(airing_at, tz)
                time_str = dt.strftime("%H:%M")
                with col:
                    with st.container(border=True):
                        title = display_title(media)
                        cover_url = cover_image_url(media)
                        if cover_url:
                            st.image(cover_url, use_container_width=True)
                        st.markdown(f"**{title}**")
                        st.caption(f"**Ep {episode}** · **{time_str}** ({timezone_name})")
                        if anime_id in saved_ids:
                            st.success("★ In your watchlist")
                        else:
                            if st.button("Add to watchlist", key=f"cal-add-{item.get('id')}", use_container_width=True):
                                save_anime(media, owner_id=owner_id)
                                st.rerun()
                        if st.button("Details", key=f"cal-det-{item.get('id')}", use_container_width=True):
                            show_anime_details(anime_id)
        st.divider()


def render_tier_list_maker(rows: list[dict[str, Any]]) -> None:
    st.subheader("Tier List Maker")
    st.caption("Organize your collection into S, A, B, C, and D tiers based on your ratings.")
    tiers: dict[str, list[dict[str, Any]]] = {
        "S Tier (Masterpiece)": [],
        "A Tier (Great)": [],
        "B Tier (Good)": [],
        "C Tier (Average)": [],
        "D Tier (Disappointing)": [],
    }
    for row in rows:
        score = row.get("user_score")
        if score is not None and score >= 90:
            tiers["S Tier (Masterpiece)"].append(row)
        elif score is not None and score >= 80:
            tiers["A Tier (Great)"].append(row)
        elif score is not None and score >= 70:
            tiers["B Tier (Good)"].append(row)
        elif score is not None and score >= 50:
            tiers["C Tier (Average)"].append(row)
        elif score is not None and score > 0:
            tiers["D Tier (Disappointing)"].append(row)
        else:
            tiers["B Tier (Good)"].append(row)

    tier_colors = {
        "S Tier (Masterpiece)": "#ff7f7f",
        "A Tier (Great)": "#ffbf7f",
        "B Tier (Good)": "#ffff7f",
        "C Tier (Average)": "#7fff7f",
        "D Tier (Disappointing)": "#7fbfff",
    }
    for tier_name, tier_items in tiers.items():
        color = tier_colors[tier_name]
        st.markdown(
            f'<div style="background:{color}; color:#111; font-weight:bold; padding:6px 14px; border-radius:8px; margin:10px 0 6px;">{tier_name} ({len(tier_items)})</div>',
            unsafe_allow_html=True,
        )
        if tier_items:
            t_cols = st.columns(min(len(tier_items), 6))
            for col, item in zip(t_cols, tier_items[:6]):
                with col:
                    img = item.get("image")
                    if img:
                        st.image(img, use_container_width=True)
                    st.caption(item.get("title", "")[:24])
        else:
            st.caption("No titles placed in this tier.")


def render_analytics(rows: list[dict[str, Any]], owner_id: str | None = None) -> None:
    st.title("Analytics & Insights")
    st.caption("Deep dive into your viewing journey, habits, achievements, and pacing.")
    if not rows:
        st.info("Add titles to your watchlist to unlock viewing analytics.")
        return
    history = fetch_watch_history(days=60, owner_id=owner_id)
    completed_episodes = sum(row.get("progress", 0) for row in rows)
    watched_minutes = sum(
        min(row.get("progress", 0), row.get("episodes") or row.get("progress", 0)) * (row.get("duration") or 24)
        for row in rows
    )
    streak = calculate_watch_streak(history)
    velocity = calculate_watch_velocity(history)
    rated_rows = [r for r in rows if r.get("user_score")]
    avg_user_score = round(sum(r["user_score"] for r in rated_rows) / len(rated_rows), 1) if rated_rows else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Titles Tracked", len(rows))
    c2.metric("Episodes Logged", completed_episodes)
    c3.metric("Time Watched", f"{watched_minutes // 60}h")
    c4.metric("Active Streak", f"{streak} day{'s' if streak != 1 else ''}", delta="🔥")
    c5.metric("Watching Pace", f"{velocity} eps/day")

    st.divider()

    active_watching = [r for r in rows if r.get("status") in {"WATCHING", "REWATCHING"} and r.get("episodes")]
    if active_watching:
        st.subheader("Completion Forecast")
        st.caption(f"Based on your current velocity (~{velocity} eps/day):")
        f_cols = st.columns(min(len(active_watching[:3]), 3))
        for col, row in zip(f_cols, active_watching[:3]):
            rem_eps = max(row["episodes"] - row["progress"], 0)
            est_date = estimate_completion_date(rem_eps, velocity)
            with col:
                with st.container(border=True):
                    st.markdown(f"**{row['title']}**")
                    st.caption(f"Progress: {row['progress']}/{row['episodes']} ({rem_eps} left)")
                    st.write(f"🎯 Est. Finish: **{est_date or 'Complete!'}**" if est_date else "Complete!")
        st.divider()

    if rated_rows:
        st.subheader("Rating Distribution")
        score_bins = {f"{i * 10}-{(i + 1) * 10}": 0 for i in range(1, 10)}
        score_bins["90-100"] = 0
        for r in rated_rows:
            s = r["user_score"]
            if s >= 90:
                score_bins["90-100"] += 1
            else:
                b_key = f"{(s // 10) * 10}-{(s // 10 + 1) * 10}"
                if b_key in score_bins:
                    score_bins[b_key] += 1
        st.bar_chart(score_bins)
        st.caption(f"Mean personal score: **{avg_user_score}/100** across {len(rated_rows)} rated titles.")
        st.divider()

    genre_counts: dict[str, int] = {}
    for row in rows:
        for genre in filter(None, (row.get("genres") or "").split(", ")):
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    if genre_counts:
        st.subheader("Genre Profile")
        st.bar_chart(dict(sorted(genre_counts.items(), key=lambda item: item[1], reverse=True)[:10]))
        st.divider()

    st.subheader("Viewing Activity Log (Recent 30 Days)")
    if history:
        day_counts: dict[str, int] = {}
        for h in history:
            day = h.get("watched_at", "")[:10]
            if day:
                day_counts[day] = day_counts.get(day, 0) + 1
        recent_30_days = [(date.today() - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
        heatmap_data = {d: day_counts.get(d, 0) for d in recent_30_days}
        st.bar_chart(heatmap_data)
    else:
        st.info("Watch history will record daily as you log progress with +1 Ep.")
    st.divider()

    st.subheader("Achievements & Milestones")
    achievements = evaluate_achievements(rows, history)
    cols_per_row = 4
    for i in range(0, len(achievements), cols_per_row):
        b_cols = st.columns(cols_per_row)
        for col, ach in zip(b_cols, achievements[i : i + cols_per_row]):
            with col:
                with st.container(border=True):
                    badge_status = "✨ Unlocked" if ach["unlocked"] else "🔒 Locked"
                    st.markdown(f"### {ach['icon']} {ach['title']}")
                    st.caption(ach["desc"])
                    if ach["unlocked"]:
                        st.success(badge_status)
                    else:
                        st.caption(badge_status)
    st.divider()

    render_tier_list_maker(rows)


def render_watchlist(owner_id: str | None = None) -> None:
    rows = db_rows(owner_id)
    st.title("Your library")
    if not rows:
        st.info("Your watchlist is empty. Discover something new from the sidebar.")
        return
    counts = {status: sum(row["status"] == status for row in rows) for status in WATCH_STATUSES}
    cols = st.columns(len(WATCH_STATUSES))
    for column, (label, value) in zip(cols, counts.items()):
        column.metric(label.title(), value)
    with st.expander("Batch actions", expanded=False):
        batch_options = [f"{row['title']} (ID: {row['anime_id']})" for row in rows]
        selected_labels = st.multiselect("Select titles for batch actions", batch_options, key="batch_selected")
        selected_ids = []
        for label in selected_labels:
            try:
                anime_id = int(label.split("(ID: ")[-1].rstrip(")"))
                selected_ids.append(anime_id)
            except (ValueError, IndexError):
                pass
        b_col1, b_col2, b_col3 = st.columns(3)
        batch_new_status = b_col1.selectbox("Set status", WATCH_STATUSES, key="batch_new_status")
        if b_col1.button("Apply status", use_container_width=True) and selected_ids:
            batch_update_status(selected_ids, batch_new_status, owner_id)
            st.success(f"Updated status for {len(selected_ids)} title(s).")
            st.rerun()
        batch_new_tag = b_col2.text_input("Add tag", placeholder="e.g. Masterpiece", key="batch_new_tag")
        if b_col2.button("Apply tag", use_container_width=True) and selected_ids and batch_new_tag.strip():
            batch_add_tag(selected_ids, batch_new_tag.strip(), owner_id)
            st.success(f"Added tag '{batch_new_tag.strip()}' to {len(selected_ids)} title(s).")
            st.rerun()
        if b_col3.button("Remove selected", type="secondary", use_container_width=True) and selected_ids:
            batch_remove_anime(selected_ids, owner_id)
            st.success(f"Removed {len(selected_ids)} title(s).")
            st.rerun()
    st.divider()
    sort_order = st.selectbox(
        "Sort saved titles",
        ["Recently updated", "Title", "AniList score", "My rating", "Progress", "Runtime remaining"],
        key="watchlist-sort",
    )
    if sort_order == "Recently updated":
        rows.sort(key=lambda row: row.get("updated_at") or "", reverse=True)
    elif sort_order == "Title":
        rows.sort(key=lambda row: row["title"].lower())
    elif sort_order == "AniList score":
        rows.sort(key=lambda row: row["score"] or 0, reverse=True)
    elif sort_order == "My rating":
        rows.sort(key=lambda row: row.get("user_score") or 0, reverse=True)
    elif sort_order == "Progress":
        rows.sort(key=lambda row: row["progress"], reverse=True)
    elif sort_order == "Runtime remaining":
        rows.sort(
            key=lambda row: (
                max((row.get("episodes") or row["progress"]) - row["progress"], 0) * (row.get("duration") or 24)
            )
        )
    active = [row for row in rows if row["status"] in {"WATCHING", "REWATCHING"}]
    goal = st.session_state.get("daily_goal", 3)
    if active:
        st.subheader("Continue watching")
        st.caption(f"Your next episodes are always at the top of the orbit. Goal: {goal} episode(s) per day.")
        for row in active[:3]:
            total = row["episodes"] or 0
            progress = row["progress"]
            remaining = max(total - progress, 0) if total else "?"
            st.write(f"**{row['title']}** · episode {progress + 1} next · {remaining} remaining")
            if total:
                st.caption(f"Remaining watch time: {calculate_runtime_display(total, row.get('duration'), progress)}")
        st.divider()
    timezone_name = st.session_state.get("display_timezone", "Asia/Kolkata")
    reminders_enabled = st.session_state.get("show_airing_reminders", True)
    reminders = [
        (row["title"], format_row_airing(row, timezone_name))
        for row in rows
        if reminders_enabled and format_row_airing(row, timezone_name)
    ]
    if reminders:
        st.subheader("Upcoming airing reminders")
        for title, airing in reminders[:5]:
            st.info(f"**{title}** · {airing}")
        st.divider()
    st.subheader("All saved titles")
    all_tags = sorted({t.strip() for r in rows for t in (r.get("tags") or "").split(",") if t.strip()})
    f_col1, f_col2, f_col3 = st.columns(3)
    search = f_col1.text_input("🔍 Quick filter watchlist", placeholder="Filter by title, tag, or notes…")
    status_filter = f_col2.selectbox("Status", ["All statuses", *WATCH_STATUSES])
    tag_filter = f_col3.selectbox("Tag", ["All tags", *all_tags] if all_tags else ["All tags"])
    visible_rows = [
        row
        for row in rows
        if (
            not search
            or search.lower() in row["title"].lower()
            or search.lower() in (row.get("tags") or "").lower()
            or search.lower() in (row.get("notes") or "").lower()
            or search.lower() in (row.get("genres") or "").lower()
        )
        and (status_filter == "All statuses" or row["status"] == status_filter)
        and (
            tag_filter == "All tags"
            or tag_filter in [t.strip() for t in (row.get("tags") or "").split(",") if t.strip()]
        )
    ]
    st.caption(f"Showing {len(visible_rows)} of {len(rows)} titles")
    for row in visible_rows:
        left, right = st.columns([3, 2])
        with left:
            if row.get("image"):
                c_img, c_info = st.columns([1, 3.5])
                with c_img:
                    st.image(row["image"], use_container_width=True)
                with c_info:
                    st.subheader(row["title"])
            else:
                st.subheader(row["title"])
            total = row["episodes"] or 0
            progress = row["progress"]
            st.progress(min(progress / total, 1.0) if total else 0.0, text=f"Episode {progress}/{total or '?'}")
            user_score_display = f"{row['user_score']}/100" if row.get("user_score") else "Not rated"
            meta_parts = [f"AniList: {row['score'] or '—'}", f"My score: {user_score_display}"]
            if row.get("rewatches"):
                meta_parts.append(f"Rewatched: {row['rewatches']}x")
            if row.get("tags"):
                meta_parts.append(f"Tags: {row['tags']}")
            st.caption(" · ".join(meta_parts))
            st.caption(f"{row['genres'] or 'Genre unknown'}")
            if row.get("notes"):
                st.caption(f"Notes: {row['notes']}")
        with right:
            status = st.selectbox(
                "Status", WATCH_STATUSES, index=WATCH_STATUSES.index(row["status"]), key=f"status-{row['anime_id']}"
            )
            p_col, r_col = st.columns(2)
            new_progress = p_col.number_input(
                "Episodes watched",
                min_value=0,
                max_value=row["episodes"] or 9999,
                value=row["progress"],
                key=f"progress-{row['anime_id']}",
            )
            rewatches_val = r_col.number_input(
                "Rewatch count",
                min_value=0,
                max_value=999,
                value=int(row.get("rewatches") or 0),
                key=f"rewatch-{row['anime_id']}",
            )
            my_score = st.number_input(
                "My rating (0-100)",
                min_value=0,
                max_value=100,
                value=int(row.get("user_score") or 0),
                key=f"userscore-{row['anime_id']}",
            )
            tags_val = st.text_input(
                "Tags",
                value=row.get("tags") or "",
                placeholder="e.g. Masterpiece, Cozy",
                max_chars=500,
                key=f"tags-{row['anime_id']}",
            )
            notes_val = st.text_input(
                "Notes",
                value=row.get("notes") or "",
                placeholder="Thoughts, reviews…",
                max_chars=5000,
                key=f"notes-{row['anime_id']}",
            )
            a, b, c = st.columns([1, 1, 1])
            if a.button("+1 Ep", key=f"inc-{row['anime_id']}", use_container_width=True):
                increment_watchlist_progress(row["anime_id"], owner_id)
                st.rerun()
            if b.button("Save", key=f"save-{row['anime_id']}", use_container_width=True):
                update_progress(
                    row["anime_id"],
                    int(new_progress),
                    status,
                    user_score=int(my_score),
                    notes=notes_val.strip(),
                    rewatches=int(rewatches_val),
                    tags=tags_val.strip(),
                    owner_id=owner_id,
                )
                st.rerun()
            if c.button("Remove", key=f"remove-{row['anime_id']}", use_container_width=True):
                remove_anime(row["anime_id"], owner_id)
                st.rerun()
        st.divider()
    if not visible_rows:
        st.info("No saved titles match those filters.")
    with st.expander("Backup your watchlist"):
        st.caption("Export a portable backup or restore one on another device.")
        d_col1, d_col2, d_col3 = st.columns(3)
        d_col1.download_button(
            "Download JSON",
            export_watchlist(rows),
            "otaku-orbit-watchlist.json",
            "application/json",
            use_container_width=True,
        )
        d_col2.download_button(
            "Download CSV",
            export_watchlist_csv(rows),
            "otaku-orbit-watchlist.csv",
            "text/csv",
            use_container_width=True,
        )
        d_col3.download_button(
            "Download MAL XML",
            export_watchlist_mal_xml(rows),
            "otaku-orbit-mal.xml",
            "application/xml",
            use_container_width=True,
        )

        uploaded = st.file_uploader("Restore JSON backup", type="json")
        if uploaded is not None and st.button("Restore backup", use_container_width=True):
            try:
                count = import_watchlist(uploaded.getvalue().decode("utf-8"), owner_id)
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
    minutes = sum((row["episodes"] or 0) * (row.get("duration") or 24) for row in rows)
    watched_minutes = sum(
        min(row["progress"], row["episodes"] or row["progress"]) * (row.get("duration") or 24) for row in rows
    )
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


def render_recommendations(rows: list[dict[str, Any]], saved_ids: set[int], owner_id: str | None = None) -> None:
    st.title("Picked for you")
    if not rows:
        st.info("Save a few anime first and your recommendations will learn your taste.")
        return
    preferred = {genre.strip() for row in rows for genre in row["genres"].split(",") if genre.strip()}
    st.write(
        "Recommendations are weighted by your ratings, progress, and favorite genres: "
        + ", ".join(sorted(preferred))
        + "."
    )
    try:
        candidates = anilist_query(TRENDING_QUERY)
    except (requests.RequestException, RuntimeError) as error:
        st.error(f"Could not load recommendations right now: {error}")
        return
    for anime in rank_recommendations(rows, candidates, saved_ids):
        with st.container(border=True):
            render_card(anime, saved_ids, "recommendation", owner_id)


def render_settings(owner_id: str | None = None) -> None:
    st.title("Settings & Integrations")
    st.caption("Configure personal preferences, theme presets, integrations, and mobile settings.")

    with st.expander("AniList 1-Click Library Synchronization", expanded=True):
        st.caption("Import your public library directly from AniList into your Otaku Orbit database.")
        anilist_user = st.text_input("AniList Username", placeholder="e.g. ShashankS1011")
        sync_type = st.radio("Sync Media", ["ANIME", "MANGA"], horizontal=True, key="sync_media_type")
        if st.button("Synchronize Library", type="primary") and anilist_user.strip():
            with st.spinner("Fetching AniList library..."):
                try:
                    count = sync_anilist_profile(anilist_user.strip(), sync_type, owner_id)
                    st.success(f"Synchronized {count} title(s) from AniList.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Synchronization failed: {error}")

    with st.expander("Progressive Web App (PWA) & Offline Setup"):
        st.caption("Install Otaku Orbit directly to your phone or desktop home screen:")
        st.markdown("""
        - **Android (Chrome/Edge):** Tap the browser menu `⋮` and select **'Add to Home screen'** or **'Install app'**.
        - **iOS (Safari):** Tap the Share button `⎋` and tap **'Add to Home Screen'** `[+]`.
        - **Desktop (Chrome/Edge):** Click the install icon in the address bar to run as a dedicated desktop app.
        """)

    with st.expander("Privacy Controls & Data Management"):
        st.caption("Permanently delete this account's watchlist and viewing history.")
        if st.button("Delete my data", key="settings-del-data"):
            st.session_state["confirm_delete_owner_data"] = True
        if st.session_state.get("confirm_delete_owner_data"):
            st.warning("This action cannot be undone. All saved titles, history, and notes will be wiped.")
            c1, c2 = st.columns(2)
            if c1.button("Confirm Wiping Data", key="conf-wipe-btn"):
                delete_owner_data(owner_id)
                st.session_state.pop("confirm_delete_owner_data", None)
                st.success("Your data has been wiped.")
                st.rerun()
            if c2.button("Cancel", key="canc-wipe-btn"):
                st.session_state.pop("confirm_delete_owner_data", None)
                st.rerun()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    st.set_page_config(page_title=APP_NAME, page_icon="O", layout="wide", initial_sidebar_state="expanded")
    auth_enabled = authentication_configured()
    owner_id = current_owner_id()
    if owner_id is None:
        st.title(APP_NAME)
        st.info("Sign in to access your private watchlist.")
        if st.button("Sign in", type="primary"):
            st.login()
        st.stop()
    init_db(owner_id)
    selected_theme = st.session_state.get("theme_palette", "Saiyan Neon")
    theme = THEME_PALETTES.get(selected_theme, THEME_PALETTES["Saiyan Neon"])
    st.markdown(
        f"""<style>
    .block-container {{max-width: 1320px; padding-top: 2rem; padding-bottom: 5rem;}}
    [data-testid="stMetricValue"] {{color: {theme["metric"]};}}
    [data-testid="stSidebar"] {{background: {theme["sidebar"]};}}
    [data-testid="stHeader"] {{background: rgba(0,0,0,0);}}
    div[data-testid="stVerticalBlockBorderWrapper"] {{border-color: rgba(244,184,255,.18); border-radius: 18px;}}
    .orbit-hero {{padding: 1.4rem 1.6rem; margin-bottom: 1.4rem; border: 1px solid rgba(244,184,255,.2); border-radius: 22px; background: radial-gradient(circle at 85% 15%, {theme["glow"]}, transparent 38%), linear-gradient(120deg, #211939, #151526);}}
    .orbit-kicker {{font-size: .76rem; letter-spacing: .18em; text-transform: uppercase; color: {theme["primary"]}; font-weight: 700;}}
    .orbit-hero h1 {{margin: .2rem 0 .4rem; font-size: clamp(2rem, 5vw, 3.5rem);}}
    .orbit-muted {{color: #aaa8bd; max-width: 700px;}}
    .orbit-credit {{position: fixed; bottom: 12px; left: 0; right: 0; text-align: center; color: #858297; font-size: .75rem; z-index: 999;}}
    :focus-visible {{outline: 3px solid {theme["primary"]} !important; outline-offset: 2px;}}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important;}} }}
    @media (max-width: 768px) {{
        .block-container {{padding: 1rem .75rem 4rem;}}
        .orbit-hero {{padding: 1rem; border-radius: 16px;}}
        .orbit-hero h1 {{font-size: 2rem; line-height: 1.1;}}
        .orbit-credit {{font-size: .68rem; padding: 0 .5rem;}}
    }}
    </style>
    <link rel="manifest" href="manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="{theme["primary"]}">
    <meta name="application-name" content="Otaku Orbit">
    """,
        unsafe_allow_html=True,
    )
    rows = db_rows(owner_id)
    saved_ids = {row["anime_id"] for row in rows}

    with st.sidebar:
        st.markdown("# Otaku Orbit")
        st.caption(f"Your personal anime command centre | v{APP_VERSION}")
        st.link_button("Open live app", APP_URL, use_container_width=True)
        st.link_button("Open community support", SUPPORT_LINK, use_container_width=True)
        if auth_enabled:
            st.caption(f"Signed in as {st.user.get('email') or st.user.get('name') or 'account user'}")
            if st.button("Sign out", use_container_width=True):
                st.logout()
        else:
            st.info("Guest mode: data is isolated to this browser session and will not sync to another device.")

        media_mode = st.radio("Media Type", ["Anime", "Manga & Light Novels"], horizontal=True, key="global_media_mode")
        st.session_state["global_media_type"] = "MANGA" if media_mode == "Manga & Light Novels" else "ANIME"

        page = st.radio(
            "Navigate",
            ["Discover", "For you", "Airing Calendar", "Seasonal", "Watchlist", "Analytics & Insights", "Settings"],
            label_visibility="collapsed",
        )
        st.divider()
        st.metric("Saved titles", len(rows))
        st.selectbox("Theme preset", list(THEME_PALETTES.keys()), key="theme_palette")
        st.session_state["daily_goal"] = st.number_input(
            "Daily episode goal", min_value=1, max_value=20, value=st.session_state.get("daily_goal", 3)
        )
        st.session_state["compact_cards"] = st.toggle(
            "Compact cards", value=st.session_state.get("compact_cards", False)
        )
        st.toggle(
            "Show airing reminders",
            value=st.session_state.get("show_airing_reminders", True),
            key="show_airing_reminders",
        )
        st.selectbox(
            "Airing timezone",
            SUPPORTED_TIMEZONES,
            key="display_timezone",
            index=SUPPORTED_TIMEZONES.index(st.session_state.get("display_timezone", "Asia/Kolkata")),
        )
        if st.button("Refresh catalogue data", help="Clear cached AniList responses and fetch fresh data"):
            anilist_response.clear()
            fetch_anime_detail.clear()
            st.session_state.pop("offline_cache", None)
            st.session_state.pop("offline_cache_updated_at", None)
            st.rerun()
        with st.expander("System status"):
            st.caption(f"AniList endpoint: {API_URL}")
            st.caption(f"Request cache: {API_CACHE_TTL} seconds")
            st.caption(f"Local database: {DB_PATH.name}")
            st.caption("Storage mode: private per-account or per-session SQLite")
            st.caption("Cloud-hosted SQLite can reset on redeploy unless a persistent path is configured.")
            if st.button("Check AniList connection"):
                anilist_response.clear()
                with st.spinner("Checking AniList availability"):
                    try:
                        health_data = anilist_response(TRENDING_QUERY, {"type": st.session_state["global_media_type"]})
                        media_count = len(health_data.get("Page", {}).get("media", []))
                        st.success(f"AniList is reachable and returned {media_count} titles.")
                    except (requests.RequestException, RuntimeError) as error:
                        st.error(f"AniList health check failed: {error}")
    st.markdown(f'<div class="orbit-credit">{AUTHOR_CREDIT}</div>', unsafe_allow_html=True)

    reminders_enabled = st.session_state.get("show_airing_reminders", True)
    countdown = get_next_airing_countdown(rows)
    if countdown and reminders_enabled:
        st.info(
            f"📢 **Airing Soon:** **{countdown['title']}** (Episode {countdown['episode']}) broadcasts in **{countdown['hours']}h {countdown['minutes']}m**."
        )

    if page == "Watchlist":
        render_watchlist(owner_id)
        return
    if page == "Analytics & Insights":
        render_analytics(rows, owner_id)
        return
    if page == "Settings":
        render_settings(owner_id)
        return
    if page == "For you":
        render_recommendations(rows, saved_ids, owner_id)
        return
    if page == "Airing Calendar":
        render_airing_calendar(rows, saved_ids, owner_id)
        return
    if page == "Discover":
        st.markdown(
            '<div class="orbit-hero"><div class="orbit-kicker">Anime discovery, upgraded</div><h1>Find your next obsession</h1><div class="orbit-muted">Search AniList, save what catches your eye, and let your watchlist become your personal anime map.</div></div>',
            unsafe_allow_html=True,
        )
        query = st.text_input("Search titles", placeholder="Try Frieren, One Piece, or Cowboy Bebop")
        m_type = st.session_state.get("global_media_type", "ANIME")
        if offline_mode_enabled():
            results = []
            st.info("Offline mode is enabled; AniList requests are disabled.")
        elif query:
            search_state = st.session_state.setdefault(
                "discover_search",
                {
                    "query": "",
                    "results": [],
                    "page": 0,
                    "has_next": True,
                },
            )
            if search_state["query"] != query:
                search_state.update({"query": query, "results": [], "page": 0, "has_next": True})
            try:
                if not search_state["results"]:
                    (first_page, has_next), from_cache = load_with_fallback(
                        f"search:{query}:1:{m_type}", lambda: fetch_anime_page(query, page=1, media_type=m_type)
                    )
                    search_state.update({"results": first_page, "page": 1, "has_next": has_next})
                    if from_cache:
                        st.info(
                            f"Showing cached results from {cache_age_label(f'search:{query}:1:{m_type}')} because AniList is unavailable."
                        )
                results = search_state["results"]
                if search_state["has_next"] and st.button(
                    "Load more results", help="Fetch the next page of search results"
                ):
                    next_page = search_state["page"] + 1
                    (next_results, has_next), _ = load_with_fallback(
                        f"search:{query}:{next_page}:{m_type}",
                        lambda: fetch_anime_page(query, page=next_page, media_type=m_type),
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
                results, from_cache = load_with_fallback(
                    f"trending:{m_type}", lambda: anilist_query(TRENDING_QUERY, {"type": m_type})
                )
                if from_cache:
                    st.info(
                        f"AniList is unavailable; showing trending results cached {cache_age_label(f'trending:{m_type}')}."
                    )
            except (requests.RequestException, RuntimeError) as error:
                st.warning(f"AniList is unavailable and no cached trending results exist yet: {error}")
                results = []
        if st.button("Surprise me", help="Show one random title from the current results") and results:
            results = [random.choice(results)]
            st.info("A random pick from the anime universe.")
        results = render_filters(results, "discover")
        d_mode = st.radio("View layout", ["Poster Grid", "Detailed Cards"], horizontal=True, key="discover_layout")
        if d_mode == "Poster Grid":
            render_poster_grid(results, saved_ids, "discover", owner_id)
        else:
            for anime in results:
                with st.container(border=True):
                    render_card(anime, saved_ids, "discover", owner_id)
    else:
        curr_season, curr_year = current_season_and_year()
        season_cols = st.columns([1, 1, 2])
        season_names = ["WINTER", "SPRING", "SUMMER", "FALL"]
        season = season_cols[0].selectbox(
            "Season", season_names, index=season_names.index(curr_season), key="seasonal-season"
        )
        years = list(range(curr_year + 1, curr_year - 6, -1))
        year = season_cols[1].selectbox(
            "Year", years, index=years.index(curr_year) if curr_year in years else 1, key="seasonal-year"
        )
        st.title(f"{season.title()} {year}")
        st.write(f"Explore the anime lineup for {season.title()} {year}.")
        m_type = st.session_state.get("global_media_type", "ANIME")
        if offline_mode_enabled():
            results = []
            st.info("Offline mode is enabled; AniList requests are disabled.")
        else:
            try:
                results, from_cache = load_with_fallback(
                    f"season:{season}:{year}:{m_type}",
                    lambda: fetch_anime(season=season, year=year, media_type=m_type),
                )
                if from_cache:
                    st.info(
                        f"AniList is unavailable; showing seasonal results cached {cache_age_label(f'season:{season}:{year}:{m_type}')}."
                    )
            except (requests.RequestException, RuntimeError) as error:
                st.error(f"Could not load the seasonal lineup: {error}")
                results = []
        results = render_filters(results, "seasonal")
        s_mode = st.radio("View layout", ["Poster Grid", "Detailed Cards"], horizontal=True, key="seasonal_layout")
        if s_mode == "Poster Grid":
            render_poster_grid(results, saved_ids, "seasonal", owner_id)
        else:
            for anime in results:
                with st.container(border=True):
                    render_card(anime, saved_ids, "seasonal", owner_id)


if __name__ == "__main__":
    main()
