from __future__ import annotations

import csv
import html
import io
import json
import math
import re
import time
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from modules.config import ACHIEVEMENTS, BACKUP_FORMAT_VERSION


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
