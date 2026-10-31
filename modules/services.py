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

from modules.config import (
    ACHIEVEMENTS,
    ANIME_ARCHETYPES,
    ANIME_MOODS,
    APP_URL,
    APP_VERSION,
    BACKUP_FORMAT_VERSION,
    BINGO_CHALLENGES,
    CHARACTER_TROPES,
    FILLER_GUIDES,
    FRANCHISE_WATCH_ORDERS,
    HISTORICAL_ERAS,
    TIER_LIST_TEMPLATES,
)


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
    title = anime.get("title")
    if isinstance(title, str):
        return title.strip()
    if isinstance(title, dict):
        return title.get("english") or title.get("romaji") or title.get("native") or "Untitled"
    return "Untitled"


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


def pick_random_backlog(
    rows: list[dict[str, Any]],
    mood: str | None = None,
    max_duration: int | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    if status:
        candidates = [r for r in rows if r.get("status") == status]
    else:
        candidates = [r for r in rows if r.get("status") in {"PLANNING", "WATCHING"}]
    if not candidates:
        candidates = list(rows)
    if not candidates:
        return None

    if mood and mood in ANIME_MOODS:
        target_genres = set(ANIME_MOODS[mood])
        candidates = [
            c for c in candidates if any(g.strip() in target_genres for g in (c.get("genres") or "").split(","))
        ] or candidates

    if max_duration and max_duration > 0:
        candidates = [c for c in candidates if (c.get("duration") or 24) <= max_duration] or candidates

    import random

    return random.choice(candidates) if candidates else None


def calculate_taste_match_score(anime: dict[str, Any], user_library: list[dict[str, Any]]) -> int:
    if not user_library:
        return int(anime.get("averageScore") or 75)

    loved_titles = [
        row for row in user_library if (row.get("user_score") or 0) >= 80 or row.get("status") == "COMPLETED"
    ]
    if not loved_titles:
        loved_titles = user_library

    genre_weights: dict[str, int] = {}
    for r in loved_titles:
        for g in (r.get("genres") or "").split(","):
            g = g.strip()
            if g:
                genre_weights[g] = genre_weights.get(g, 0) + 1

    anime_genres = anime.get("genres", [])
    if isinstance(anime_genres, str):
        anime_genres = [g.strip() for g in anime_genres.split(",")]

    if not anime_genres or not genre_weights:
        return int(anime.get("averageScore") or 75)

    max_weight = max(genre_weights.values(), default=1)
    overlap_score = sum(genre_weights.get(g, 0) for g in anime_genres) / (len(anime_genres) * max_weight)

    base = anime.get("averageScore") or 70
    match_pct = int(min(99, max(50, (base * 0.4) + (overlap_score * 60))))
    return match_pct


def filter_by_mood(results: list[dict[str, Any]], mood: str) -> list[dict[str, Any]]:
    if not mood or mood not in ANIME_MOODS:
        return results
    target_genres = set(ANIME_MOODS[mood])
    matched = []
    for anime in results:
        genres = anime.get("genres", [])
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",")]
        if any(g in target_genres for g in genres):
            matched.append(anime)
    return matched


def extract_staff_and_directors(
    anime_detail: dict[str, Any],
) -> list[dict[str, str]]:
    staff_nodes = anime_detail.get("staff", {}).get("edges", []) if isinstance(anime_detail.get("staff"), dict) else []
    result = []
    for edge in staff_nodes:
        role = edge.get("role", "")
        node = edge.get("node", {})
        name = node.get("name", {}).get("full") or "Unknown"
        if role and name:
            result.append({"name": name, "role": role})
    return result


def get_franchise_watch_order(title: str) -> dict[str, Any] | None:
    t_lower = title.lower()
    for key, order in FRANCHISE_WATCH_ORDERS.items():
        if key.lower() in t_lower:
            return order
    return None


def derive_artwork_accent_color(anime: dict[str, Any] | str) -> str:
    if isinstance(anime, str):
        seed_str = anime
    else:
        seed_str = str(anime.get("id") or anime.get("anime_id") or display_title(anime))
    palette = [
        "#00f0ff",
        "#f4b8ff",
        "#00ff88",
        "#ff8447",
        "#bd93f9",
        "#ff2e93",
        "#00e5ff",
        "#ffea00",
        "#7000ff",
    ]
    hash_val = sum(ord(c) for c in seed_str)
    return palette[hash_val % len(palette)]


def get_theme_video_links(anime_title: str) -> dict[str, str]:
    q = quote(f"{anime_title} anime opening theme")
    return {
        "YouTube Search": f"https://www.youtube.com/results?search_query={q}",
        "AnimeThemes": f"https://animethemes.moe/search?q={quote(anime_title)}",
    }


def build_seiyuu_character_matrix(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    matrix: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        title = r.get("title", "Unknown")
        seiyuu_list = extract_characters_and_seiyuu(r)
        if not seiyuu_list and r.get("characters_json"):
            try:
                raw = json.loads(r["characters_json"])
                if isinstance(raw, list):
                    seiyuu_list = raw
            except Exception:
                pass
        for pair in seiyuu_list:
            actor = (pair.get("actor") or pair.get("seiyuu") or pair.get("voice_actor") or "").strip()
            char = pair.get("character", "").strip()
            if actor and actor != "Unknown":
                matrix.setdefault(actor, []).append({"character": char, "anime": title})
    return {k: v for k, v in matrix.items() if len(v) >= 1}


def apply_spoiler_mask(synopsis: str, is_unwatched: bool = True) -> str:
    if not is_unwatched or not synopsis:
        return synopsis
    return (
        f'<div class="orbit-spoiler-box" title="Click to reveal synopsis">'
        f'<span class="orbit-spoiler-tag">⚠️ UNWATCHED - SPOILER BLOCKED</span>'
        f'<div class="orbit-spoiler-text">{html.escape(synopsis)}</div></div>'
    )


def generate_otaku_passport_svg(username: str, library_rows: list[dict[str, Any]]) -> str:
    total_titles = len(library_rows)
    completed_eps = sum(r.get("progress", 0) for r in library_rows)
    watched_hours = (
        sum(
            min(r.get("progress", 0), r.get("episodes") or r.get("progress", 0)) * (r.get("duration") or 24)
            for r in library_rows
        )
        // 60
    )
    genres: dict[str, int] = {}
    for r in library_rows:
        for g in (r.get("genres") or "").split(","):
            g = g.strip()
            if g:
                genres[g] = genres.get(g, 0) + 1
    top_genre = max(genres, key=genres.get) if genres else "Explorer"

    fav = "Undiscovered"
    rated = [r for r in library_rows if r.get("user_score")]
    if rated:
        best = max(rated, key=lambda x: x["user_score"])
        fav = best.get("title", "Undiscovered")[:28]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#141126"/>
      <stop offset="100%" stop-color="#0a0a14"/>
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f4b8ff"/>
      <stop offset="100%" stop-color="#00f0ff"/>
    </linearGradient>
  </defs>
  <rect width="800" height="450" rx="24" fill="url(#bg)" stroke="rgba(244,184,255,0.3)" stroke-width="2"/>
  <circle cx="720" cy="80" r="120" fill="rgba(111,76,255,0.12)" filter="blur(40px)"/>
  
  <text x="50" y="70" font-family="'Segoe UI', Roboto, sans-serif" font-size="28" font-weight="900" fill="url(#glow)">OTAKU ORBIT PASSPORT</text>
  <text x="50" y="100" font-family="'Segoe UI', Roboto, sans-serif" font-size="14" fill="#8c89a0" letter-spacing="2">OFFICIAL ANIME EXPLORER IDENTITY | v{APP_VERSION}</text>
  
  <rect x="50" y="130" width="220" height="260" rx="16" fill="rgba(255,255,255,0.04)" stroke="rgba(255,255,255,0.1)"/>
  <circle cx="160" cy="220" r="50" fill="#231d3d" stroke="url(#glow)" stroke-width="2"/>
  <text x="160" y="235" font-family="'Segoe UI', Roboto, sans-serif" font-size="40" text-anchor="middle" fill="#f4b8ff">⚡</text>
  <text x="160" y="320" font-family="'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="700" text-anchor="middle" fill="#ffffff">{username}</text>
  <text x="160" y="345" font-family="'Segoe UI', Roboto, sans-serif" font-size="12" text-anchor="middle" fill="#00f0ff">SAIYAN LEVEL: OVER 9000</text>
  
  <g transform="translate(310, 140)">
    <rect width="440" height="60" rx="12" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
    <text x="20" y="26" font-family="'Segoe UI', Roboto, sans-serif" font-size="12" fill="#8c89a0">TITLES TRACKED</text>
    <text x="20" y="48" font-family="'Segoe UI', Roboto, sans-serif" font-size="20" font-weight="700" fill="#ffffff">{total_titles}</text>
    
    <text x="230" y="26" font-family="'Segoe UI', Roboto, sans-serif" font-size="12" fill="#8c89a0">EPISODES WATCHED</text>
    <text x="230" y="48" font-family="'Segoe UI', Roboto, sans-serif" font-size="20" font-weight="700" fill="#f4b8ff">{completed_eps}</text>
  </g>
  
  <g transform="translate(310, 220)">
    <rect width="440" height="60" rx="12" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
    <text x="20" y="26" font-family="'Segoe UI', Roboto, sans-serif" font-size="12" fill="#8c89a0">TOTAL TIME LOGGED</text>
    <text x="20" y="48" font-family="'Segoe UI', Roboto, sans-serif" font-size="20" font-weight="700" fill="#00ff88">{watched_hours} Hours</text>
    
    <text x="230" y="26" font-family="'Segoe UI', Roboto, sans-serif" font-size="12" fill="#8c89a0">TOP AFFINITY GENRE</text>
    <text x="230" y="48" font-family="'Segoe UI', Roboto, sans-serif" font-size="20" font-weight="700" fill="#00f0ff">{top_genre}</text>
  </g>
  
  <g transform="translate(310, 300)">
    <rect width="440" height="90" rx="12" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
    <text x="20" y="30" font-family="'Segoe UI', Roboto, sans-serif" font-size="12" fill="#8c89a0">TOP RATED FAVORITE</text>
    <text x="20" y="60" font-family="'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="700" fill="#ffffff">{fav}</text>
  </g>
</svg>"""


def evaluate_bingo_card(library_rows: list[dict[str, Any]], history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed_series = [r for r in library_rows if r.get("status") == "COMPLETED"]
    total_eps = sum(r.get("progress", 0) for r in library_rows)
    all_genres = {g.strip().lower() for r in library_rows for g in (r.get("genres") or "").split(",")}

    eval_card = []
    for item in BINGO_CHALLENGES:
        cid = item["check"]
        status = False
        if cid == "free_space":
            status = True
        elif cid == "long_series":
            status = any((r.get("episodes") or 0) >= 50 for r in completed_series)
        elif cid == "perfect_score":
            status = any((r.get("user_score") or 0) >= 100 for r in library_rows)
        elif cid == "rewatch":
            status = any(r.get("rewatches", 0) > 0 for r in library_rows)
        elif cid == "format_movie":
            status = any(r.get("format") == "MOVIE" for r in completed_series)
        elif cid == "genre_mecha":
            status = "mecha" in all_genres
        elif cid == "genre_music":
            status = "music" in all_genres
        elif cid == "genre_psychological":
            status = "psychological" in all_genres
        elif cid == "genre_sports":
            status = "sports" in all_genres
        elif cid == "genre_fantasy":
            status = "fantasy" in all_genres
        elif cid == "genre_romance":
            status = "romance" in all_genres
        elif cid == "genre_scifi":
            status = "sci-fi" in all_genres
        elif cid == "source_original":
            status = any(r.get("source") == "ORIGINAL" for r in library_rows)
        elif cid == "rated_10":
            status = sum(1 for r in library_rows if r.get("user_score")) >= 10
        elif cid == "tracked_manga":
            status = any(r.get("media_type") == "MANGA" for r in library_rows)
        elif cid == "completed_5":
            status = len(completed_series) >= 5
        elif cid == "episodes_25":
            status = total_eps >= 25
        elif cid == "tagged_5":
            status = sum(1 for r in library_rows if r.get("tags")) >= 5
        elif cid == "binge_5":
            day_counts: dict[str, int] = {}
            for h in history:
                d = h.get("watched_at", "")[:10]
                day_counts[d] = day_counts.get(d, 0) + 1
            status = any(v >= 5 for v in day_counts.values())
        elif cid == "backup_ready":
            status = len(library_rows) >= 1
        elif cid in {"pre_2000", "streak_3", "studio_kyoani", "studio_mappa", "studio_ufotable"}:
            status = len(library_rows) >= 3

        eval_card.append({**item, "completed": status})
    return eval_card


def calculate_user_taste_compatibility(lib_a: list[dict[str, Any]], lib_b: list[dict[str, Any]]) -> dict[str, Any]:
    ids_a = {r["anime_id"]: r for r in lib_a if "anime_id" in r}
    ids_b = {r["anime_id"]: r for r in lib_b if "anime_id" in r}
    common = set(ids_a.keys()).intersection(ids_b.keys())

    if not common:
        return {
            "common_count": 0,
            "compatibility_pct": 50,
            "summary": "No overlapping anime found yet between libraries.",
            "recommendations": [r.get("title", "") for r in lib_b[:5]],
        }

    score_diffs = []
    for aid in common:
        sa = ids_a[aid].get("user_score")
        sb = ids_b[aid].get("user_score")
        if sa and sb:
            score_diffs.append(abs(sa - sb))

    diff_penalty = sum(score_diffs) / len(score_diffs) if score_diffs else 10
    pct = int(max(20, min(99, 100 - (diff_penalty * 0.8))))

    unique_b = [r.get("title", "") for r in lib_b if r.get("anime_id") not in ids_a][:5]

    return {
        "common_count": len(common),
        "compatibility_pct": pct,
        "summary": f"Calculated over {len(common)} shared title(s).",
        "recommendations": unique_b,
    }


def generate_tier_list_svg(tiers_data: dict[str, list[dict[str, Any]]] | list[dict[str, Any]]) -> str:
    if isinstance(tiers_data, list):
        categorized: dict[str, list[dict[str, Any]]] = {"S": [], "A": [], "B": [], "C": [], "D": []}
        for item in tiers_data:
            score = item.get("user_score") or item.get("score") or 0
            if score >= 90:
                categorized["S"].append(item)
            elif score >= 80:
                categorized["A"].append(item)
            elif score >= 70:
                categorized["B"].append(item)
            elif score >= 60:
                categorized["C"].append(item)
            else:
                categorized["D"].append(item)
        tiers_data = categorized

    tier_colors = {
        "S": "#ff7f7f",
        "A": "#ffbf7f",
        "B": "#ffff7f",
        "C": "#7fff7f",
        "D": "#7fbfff",
    }
    rows_svg = []
    y = 60
    for tier, color in tier_colors.items():
        items = tiers_data.get(tier, [])
        titles_str = ", ".join(i.get("title", "") for i in items[:5]) or "No titles"
        rows_svg.append(f"""
    <g transform="translate(20, {y})">
      <rect width="80" height="70" rx="8" fill="{color}"/>
      <text x="40" y="44" font-family="sans-serif" font-size="28" font-weight="900" fill="#000000" text-anchor="middle">{tier}</text>
      <rect x="90" width="670" height="70" rx="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.1)"/>
      <text x="110" y="40" font-family="sans-serif" font-size="14" fill="#ffffff">{titles_str}</text>
    </g>""")
        y += 85

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{y + 20}" viewBox="0 0 800 {y + 20}">
  <rect width="800" height="{y + 20}" rx="16" fill="#121020"/>
  <text x="30" y="38" font-family="sans-serif" font-size="22" font-weight="700" fill="#f4b8ff">OTAKU ORBIT TIER LIST</text>
  {"".join(rows_svg)}
</svg>"""


def prepare_anilist_sync_payload(
    row: dict[str, Any] | int,
    status: str = "PLANNING",
    progress: int = 0,
    score: int | None = None,
) -> dict[str, Any]:
    from modules.config import ANILIST_STATUS_MAP

    rev_status = {v: k for k, v in ANILIST_STATUS_MAP.items()}
    if isinstance(row, int):
        media_id = row
        media_status = status
        media_progress = progress
        media_score = score or 0
    else:
        media_id = row.get("anime_id") or row.get("id", 0)
        media_status = row.get("status", "PLANNING")
        media_progress = row.get("progress", 0)
        media_score = row.get("user_score", 0) or 0

    anilist_status = rev_status.get(media_status, "CURRENT")
    mutation = """mutation ($mediaId: Int, $status: MediaListStatus, $progress: Int, $scoreRaw: Int) {
  SaveMediaListEntry (mediaId: $mediaId, status: $status, progress: $progress, scoreRaw: $scoreRaw) {
    id
    status
    progress
    score (format: POINT_100)
  }
}"""
    return {
        "query": mutation,
        "variables": {
            "mediaId": media_id,
            "status": anilist_status,
            "progress": media_progress,
            "scoreRaw": media_score,
        },
    }


def export_kitsu_json(rows: list[dict[str, Any]]) -> str:
    kitsu_entries = []
    for r in rows:
        status_map = {
            "WATCHING": "current",
            "COMPLETED": "completed",
            "PLANNING": "planned",
            "DROPPED": "dropped",
            "REWATCHING": "current",
        }
        kitsu_entries.append(
            {
                "type": "library-entries",
                "attributes": {
                    "status": status_map.get(r.get("status"), "planned"),
                    "progress": r.get("progress", 0),
                    "ratingTwenty": (r.get("user_score", 0) // 5) if r.get("user_score") else None,
                    "notes": r.get("notes", ""),
                    "reconsumeCount": r.get("rewatches", 0),
                },
                "media": {
                    "title": r.get("title", ""),
                    "id": r.get("anime_id"),
                },
            }
        )
    return json.dumps({"data": kitsu_entries}, indent=2)


def import_kitsu_json(json_str: str) -> list[dict[str, Any]]:
    payload = json.loads(json_str)
    entries = payload.get("data", [])
    result = []
    rev_status = {
        "current": "WATCHING",
        "completed": "COMPLETED",
        "planned": "PLANNING",
        "dropped": "DROPPED",
    }
    for e in entries:
        attrs = e.get("attributes", {})
        media = e.get("media", {})
        aid = media.get("id") or hash(media.get("title", "kitsu")) % 1_000_000
        score = (attrs.get("ratingTwenty") or 0) * 5
        result.append(
            {
                "anime_id": int(aid),
                "title": media.get("title", "Imported Title"),
                "status": rev_status.get(attrs.get("status"), "PLANNING"),
                "progress": attrs.get("progress", 0),
                "user_score": score if score > 0 else None,
                "notes": attrs.get("notes", ""),
                "rewatches": attrs.get("reconsumeCount", 0),
                "updated_at": datetime.now().isoformat(),
            }
        )
    return result


def export_simkl_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["simkl_id", "title", "type", "status", "user_rating", "episodes_watched"])
    for r in rows:
        writer.writerow(
            [
                r.get("anime_id"),
                csv_safe_cell(r.get("title", "")),
                r.get("media_type", "anime").lower(),
                r.get("status", "planning").lower(),
                r.get("user_score", ""),
                r.get("progress", 0),
            ]
        )
    return output.getvalue()


def import_simkl_csv(csv_str: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(csv_str))
    result = []
    for row in reader:
        try:
            aid = int(row.get("simkl_id") or 0)
        except ValueError:
            aid = 0
        if not aid:
            continue
        score_val = None
        if row.get("user_rating"):
            try:
                score_val = int(row["user_rating"])
            except ValueError:
                pass
        result.append(
            {
                "anime_id": aid,
                "title": row.get("title", "SIMKL Anime"),
                "status": (row.get("status") or "planning").upper(),
                "progress": int(row.get("episodes_watched") or 0),
                "user_score": score_val,
                "updated_at": datetime.now().isoformat(),
            }
        )
    return result


def generate_discord_webhook_payload(
    airing_anime: dict[str, Any] | str,
    episode: int | str = "?",
    total_episodes: int | str | None = None,
    score: int | None = None,
) -> dict[str, Any]:
    if isinstance(airing_anime, str):
        title = airing_anime
        ep = episode
        image = ""
    else:
        title = airing_anime.get("title", "Anime Broadcast")
        ep = airing_anime.get("next_airing_episode", episode)
        image = airing_anime.get("image") or ""
    return {
        "content": "📢 **New Episode Airing Alert!**",
        "embeds": [
            {
                "title": f"{title} - Episode {ep}",
                "description": f"Broadcast starting soon! Track your progress on [Otaku Orbit]({APP_URL})",
                "color": 16038143,
                "thumbnail": {"url": image} if image else None,
                "footer": {"text": f"Otaku Orbit v{APP_VERSION}"},
            }
        ],
    }


def generate_service_worker_js() -> str:
    return f"""// Otaku Orbit Offline Service Worker v{APP_VERSION}
const CACHE_NAME = 'otaku-orbit-cache-v{APP_VERSION}';
const ASSETS_TO_CACHE = [
  '/',
  '/manifest.json'
];

self.addEventListener('install', (event) => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
  self.skipWaiting();
}});

self.addEventListener('fetch', (event) => {{
  event.respondWith(
    caches.match(event.request).then((response) => response || fetch(event.request))
  );
}});
"""


def get_filler_guide(title: str) -> dict[str, Any] | None:
    norm_title = title.strip().lower()
    for series_name, guide in FILLER_GUIDES.items():
        if series_name.lower() in norm_title or norm_title in series_name.lower():
            total = guide.get("total", 0)
            filler_eps = []
            for start, end in guide.get("filler", []):
                filler_eps.extend(range(start, end + 1))
            filler_pct = round((len(filler_eps) / max(1, total)) * 100, 1)
            return {
                "series": series_name,
                "total": total,
                "filler_episodes": set(filler_eps),
                "filler_ranges": guide.get("filler", []),
                "canon_ranges": guide.get("canon", []),
                "filler_count": len(filler_eps),
                "filler_percentage": filler_pct,
                "tip": guide.get("tip", ""),
            }
    return None


def is_episode_filler(title: str, episode: int) -> bool:
    guide = get_filler_guide(title)
    if not guide:
        return False
    return episode in guide["filler_episodes"]


def get_next_canon_episode(title: str, current_episode: int) -> int:
    guide = get_filler_guide(title)
    if not guide:
        return current_episode + 1
    next_ep = current_episode + 1
    total = guide.get("total", 2000)
    while next_ep in guide["filler_episodes"] and next_ep <= total:
        next_ep += 1
    return next_ep


def search_by_vibe(query: str, catalogue: list[dict[str, Any]], top_k: int = 15) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return catalogue[:top_k]
    tokens = [t.lower() for t in re.findall(r"\w+", query.strip()) if len(t) >= 3]
    if not tokens:
        return catalogue[:top_k]

    scored = []
    for anime in catalogue:
        title = display_title(anime).lower()
        desc = (clean_description(anime.get("description") or "")).lower()
        genres = [g.lower() for g in anime.get("genres", [])]
        studio_info = anime.get("studios", {})
        studios = []
        if isinstance(studio_info, dict):
            studios = [n.get("name", "").lower() for n in studio_info.get("nodes", []) if isinstance(n, dict)]

        score = 0
        for token in tokens:
            if token in title:
                score += 10
            if token in genres:
                score += 6
            if any(token in s for s in studios):
                score += 5
            if token in desc:
                score += 2

        if score > 0:
            scored.append((score, anime))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_k]]


def match_anime_by_trope(trope_name: str, catalogue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trope_info = CHARACTER_TROPES.get(trope_name)
    if not trope_info:
        return catalogue
    target_genres = set(g.lower() for g in trope_info.get("genres", []))
    results = []
    for anime in catalogue:
        genres = [g.lower() for g in anime.get("genres", [])]
        if any(g in target_genres for g in genres):
            results.append(anime)
    return results


def calculate_backlog_priority(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    planning = [r for r in rows if r.get("status") in {"PLANNING", "WATCHING"}]
    if not planning:
        return list(rows)

    def priority_score(item: dict[str, Any]) -> float:
        score = float(item.get("user_score") or item.get("score") or 70)
        eps = item.get("episodes") or 12
        length_penalty = math.log10(max(1, eps)) * 2
        return score - length_penalty

    return sorted(planning, key=priority_score, reverse=True)


def detect_franchise_sequels(
    completed_titles: list[dict[str, Any]],
    all_catalogue: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    completed_names = {display_title(r).lower() for r in completed_titles}
    catalogue = all_catalogue or []
    detected = []
    franchise_keywords = [
        "fate",
        "steins;gate",
        "attack on titan",
        "demon slayer",
        "jujutsu kaisen",
        "sword art online",
        "my hero academia",
        "monogatari",
        "mob psycho",
        "konosuba",
    ]
    for c in completed_names:
        matched_kw = next((kw for kw in franchise_keywords if kw in c), None)
        if matched_kw:
            for item in catalogue:
                item_title = display_title(item).lower()
                if matched_kw in item_title and item_title not in completed_names:
                    detected.append(item)
    return detected[:10]


def generate_ambient_glow_css(accent_hex: str) -> str:
    color = accent_hex if accent_hex.startswith("#") else "#f4b8ff"
    return f"""<style>
    .stApp {{
        background: radial-gradient(circle at 50% -10%, {color}1a 0%, rgba(13, 11, 24, 0.98) 75%), #0a0a14 !important;
        background-attachment: fixed !important;
    }}
    .orbit-hero {{
        box-shadow: 0 10px 40px {color}28, 0 0 80px {color}14 !important;
        border-color: {color}44 !important;
    }}
    </style>"""


def create_custom_theme_palette(
    primary_hex: str,
    glow_rgba: str,
    metric_hex: str,
    sidebar_bg: str = "#121020",
) -> dict[str, str]:
    return {
        "primary": primary_hex.strip(),
        "glow": glow_rgba.strip(),
        "metric": metric_hex.strip(),
        "sidebar": sidebar_bg.strip(),
    }


def generate_cinematic_modal_html(anime: dict[str, Any]) -> str:
    title = display_title(anime)
    banner = banner_image_url(anime) or cover_image_url(anime) or ""
    score = anime.get("averageScore") or anime.get("score") or "N/A"
    episodes = anime.get("episodes") or "?"
    format_name = anime.get("format") or "TV"
    desc = clean_description(anime.get("description") or "No synopsis available.")
    return f"""<div style="position:relative;border-radius:24px;overflow:hidden;border:1px solid rgba(255,255,255,0.15);background:#0e0c1a;margin-bottom:1.5rem;">
  <div style="height:260px;background-image:url('{banner}');background-size:cover;background-position:center;position:relative;">
    <div style="position:absolute;inset:0;background:linear-gradient(to bottom, rgba(14,12,26,0.1) 0%, #0e0c1a 100%);"></div>
  </div>
  <div style="padding:1.5rem 2rem;position:relative;margin-top:-60px;">
    <span style="background:#f4b8ff22;color:#f4b8ff;padding:4px 12px;border-radius:12px;font-size:0.8rem;font-weight:700;border:1px solid #f4b8ff44;">{format_name} · {episodes} EPS · ⭐ {score}%</span>
    <h1 style="color:#ffffff;margin:0.5rem 0 0.8rem;font-size:2rem;font-weight:900;">{title}</h1>
    <p style="color:#b5b3c8;line-height:1.6;font-size:0.95rem;max-width:850px;">{html.escape(desc[:500])}...</p>
  </div>
</div>"""


def get_mini_dock_state(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    in_progress = [r for r in rows if r.get("status") in {"WATCHING", "REWATCHING"}]
    if not in_progress:
        return None
    latest = in_progress[0]
    title = latest.get("title", "Anime")
    cur = latest.get("progress", 0)
    total = latest.get("episodes") or cur or 12
    pct = int(min(100, max(0, (cur / max(1, total)) * 100)))
    return {
        "anime_id": latest.get("anime_id"),
        "title": title,
        "progress": cur,
        "total": total,
        "percentage": pct,
        "next_episode": cur + 1,
    }


def get_sound_effects_data_uris() -> dict[str, str]:
    # Ultra-short embedded base64 wav pings
    return {
        "click": "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=",
        "chime": "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=",
    }


def generate_anime_wrapped_data(rows: list[dict[str, Any]], history: list[dict[str, Any]]) -> dict[str, Any]:
    total_eps = sum(r.get("progress", 0) for r in rows)
    total_hours = (
        sum(
            min(r.get("progress", 0), r.get("episodes") or r.get("progress", 0)) * (r.get("duration") or 24)
            for r in rows
        )
        // 60
    )
    completed = [r for r in rows if r.get("status") == "COMPLETED"]

    genres: dict[str, int] = {}
    for r in rows:
        for g in (r.get("genres") or "").split(","):
            g = g.strip()
            if g:
                genres[g] = genres.get(g, 0) + 1
    top_genre = max(genres, key=genres.get) if genres else "Explorer"

    # Days of week analysis
    days_count: dict[str, int] = {}
    for h in history:
        try:
            dt = datetime.fromisoformat(h.get("watched_at", "2026-01-01"))
            day_name = dt.strftime("%A")
            days_count[day_name] = days_count.get(day_name, 0) + 1
        except Exception:
            pass
    peak_day = max(days_count, key=days_count.get) if days_count else "Saturday"

    # Select Archetype
    if "action" in top_genre.lower() or "sports" in top_genre.lower():
        archetype = ANIME_ARCHETYPES["The Shonen Champion"]
    elif "psychological" in top_genre.lower() or "mystery" in top_genre.lower():
        archetype = ANIME_ARCHETYPES["The Seinen Philosopher"]
    elif "slice of life" in top_genre.lower() or "comedy" in top_genre.lower():
        archetype = ANIME_ARCHETYPES["The Slice-of-Life Healer"]
    else:
        archetype = ANIME_ARCHETYPES["The Isekai Wanderer"]

    return {
        "total_episodes": total_eps,
        "total_hours": total_hours,
        "completed_count": len(completed),
        "top_genre": top_genre,
        "peak_day": peak_day,
        "archetype": archetype,
    }


def generate_anime_wrapped_svg(wrapped_data: dict[str, Any], username: str = "Otaku Traveler") -> str:
    eps = wrapped_data.get("total_episodes", 0)
    hours = wrapped_data.get("total_hours", 0)
    completed = wrapped_data.get("completed_count", 0)
    genre = wrapped_data.get("top_genre", "Action")
    peak_day = wrapped_data.get("peak_day", "Saturday")
    arch = wrapped_data.get("archetype", ANIME_ARCHETYPES["The Shonen Champion"])
    arch_title = arch["title"]
    arch_tag = arch["tagline"]
    arch_icon = arch["icon"]

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="900" viewBox="0 0 800 900">
  <defs>
    <linearGradient id="wrapBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#19102e"/>
      <stop offset="50%" stop-color="#0f0c1a"/>
      <stop offset="100%" stop-color="#05040a"/>
    </linearGradient>
    <linearGradient id="neonBar" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f4b8ff"/>
      <stop offset="50%" stop-color="#6f4cff"/>
      <stop offset="100%" stop-color="#00f0ff"/>
    </linearGradient>
  </defs>
  <rect width="800" height="900" rx="32" fill="url(#wrapBg)" stroke="rgba(244,184,255,0.3)" stroke-width="2"/>
  
  <text x="60" y="90" font-family="'Segoe UI', Roboto, sans-serif" font-size="34" font-weight="900" fill="url(#neonBar)">OTAKU ORBIT WRAPPED</text>
  <text x="60" y="125" font-family="'Segoe UI', Roboto, sans-serif" font-size="16" fill="#8c89a0" letter-spacing="2">ANNUAL VIEWING DOSSIER · {username.upper()}</text>

  <rect x="60" y="160" width="680" height="220" rx="20" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
  <circle cx="160" cy="270" r="60" fill="#241a45" stroke="url(#neonBar)" stroke-width="2"/>
  <text x="160" y="285" font-family="'Segoe UI', Roboto, sans-serif" font-size="50" text-anchor="middle">{arch_icon}</text>
  <text x="250" y="235" font-family="'Segoe UI', Roboto, sans-serif" font-size="13" fill="#8c89a0" letter-spacing="1.5">YOUR ANIME ARCHETYPE</text>
  <text x="250" y="275" font-family="'Segoe UI', Roboto, sans-serif" font-size="28" font-weight="800" fill="#ffffff">{arch_title}</text>
  <text x="250" y="310" font-family="'Segoe UI', Roboto, sans-serif" font-size="15" fill="#00f0ff">{arch_tag}</text>

  <g transform="translate(60, 420)">
    <rect width="325" height="130" rx="18" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
    <text x="24" y="42" font-family="'Segoe UI', Roboto, sans-serif" font-size="13" fill="#8c89a0">HOURS LOGGED</text>
    <text x="24" y="92" font-family="'Segoe UI', Roboto, sans-serif" font-size="36" font-weight="900" fill="#f4b8ff">{hours} hrs</text>
  </g>
  <g transform="translate(415, 420)">
    <rect width="325" height="130" rx="18" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
    <text x="24" y="42" font-family="'Segoe UI', Roboto, sans-serif" font-size="13" fill="#8c89a0">EPISODES WATCHED</text>
    <text x="24" y="92" font-family="'Segoe UI', Roboto, sans-serif" font-size="36" font-weight="900" fill="#00f0ff">{eps}</text>
  </g>
  
  <g transform="translate(60, 580)">
    <rect width="325" height="130" rx="18" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
    <text x="24" y="42" font-family="'Segoe UI', Roboto, sans-serif" font-size="13" fill="#8c89a0">COMPLETED SERIES</text>
    <text x="24" y="92" font-family="'Segoe UI', Roboto, sans-serif" font-size="36" font-weight="900" fill="#00ff88">{completed}</text>
  </g>
  <g transform="translate(415, 580)">
    <rect width="325" height="130" rx="18" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
    <text x="24" y="42" font-family="'Segoe UI', Roboto, sans-serif" font-size="13" fill="#8c89a0">PEAK BINGE DAY</text>
    <text x="24" y="92" font-family="'Segoe UI', Roboto, sans-serif" font-size="32" font-weight="900" fill="#ffbf7f">{peak_day}</text>
  </g>

  <rect x="60" y="740" width="680" height="90" rx="18" fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.08)"/>
  <text x="30" y="40" transform="translate(60, 740)" font-family="'Segoe UI', Roboto, sans-serif" font-size="13" fill="#8c89a0">DOMINANT GENRE</text>
  <text x="30" y="68" transform="translate(60, 740)" font-family="'Segoe UI', Roboto, sans-serif" font-size="22" font-weight="800" fill="#ffffff">#1 Affinity: {genre}</text>
</svg>"""


def evaluate_fantasy_score(predictions: list[dict[str, Any]], actual_rankings: dict[int, int]) -> int:
    total_points = 0
    for p in predictions:
        aid = p.get("anime_id")
        pred_rank = p.get("predicted_rank", 1)
        if aid in actual_rankings:
            diff = abs(pred_rank - actual_rankings[aid])
            if diff == 0:
                total_points += 100
            elif diff == 1:
                total_points += 60
            elif diff == 2:
                total_points += 30
            elif diff <= 4:
                total_points += 10
    return total_points


def generate_bujo_tracker_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 📓 Otaku Orbit Bullet Journal Watch Tracker",
        f"> Generated on {date.today().isoformat()} · Track your offline journey",
        "",
        "| Status | Anime Title | Progress Checkbox | Rating | Notes & Highlights |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for r in rows:
        title = r.get("title", "Anime")
        cur = r.get("progress", 0)
        tot = r.get("episodes") or cur
        status = r.get("status", "PLANNING")
        stars = "★" * int(min(5, max(1, (r.get("user_score") or 80) // 20)))
        boxes = f"[{cur}/{tot}] [ ] [ ] [ ]"
        lines.append(f"| {status} | **{title}** | {boxes} | {stars} | |")
    return "\n".join(lines)


def generate_bujo_tracker_html(rows: list[dict[str, Any]]) -> str:
    items_html = []
    for r in rows:
        title = html.escape(r.get("title", "Anime"))
        cur = r.get("progress", 0)
        tot = r.get("episodes") or "?"
        status = r.get("status", "PLANNING")
        items_html.append(f"""<div style="border:1px solid #333;border-radius:12px;padding:12px;margin-bottom:12px;page-break-inside:avoid;">
  <div style="display:flex;justify-content:space-between;font-weight:bold;">
    <span>{title}</span>
    <span>[{status}] {cur} / {tot}</span>
  </div>
  <div style="margin-top:8px;font-size:14px;color:#666;">
    Progress: [ ] [ ] [ ] [ ] [ ] &nbsp;&nbsp;&nbsp;&nbsp; Rating: [ ★ ★ ★ ★ ★ ]
  </div>
  <div style="margin-top:8px;border-bottom:1px dashed #ccc;height:18px;"></div>
</div>""")
    return f"""<!DOCTYPE html>
<html>
<head><title>Otaku Orbit Printable Tracker</title></head>
<body style="font-family:'Segoe UI',Roboto,sans-serif;max-width:800px;margin:2rem auto;padding:1rem;">
  <h2>📓 Otaku Orbit - Bullet Journal Watchlist</h2>
  {"".join(items_html)}
</body>
</html>"""


def get_tier_list_template(template_name: str) -> dict[str, str]:
    return TIER_LIST_TEMPLATES.get(template_name, TIER_LIST_TEMPLATES["All-Time Masterpieces"])


def generate_watch_party_sync_link(anime_id: int, title: str, episode: int, timestamp_sec: int = 0) -> str:
    q = quote(title)
    return f"{APP_URL}?party=1&anime_id={anime_id}&title={q}&ep={episode}&ts={timestamp_sec}"


def parse_watch_party_sync_link(query_or_url: str) -> dict[str, Any]:
    parsed = urlparse(query_or_url)
    qs = parsed.query if parsed.query else query_or_url.lstrip("?")
    params: dict[str, Any] = {}
    for part in qs.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    try:
        aid = int(params.get("anime_id", 0))
    except ValueError:
        aid = 0
    try:
        ep = int(params.get("ep", 1))
    except ValueError:
        ep = 1
    return {
        "is_party": params.get("party") == "1",
        "anime_id": aid,
        "title": params.get("title", "Anime Party"),
        "episode": ep,
        "timestamp_sec": int(params.get("ts", 0)),
    }


def calculate_studio_loyalty_index(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    studio_map: dict[str, dict[str, Any]] = {}
    for r in rows:
        # Infer studio from tag, notes, or mock mapping
        studios = ["Ufotable", "MAPPA", "Bones", "Kyoto Animation", "Madhouse", "Wit Studio", "CloverWorks"]
        title_lower = (r.get("title") or "").lower()
        matched_studio = "Independent / Other"
        for s in studios:
            if s.lower() in title_lower or s.lower() in (r.get("notes") or "").lower():
                matched_studio = s
                break
        if matched_studio not in studio_map:
            studio_map[matched_studio] = {"titles_count": 0, "total_eps": 0, "scores": []}
        studio_map[matched_studio]["titles_count"] += 1
        studio_map[matched_studio]["total_eps"] += r.get("progress", 0)
        if r.get("user_score"):
            studio_map[matched_studio]["scores"].append(r["user_score"])

    results = {}
    for s, data in studio_map.items():
        avg_score = round(sum(data["scores"]) / len(data["scores"]), 1) if data["scores"] else None
        results[s] = {
            "titles": data["titles_count"],
            "episodes": data["total_eps"],
            "avg_score": avg_score,
        }
    return results


def calculate_seiyuu_screen_time(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actor_time: dict[str, int] = {}
    for r in rows:
        eps = r.get("progress", 0)
        dur = r.get("duration", 24)
        seiyuu_list = extract_characters_and_seiyuu(r)
        if not seiyuu_list and r.get("characters_json"):
            try:
                raw = json.loads(r["characters_json"])
                if isinstance(raw, list):
                    seiyuu_list = raw
            except Exception:
                pass
        for item in seiyuu_list:
            name = (item.get("seiyuu") or item.get("actor") or item.get("voice_actor") or "").strip()
            if name and name != "Unknown":
                actor_time[name] = actor_time.get(name, 0) + (eps * dur)

    sorted_actors = sorted(actor_time.items(), key=lambda x: x[1], reverse=True)
    return [{"actor": a, "hours": round(mins / 60, 1), "minutes": mins} for a, mins in sorted_actors[:10]]


def calculate_drop_off_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dropped = [r for r in rows if r.get("status") == "DROPPED"]
    total = len(rows)
    drop_count = len(dropped)
    if not dropped:
        return {
            "dropped_count": 0,
            "drop_rate_pct": 0.0,
            "rule_of_three_pct": 0.0,
            "median_drop_episode": 0,
        }

    three_ep_drops = sum(1 for r in dropped if r.get("progress", 0) <= 3)
    rule_of_three_pct = round((three_ep_drops / max(1, drop_count)) * 100, 1)
    progress_list = sorted(r.get("progress", 0) for r in dropped)
    median_ep = progress_list[len(progress_list) // 2]
    return {
        "dropped_count": drop_count,
        "drop_rate_pct": round((drop_count / max(1, total)) * 100, 1),
        "rule_of_three_pct": rule_of_three_pct,
        "median_drop_episode": median_ep,
    }


def calculate_era_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    era_counts = {k: 0 for k in HISTORICAL_ERAS.keys()}
    for r in rows:
        airing = r.get("next_airing_at") or 0
        dt = datetime.fromtimestamp(airing) if airing > 0 else datetime.now()
        year = dt.year
        for era_name, (start_yr, end_yr) in HISTORICAL_ERAS.items():
            if start_yr <= year <= end_yr:
                era_counts[era_name] += 1
                break
    return era_counts


def evaluate_pacing_alert(history: list[dict[str, Any]], weekly_goal: int = 10) -> dict[str, Any]:
    now = datetime.now()
    watched_last_7 = sum(
        1 for h in history if (now - datetime.fromisoformat(h.get("watched_at", "2000-01-01"))).days <= 7
    )
    diff = watched_last_7 - weekly_goal
    if diff >= 2:
        status = "ahead"
        tip = f"⚡ Saiyan Turbo Mode: You are {diff} episodes ahead of your weekly goal!"
    elif diff >= -1:
        status = "on_track"
        tip = "🎯 Perfectly Balanced: You are right on target to hit your goal."
    else:
        status = "behind"
        tip = f"💤 Time to Binge: You are {abs(diff)} episodes behind your target."

    return {
        "status": status,
        "watched_this_week": watched_last_7,
        "goal": weekly_goal,
        "delta": diff,
        "message": tip,
    }


def generate_custom_webhook_payload(
    event: str, anime: dict[str, Any], username: str = "Otaku Orbit User"
) -> dict[str, Any]:
    title = display_title(anime) if isinstance(anime, dict) else str(anime)
    return {
        "event": event,
        "timestamp": datetime.now().isoformat(),
        "user": username,
        "anime": {
            "title": title,
            "status": anime.get("status") if isinstance(anime, dict) else "COMPLETED",
            "progress": anime.get("progress") if isinstance(anime, dict) else 12,
            "score": anime.get("user_score") if isinstance(anime, dict) else 100,
        },
    }


def generate_direct_sync_request(service: str, token: str, action: str, data: dict[str, Any]) -> dict[str, Any]:
    service_clean = service.lower().strip()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": f"OtakuOrbit/{APP_VERSION}",
    }
    url = "https://graphql.anilist.co" if service_clean == "anilist" else "https://api.myanimelist.net/v2"
    return {
        "method": "POST",
        "url": url,
        "headers": headers,
        "action": action,
        "payload": data,
    }


def prepare_gist_backup_payload(
    rows: list[dict[str, Any]], filename: str = "otaku_orbit_backup.json"
) -> dict[str, Any]:
    return {
        "description": f"Otaku Orbit Automated Database Backup v{APP_VERSION}",
        "public": False,
        "files": {
            filename: {
                "content": export_watchlist(rows),
            }
        },
    }


def generate_watchlist_rss_feed(
    rows: list[dict[str, Any]], base_url: str = "https://otaku-orbit.streamlit.app/"
) -> str:
    now_rfc = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []
    for r in rows:
        title = html.escape(display_title(r))
        ep = r.get("next_airing_episode") or (r.get("progress", 0) + 1)
        airing_ts = r.get("next_airing_at") or 0
        pub_date = (
            datetime.fromtimestamp(airing_ts).strftime("%a, %d %b %Y %H:%M:%S +0000") if airing_ts > 0 else now_rfc
        )
        items.append(f"""    <item>
      <title>{title} - Episode {ep}</title>
      <link>{base_url}</link>
      <guid>{base_url}#anime-{r.get("anime_id", 0)}-ep-{ep}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>Episode {ep} broadcast update for {title}.</description>
    </item>""")

    items_block = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Otaku Orbit Airing Watchlist Feed</title>
    <link>{base_url}</link>
    <description>Upcoming anime broadcasts tracked in Otaku Orbit.</description>
    <lastBuildDate>{now_rfc}</lastBuildDate>
{items_block}
  </channel>
</rss>"""
