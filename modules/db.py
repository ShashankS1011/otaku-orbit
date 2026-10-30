from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import streamlit as st

from modules.config import (
    BACKUP_FORMAT_VERSION,
    DB_PATH,
    MANGA_STATUSES,
    WATCH_STATUSES,
)


def get_db_path() -> Path:
    app_mod = sys.modules.get("app")
    if app_mod is not None and hasattr(app_mod, "DB_PATH"):
        return app_mod.DB_PATH
    return DB_PATH


def authentication_configured() -> bool:
    app_mod = sys.modules.get("app")
    if app_mod is not None and hasattr(app_mod, "authentication_configured"):
        fn = getattr(app_mod, "authentication_configured")
        if fn != authentication_configured:
            return bool(fn())
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
    base_path = get_db_path()
    if owner_id is None:
        return base_path
    digest = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:24]
    return base_path.with_name(f"{base_path.stem}.{digest}{base_path.suffix}")


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
        connection.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_media_status ON watchlist(media_type, status)")

        connection.execute("""CREATE TABLE IF NOT EXISTS watch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            episode INTEGER NOT NULL,
            watched_at TEXT NOT NULL
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_watch_history_date ON watch_history(watched_at DESC)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_watch_history_anime ON watch_history(anime_id, watched_at DESC)"
        )


def db_rows(owner_id: str | None = None) -> list[dict[str, Any]]:
    with sqlite3.connect(database_path_for_owner(owner_id), timeout=15) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM watchlist ORDER BY updated_at DESC")]


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
    from modules.services import banner_image_url, cover_image_url, display_title

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


def validate_backup_row(row: Any, index: int) -> dict[str, Any]:
    from modules.services import is_safe_cover_url

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
        imported = backup
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
