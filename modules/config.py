from __future__ import annotations

import os
from pathlib import Path
from typing import Any


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
APP_VERSION = "1.8.0"
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
CUSTOM_SHELVES = [
    "Favorites",
    "Masterpiece",
    "Seasonal Priority",
    "Classic Hall of Fame",
    "Casual & Cozy",
    "Guilty Pleasures",
]
MEDIA_SUBTYPES = ["TV", "MOVIE", "OVA", "ONA", "SPECIAL", "ANIME", "MANGA", "MANHWA", "LIGHT_NOVEL"]
BACKUP_FORMAT_VERSION = 1
SUPPORTED_TIMEZONES = [
    "UTC",
    "Asia/Kolkata",
    "America/New_York",
    "Europe/London",
    "Asia/Tokyo",
    "Australia/Sydney",
]
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

ANIME_MOODS = {
    "Adrenaline & Hype": ["Action", "Sports"],
    "Tearjerker & Emotional": ["Drama", "Romance"],
    "Mind-Bending & Psychological": ["Psychological", "Mystery", "Sci-Fi"],
    "Brainless Comedy": ["Comedy", "Slice of Life"],
    "Dark & Gritty": ["Horror", "Thriller", "Psychological"],
    "Wholesome & Cozy": ["Slice of Life", "Fantasy"],
    "Cozy & Chill": ["Slice of Life", "Comedy"],
}

BINGO_CHALLENGES = [
    {"id": "b1", "text": "Watch a pre-2000s classic", "check": "pre_2000"},
    {"id": "b2", "text": "Complete a 50+ episode series", "check": "long_series"},
    {"id": "b3", "text": "Watch a Mecha show", "check": "genre_mecha"},
    {"id": "b4", "text": "Score a title 100/100", "check": "perfect_score"},
    {"id": "b5", "text": "Log a full rewatch cycle", "check": "rewatch"},
    {"id": "b6", "text": "Watch an anime movie", "check": "format_movie"},
    {"id": "b7", "text": "Log 3 days in a row", "check": "streak_3"},
    {"id": "b8", "text": "Explore a Music anime", "check": "genre_music"},
    {"id": "b9", "text": "Watch an original anime", "check": "source_original"},
    {"id": "b10", "text": "Rate 10 or more titles", "check": "rated_10"},
    {"id": "b11", "text": "Watch a Psychological show", "check": "genre_psychological"},
    {"id": "b12", "text": "Track a Manga or Manhwa", "check": "tracked_manga"},
    {"id": "b13", "text": "FREE SPACE (Otaku Orbit)", "check": "free_space"},
    {"id": "b14", "text": "Complete 5 distinct series", "check": "completed_5"},
    {"id": "b15", "text": "Log 25 total episodes", "check": "episodes_25"},
    {"id": "b16", "text": "Watch a Kyoto Animation show", "check": "studio_kyoani"},
    {"id": "b17", "text": "Watch a MAPPA show", "check": "studio_mappa"},
    {"id": "b18", "text": "Watch an Ufotable show", "check": "studio_ufotable"},
    {"id": "b19", "text": "Add 5 custom tags", "check": "tagged_5"},
    {"id": "b20", "text": "Watch a Sports anime", "check": "genre_sports"},
    {"id": "b21", "text": "Binge 5 episodes in a day", "check": "binge_5"},
    {"id": "b22", "text": "Watch an Isekai fantasy", "check": "genre_fantasy"},
    {"id": "b23", "text": "Watch a Romance title", "check": "genre_romance"},
    {"id": "b24", "text": "Watch a Sci-Fi series", "check": "genre_scifi"},
    {"id": "b25", "text": "Export a backup file", "check": "backup_ready"},
]

FRANCHISE_WATCH_ORDERS: dict[str, dict[str, Any]] = {
    "Fate": {
        "release": [
            "Fate/stay night (2006)",
            "Fate/Zero (2011)",
            "Fate/stay night: Unlimited Blade Works (2014)",
            "Fate/stay night: Heaven's Feel (2017-2020)",
        ],
        "chronological": [
            "Fate/Zero",
            "Fate/stay night (UBW or Heaven's Feel)",
            "Fate/Apocrypha (Alternate)",
            "Fate/Grand Order (Spin-off)",
        ],
        "tip": "Start with Fate/Zero or Unlimited Blade Works for optimal setup.",
    },
    "Monogatari": {
        "release": [
            "Bakemonogatari",
            "Nisemonogatari",
            "Nekomonogatari (Black)",
            "Monogatari Series: Second Season",
            "Hanamonogatari",
            "Tsukimonogatari",
            "Owarimonogatari",
            "Kizumonogatari",
        ],
        "chronological": [
            "Kizumonogatari (I-III)",
            "Nekomonogatari (Black)",
            "Bakemonogatari",
            "Nisemonogatari",
            "Monogatari Series: Second Season",
            "Tsukimonogatari",
            "Owarimonogatari",
            "Hanamonogatari",
        ],
        "tip": "Novel order (Kizumonogatari right after Bakemonogatari) provides maximum narrative coherence.",
    },
    "Steins;Gate": {
        "release": [
            "Steins;Gate (Episodes 1-24)",
            "Steins;Gate: Egoistic Poriomania (OVA)",
            "Steins;Gate: The Movie - Load Region of Déjà Vu",
            "Steins;Gate 23β",
            "Steins;Gate 0",
        ],
        "chronological": [
            "Steins;Gate (Episodes 1-22)",
            "Steins;Gate 23β",
            "Steins;Gate 0",
            "Steins;Gate (Episodes 23-24)",
            "Egoistic Poriomania",
            "Load Region of Déjà Vu",
        ],
        "tip": "First-time watchers should follow release order to preserve the original climax.",
    },
    "Attack on Titan": {
        "release": [
            "Season 1",
            "Season 2",
            "Season 3 (Part 1 & 2)",
            "The Final Season (Part 1, 2, & Specials)",
        ],
        "chronological": [
            "Season 1",
            "Ilse's Notebook (OVA)",
            "Season 2",
            "No Regrets (Levi OVA)",
            "Season 3",
            "The Final Season",
        ],
        "tip": "Watch Levi's backstory OVA (No Regrets) before Season 3 for deeper character resonance.",
    },
}
