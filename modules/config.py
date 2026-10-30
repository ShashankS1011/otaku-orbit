from __future__ import annotations

import os
from pathlib import Path


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
APP_VERSION = "1.7.0"
APP_URL = "https://otaku-orbit.streamlit.app/"
SUPPORT_LINK = "https://discord.com/channels/@me/1252520070043668561/1562171196617785464"
AUTHOR_CREDIT = "Made by Shashank — powered by Saiyan spirit"
API_URL = os.getenv("ANILIST_API_URL", "https://graphql.anilist.co")
DB_PATH = Path(os.getenv("OTAKU_ORBIT_DB_PATH", Path(__file__).parents[1] / "anime_companion.db"))
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
        "accent": "#bd93f9",
    },
    "Cyberpunk Cyan": {
        "primary": "#00f0ff",
        "glow": "rgba(0,180,255,.32)",
        "metric": "#00f0ff",
        "sidebar": "linear-gradient(180deg, #101c2e 0%, #0a0e17 100%)",
        "accent": "#00d2ff",
    },
    "Sunset Flame": {
        "primary": "#ff8447",
        "glow": "rgba(255,46,147,.32)",
        "metric": "#ff8447",
        "sidebar": "linear-gradient(180deg, #24111e 0%, #140a12 100%)",
        "accent": "#ff4b4b",
    },
    "Emerald Matrix": {
        "primary": "#00ff88",
        "glow": "rgba(0,255,136,.32)",
        "metric": "#00ff88",
        "sidebar": "linear-gradient(180deg, #102419 0%, #0a140f 100%)",
        "accent": "#00d470",
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

ANILIST_STATUS_MAP = {
    "CURRENT": "WATCHING",
    "COMPLETED": "COMPLETED",
    "PLANNING": "PLANNING",
    "DROPPED": "DROPPED",
    "PAUSED": "PAUSED",
    "REPEATING": "REWATCHING",
}
