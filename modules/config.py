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
APP_VERSION = "1.9.0"
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


FILLER_GUIDES: dict[str, dict[str, Any]] = {
    "Naruto": {
        "total": 220,
        "canon": [(1, 25), (27, 96), (98, 100), (107, 135), (220, 220)],
        "filler": [(26, 26), (97, 97), (101, 106), (136, 219)],
        "tip": "Episodes 136-219 are non-canon standalone missions. You can safely jump to Episode 220 or directly into Naruto Shippuden.",
    },
    "Naruto: Shippuden": {
        "total": 500,
        "canon": [
            (1, 56),
            (72, 90),
            (113, 143),
            (152, 169),
            (172, 175),
            (197, 222),
            (243, 256),
            (261, 270),
            (272, 278),
            (282, 283),
            (296, 302),
            (321, 346),
            (362, 375),
            (378, 387),
            (391, 393),
            (414, 415),
            (418, 421),
            (424, 426),
            (451, 463),
            (470, 479),
            (484, 500),
        ],
        "filler": [
            (57, 71),
            (91, 112),
            (144, 151),
            (170, 171),
            (176, 196),
            (223, 242),
            (257, 260),
            (271, 271),
            (279, 281),
            (284, 295),
            (303, 320),
            (347, 361),
            (376, 377),
            (388, 390),
            (394, 413),
            (416, 417),
            (422, 423),
            (427, 450),
            (464, 469),
            (480, 483),
        ],
        "tip": "The Kakashi Anbu arc (Episodes 349-361) is mixed canon and widely acclaimed by fans.",
    },
    "Bleach": {
        "total": 366,
        "canon": [
            (1, 32),
            (34, 49),
            (51, 63),
            (110, 127),
            (138, 146),
            (150, 167),
            (190, 203),
            (206, 212),
            (215, 227),
            (267, 286),
            (288, 297),
            (300, 302),
            (306, 310),
            (343, 354),
            (356, 366),
        ],
        "filler": [
            (33, 33),
            (50, 50),
            (64, 109),
            (128, 137),
            (147, 149),
            (168, 189),
            (204, 205),
            (213, 214),
            (228, 266),
            (287, 287),
            (298, 299),
            (303, 305),
            (311, 342),
            (355, 355),
        ],
        "tip": "The Bount Arc (Episodes 64-109) can be skipped entirely without affecting the Arrancar storyline.",
    },
    "One Piece": {
        "total": 1100,
        "canon": [
            (1, 53),
            (62, 97),
            (100, 101),
            (103, 130),
            (144, 195),
            (207, 219),
            (227, 278),
            (284, 316),
            (320, 325),
            (337, 381),
            (385, 425),
            (430, 456),
            (459, 491),
            (493, 541),
            (543, 574),
            (579, 589),
            (591, 625),
            (629, 746),
            (751, 779),
            (783, 894),
            (897, 906),
            (908, 1028),
            (1031, 1100),
        ],
        "filler": [
            (54, 61),
            (98, 99),
            (102, 102),
            (131, 143),
            (196, 206),
            (220, 226),
            (279, 283),
            (317, 319),
            (326, 336),
            (382, 384),
            (426, 429),
            (457, 458),
            (492, 492),
            (542, 542),
            (575, 578),
            (590, 590),
            (626, 628),
            (747, 750),
            (780, 782),
            (895, 896),
            (907, 907),
            (1029, 1030),
        ],
        "tip": "The G-8 Marine Base arc (Episodes 196-206) is widely celebrated as one of the best anime fillers in history.",
    },
    "Gintama": {
        "total": 367,
        "canon": [
            (3, 49),
            (51, 56),
            (58, 74),
            (76, 81),
            (83, 99),
            (101, 105),
            (107, 113),
            (115, 119),
            (121, 123),
            (126, 134),
            (136, 136),
            (138, 149),
            (151, 154),
            (156, 163),
            (165, 165),
            (167, 170),
            (172, 172),
            (175, 175),
            (177, 184),
            (186, 188),
            (190, 208),
            (210, 251),
            (253, 367),
        ],
        "filler": [
            (1, 2),
            (50, 50),
            (57, 57),
            (75, 75),
            (82, 82),
            (100, 100),
            (106, 106),
            (114, 114),
            (120, 120),
            (124, 125),
            (135, 135),
            (137, 137),
            (150, 150),
            (155, 155),
            (164, 164),
            (166, 166),
            (171, 171),
            (173, 174),
            (176, 176),
            (185, 185),
            (189, 189),
            (209, 209),
            (252, 252),
        ],
        "tip": "Even Gintama filler episodes contain legendary self-aware parody writing, so consider watching them!",
    },
    "Dragon Ball Z": {
        "total": 291,
        "canon": [
            (1, 8),
            (11, 11),
            (17, 38),
            (45, 99),
            (101, 101),
            (103, 107),
            (118, 123),
            (126, 169),
            (172, 173),
            (175, 194),
            (200, 201),
            (205, 273),
            (275, 287),
            (289, 291),
        ],
        "filler": [
            (9, 10),
            (12, 16),
            (39, 44),
            (100, 100),
            (102, 102),
            (108, 117),
            (124, 125),
            (170, 171),
            (174, 174),
            (195, 199),
            (202, 204),
            (274, 274),
            (288, 288),
        ],
        "tip": "Episode 125 features Goku and Piccolo taking their driver license test and is a beloved classic comedy episode.",
    },
}

CHARACTER_TROPES: dict[str, dict[str, Any]] = {
    "Rivalry Duo": {
        "desc": "Intense rivalry, mutual respect, and legendary clashes (e.g. Goku/Vegeta, Naruto/Sasuke, Deku/Bakugo).",
        "genres": ["Action", "Shounen", "Sports"],
    },
    "Tsundere Romance": {
        "desc": "Spiky on the outside, affectionate on the inside (e.g. Toradora, Steins;Gate).",
        "genres": ["Romance", "Comedy"],
    },
    "Master & Apprentice": {
        "desc": "Wise mentor training an underdog to inherit their legacy (e.g. All Might/Deku, Roshi/Goku, Jiraiya/Naruto).",
        "genres": ["Action", "Adventure", "Fantasy"],
    },
    "Found Family": {
        "desc": "Outcasts banding together and forging bonds stronger than blood (e.g. One Piece, Spy x Family).",
        "genres": ["Slice of Life", "Adventure", "Fantasy"],
    },
    "Overpowered Protagonist": {
        "desc": "Ridiculously strong heroes wiping the floor with arrogant villains (e.g. One Punch Man, Solo Leveling, Overlord).",
        "genres": ["Action", "Fantasy", "Supernatural"],
    },
    "Revenge Quest": {
        "desc": "Cold, calculated pursuit of vengeance against impossible odds (e.g. Vinland Saga, Attack on Titan, 91 Days).",
        "genres": ["Action", "Drama", "Psychological"],
    },
    "Tournament Arc": {
        "desc": "High-stakes battles, brackets, and signature power escalations (e.g. Hunter x Hunter, My Hero Academia, Yu Yu Hakusho).",
        "genres": ["Action", "Sports", "Supernatural"],
    },
    "Mind Games & 300 IQ": {
        "desc": "Multi-layered battle of wits, deduction, and deception (e.g. Death Note, Code Geass, Monster).",
        "genres": ["Psychological", "Mystery", "Thriller"],
    },
}

TIER_LIST_TEMPLATES: dict[str, dict[str, str]] = {
    "All-Time Masterpieces": {
        "S": "God Tier (10/10)",
        "A": "Masterpiece (9/10)",
        "B": "Great Watch (8/10)",
        "C": "Decent / Fun (7/10)",
        "D": "Mid or Skip (<6/10)",
    },
    "Opening Themes (OST)": {
        "S": "Legendary Banger",
        "A": "Daily Repeat",
        "B": "Solid Vibe",
        "C": "Average",
        "D": "Skip Intro",
    },
    "Antagonists & Villains": {
        "S": "Peak Menace",
        "A": "Compelling & Complex",
        "B": "Solid Threat",
        "C": "Forgettable",
        "D": "Clown Tier",
    },
    "Emotional Impact": {
        "S": "Emotional Devastation",
        "A": "Heavy Tears",
        "B": "Touchy & Heartfelt",
        "C": "Mild Chills",
        "D": "Felt Nothing",
    },
}

HISTORICAL_ERAS: dict[str, tuple[int, int]] = {
    "80s Retro Classics": (1980, 1989),
    "90s Golden Age": (1990, 1999),
    "2000s Renaissance": (2000, 2009),
    "2010s Modern Boom": (2010, 2019),
    "2020s Next-Gen Era": (2020, 2030),
}

ANIME_ARCHETYPES: dict[str, dict[str, str]] = {
    "The Shonen Champion": {
        "title": "The Shonen Champion",
        "tagline": "Fuelled by grit, rivalries, and limitless power surges.",
        "icon": "🔥",
    },
    "The Seinen Philosopher": {
        "title": "The Seinen Philosopher",
        "tagline": "Drawn to psychological chess, moral ambiguity, and existential depths.",
        "icon": "🧠",
    },
    "The Slice-of-Life Healer": {
        "title": "The Slice-of-Life Healer",
        "tagline": "Searching for cozy warmth, heartwarming connections, and comfort food.",
        "icon": "🍵",
    },
    "The Isekai Wanderer": {
        "title": "The Isekai Wanderer",
        "tagline": "Exploring fantastical dimensions, magic systems, and guild quests.",
        "icon": "⚔️",
    },
}
