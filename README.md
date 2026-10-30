# Otaku Orbit

> **Your personal anime command centre — discover, track, and curate your next obsession.**

Welcome to the orbit, traveller. Whether you're ascending to Super Saiyan over weekly shonen tournament arcs, dissecting 300-IQ psychological mind games, crying into your ramen over heartbreaking slice-of-life finales, or hunting for forgotten 90s vintage gems, **Otaku Orbit** is your definitive anime battle-station. Engineered with Python and Streamlit, powered by the AniList GraphQL API, and styled with high-contrast glassmorphic neon aesthetics, it merges catalogue exploration, real-time broadcast schedules, canon filler guides, personal library tracking, and deep viewing analytics into an ultra-fast, ad-free command centre.

**Crafted by Shashank — powered by Saiyan spirit.**

[Open Otaku Orbit](https://otaku-orbit.streamlit.app/)

Current version: `1.9.0`

---

## Executive Overview

Otaku Orbit delivers a frictionless anime tracking experience with zero forced sign-ups, zero third-party tracking, and enterprise-grade privacy boundaries. Whether running as a lightweight personal desktop app or deployed to Streamlit Community Cloud with OIDC multi-user authentication, Otaku Orbit gives you full ownership of your data, library, and viewing history.

### Core Highlights

- **Modular Clean Architecture**: Refactored domain architecture cleanly decoupled across configuration (`modules.config`), database persistence (`modules.db`), AniList GraphQL integration (`modules.api`), domain business services (`modules.services`), and responsive presentation (`modules.ui`).
- **Glassmorphic Visual Design**: High-contrast modern glassmorphic interface with dynamic backdrop-blur filters, theme glow accents, card hover elevation transforms, and responsive mobile-first breakpoints.
- **Dynamic Ambient Glow**: Screen background ambient illumination adapting dynamically to cover artwork accents.
- **Curated Canon vs. Filler Guides**: Integrated filler episode detection and canon skip calculations for legendary long-runners (*Naruto, Bleach, One Piece, Gintama, DBZ*).
- **Semantic "Vibe & Premise" Search**: Query anime using natural descriptions (*e.g., "dark cyberpunk detective thriller", "cozy cafe romance"*) powered by keyword token scoring.
- **Character Tropes & Dynamic Chemistry**: Discover titles matching beloved archetypes (*Rivalry Duo, Tsundere Romance, Master & Apprentice, Found Family, 300-IQ Mind Games*).
- **Adaptive Backlog Prioritization**: Intelligent queue ranking balancing taste affinity, community rating, and episode pacing.
- **Spotify-Style "Anime Wrapped"**: Generate downloadable annual vector SVG dossiers detailing your total hours, top studios, peak binge days, and assigned anime archetype.
- **Anime Season Fantasy League**: Predict top seasonal rankings and earn prediction accuracy points as seasons conclude.
- **Printable Bullet Journal Watch Tracker**: Export formatted Markdown and printable HTML trackers with progress checkboxes and rating stars.
- **Franchise Chronological Roadmaps**: Step-by-step release order vs. chronological story timelines and viewing tips for major universes (*Fate*, *Monogatari*, *Steins;Gate*, *Attack on Titan*, etc.).
- **Studio Loyalty Radar & Seiyuu Screen-Time**: Deep insights breaking down which studios (*Ufotable, MAPPA, Bones, KyoAni*) and voice actors you watch the most.
- **The 3-Episode Rule & Drop-off Curves**: Analyze median drop points and drop rate percentages across your backlog.
- **Historical Era Chronology**: Breakdown of your anime journey across the 80s Retro, 90s Golden Age, 2000s Classics, 2010s Renaissance, and 2020s Modern eras.
- **Multi-Profile Household Switcher**: Switch effortlessly between distinct library profiles (*Default, Family / SFW, Manga Only*) with isolated storage.
- **Watch Party Synchronized Timestamps**: Generate synchronized sharing links with embedded episode and timestamp markers for co-watching.
- **Personal Watchlist RSS 2.0 Feed**: Subscribe to automated airing update feeds for titles in your active queue.
- **Comprehensive Ecosystem Sync**: Two-way export and import for Kitsu JSON, SIMKL CSV, MyAnimeList (MAL) XML, spreadsheet CSV with formula sanitization, and atomic JSON backups.
- **Cloud SQLite Snapshot (Zero Data Loss)**: Base64 export and restore of raw SQLite databases for zero data loss on cloud ephemeral instances.
- **Privacy & Security First**: Session-scoped guest data, optional per-user OIDC SQLite isolation, automated database migrations, and one-click data deletion.

---

## Architectural Stack

| Layer | Technologies & Specifications |
| :--- | :--- |
| **Frontend Framework** | Streamlit (Python 3.11, 3.12, 3.13) with glassmorphism CSS design system & backdrop filters |
| **Modular Architecture** | Clean domain modules (`modules.config`, `modules.db`, `modules.api`, `modules.services`, `modules.ui`) |
| **Upstream Data API** | AniList GraphQL API v2 with client-side TTL caching, rate-limit backoff, and retry jitter |
| **Persistence Engine** | SQLite 3 with composite indexes (`idx_watchlist_media_status`, `idx_watch_history_anime`) & WAL mode |
| **Security & Hardening** | Bandit static analysis, `pip-audit` CVE vulnerability scanning, formula injection escaping |
| **Linting & Formatting** | Ruff (fast static analysis, PEP 8 compliance, import sorting) |
| **Quality & Testing** | `pytest` test suite (115+ tests), Streamlit `AppTest`, Playwright mobile browser smoke tests |
| **CI / CD Pipelines** | GitHub Actions matrix test suite, CodeQL security analysis, release integrity verification |

---

## Feature Deep Dive

### 1. Discovery, Moods & Vibe Intelligence
- **Semantic "Vibe & Premise" Search**: Query using everyday descriptions to match thematic premises across synopses, genres, and studios.
- **Character Trope Filtering**: Explore anime curated by iconic relationship dynamics (*Rivalry Duo, Tsundere Romance, Master & Apprentice, Found Family*).
- **Curated Mood & Vibe Filter**: Filter catalogue titles by mood tags (*Cozy & Chill, Adrenaline & Hype, Dark & Gritty, Tearjerker, Brainless Comedy, Mind-Bending Sci-Fi*).
- **Wheel of Fortune Decision Maker**: Randomly spins your unwatched queue to break backlog analysis paralysis based on mood or runtime constraints.
- **Adaptive Backlog Prioritizer**: Ranks queued titles based on personal taste scores and episode pacing.

### 2. Media Modals & Canon Guides
- **Canon vs. Filler Episode Guides**: Detailed breakdown of canon vs. filler ranges with 1-click calculation of the next canon episode.
- **Chronological Franchise Watch Orders**: In-depth viewing guides for complex franchises with release vs chronological ordering.
- **Key Production Staff**: Discover directors, series composers, and character designers.
- **Legal Streaming Deeplinks**: Direct watch buttons for verified legal platforms (Crunchyroll, Netflix, Hulu, HIDIVE, etc.).
- **Character & Voice Actor Gallery**: Detailed portrait gallery of characters paired with Japanese voice actors (Seiyuu).
- **Theme Song Jukebox & Video Previews**: Direct music and video links to stream Opening, Ending, and OST tracks.
- **Anti-Spoiler Synopsis Masking**: Keeps key plot surprises hidden behind blur overlays until you choose to reveal them.

### 3. Airing Calendar, Countdown & Schedule Feeds
- **Weekly Schedule**: Aggregates upcoming episode broadcasts across seven days with countdown timers.
- **Local Timezone Conversion**: Automatically adapts UTC broadcast schedules into any configured local timezone.
- **Watchlist Badges & Countdown Ticker**: Highlights upcoming episodes for anime currently tracked in your personal library and displays a top alert banner for episodes broadcasting within 48 hours.
- **iCalendar (.ics) Export**: Export your personal airing schedule as an RFC 5545 standard `.ics` calendar file to subscribe via Google Calendar, Apple Calendar, or Outlook.
- **Personal Watchlist RSS 2.0 Feed**: Download or subscribe to an XML RSS feed of airing broadcast updates for your tracked anime.

### 4. Watchlist & Library Operations
- **Custom Shelves**: Organize your queue into customizable shelves (*Favorites, Masterpiece, Guilty Pleasure, etc.*) with batch updates.
- **Episode Notes & Timestamps**: Capture granular notes on every episode.
- **Lifecycle Statuses**: Track titles across Planning, Watching, Rewatching, Completed, Paused, and Dropped states.
- **Quick Episode Increment (+1)**: Single-click progress updates that automatically log to watch history.
- **Manga & Light Novel Mode**: Toggle between anime episodes and manga chapters/volumes seamlessly.
- **Rewatch Cycles**: Full tracking of repeat watches with start/finish timestamps.
- **Printable Bullet Journal Watch Tracker**: Download styled Markdown or printable HTML tracking sheets with checkboxes.

### 5. Analytics, Gamification & Social
- **Spotify-Style Anime Wrapped**: Download a shareable vector SVG card showcasing your annual anime dossier and assigned archetype.
- **Anime Season Fantasy League**: Lock in seasonal rank predictions and earn prediction accuracy points.
- **Otaku ID Passport Generator**: Download a shareable vector SVG card showcasing your anime level, favorite genres, and stats.
- **5x5 Anime Watch Bingo**: Interactive 25-challenge board evaluated against your real library.
- **Studio Loyalty & Seiyuu Screen-Time**: Visual breakdown of your most-watched animation studios and voice actors.
- **The 3-Episode Rule Analysis**: Statistics on your drop rates and median drop-off points.
- **Historical Era Chronology**: Breakdown of your library across vintage eras (*80s Retro, 90s Golden Age, 2000s Classics, 2010s Renaissance, 2020s Modern*).
- **Watch Party Synchronized Sharing**: Generate sync links with embedded timestamps for co-watching with friends.

### 6. Data Portability & Integrations
- **Cloud SQLite Database Snapshot**: Base64 database string backup and restore for zero data loss on ephemeral cloud deployments.
- **Multi-Profile Household Switcher**: Maintain separate libraries on a single device (*Default, Family / SFW, Manga Only*).
- **Kitsu & SIMKL Support**: Two-way export and import for Kitsu JSON and SIMKL CSV formats.
- **1-Click AniList Profile Sync**: Synchronize public anime libraries directly from AniList usernames.
- **MyAnimeList (MAL) XML Export**: Seamlessly migrate your watch history and scores to MyAnimeList or third-party ecosystem tools.
- **Spreadsheet CSV Export**: Export your complete library to CSV, hardened against spreadsheet formula injection (`=`, `@`, `+`, `-`).
- **Atomic JSON Backups**: Full snapshot export and import with backward-compatible schema validation.
- **Discord & Custom Webhook Payloads**: Generate formatted JSON embeds for publishing updates to Discord channels or home automation webhooks.

---

## Configuration & Environment Variables

Otaku Orbit can be configured via environment variables or Streamlit secrets (`.streamlit/secrets.toml`):

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ANILIST_API_URL` | String | `https://graphql.anilist.co` | Upstream AniList GraphQL endpoint |
| `OTAKU_ORBIT_DB_PATH` | Path | `otaku_orbit.db` | Target path for SQLite database file |
| `OTAKU_ORBIT_CACHE_TTL` | Integer | `900` | In-memory cache duration in seconds (15 minutes) |
| `OTAKU_ORBIT_REQUEST_TIMEOUT` | Float | `10.0` | HTTP request timeout in seconds |
| `OTAKU_ORBIT_REQUEST_ATTEMPTS` | Integer | `3` | Maximum HTTP retry attempts with exponential backoff |

For multi-user deployments with OpenID Connect (OIDC), reference the template in `.streamlit/secrets.toml.example`.

---

## Local Development & Setup

### Prerequisites
- Python 3.11, 3.12, or 3.13
- Git

### Installation

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/ShashankS1011/otaku-orbit.git
   cd "otaku-orbit"
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   # Windows PowerShell:
   py -3.11 -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS:
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install development dependencies:**
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements-dev.txt
   ```

4. **Run the application:**
   ```powershell
   streamlit run app.py
   ```
   The local application will launch at `http://localhost:8501`.

---

## Quality Assurance & Automated Testing

Otaku Orbit maintains a comprehensive test suite covering database operations, API resilience, schema migrations, and frontend rendering:

```powershell
# Run the unit and integration test suite (115+ tests):
python -m pytest -q tests/test_app.py

# Verify Python syntax compilation:
python -m py_compile app.py modules/config.py modules/db.py modules/api.py modules/services.py modules/ui.py modules/__init__.py

# Run static linting and import checks:
python -m ruff check app.py modules tests

# Verify code formatting:
python -m ruff format --check app.py modules tests

# Run mobile browser smoke tests (requires Playwright Chromium):
python -m playwright install --with-deps chromium
python -m pytest -q tests/test_mobile_browser.py
```

### Continuous Integration (CI/CD)

The GitHub Actions workflow suite runs on all pushes and pull requests:
- **`ci.yml`**: Executes the test suite, Ruff linting, and formatting checks across Python 3.11, 3.12, and 3.13, alongside mobile browser emulation.
- **`security.yml`**: Runs `pip-audit` dependency vulnerability scanning and Bandit static analysis.
- **`release-check.yml`**: Enforces strict semantic version consistency across `app.py`, `README.md`, and `CHANGELOG.md`.
- **`codeql.yml`**: GitHub Advanced Security static code analysis for Python.

---

## Streamlit Community Cloud Deployment

To deploy Otaku Orbit to Streamlit Community Cloud:

1. Connect your GitHub repository to Streamlit Community Cloud.
2. Configure the deployment settings:
   - **Repository:** `ShashankS1011/otaku-orbit`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **Custom subdomain:** `otaku-orbit` (resulting in `otaku-orbit.streamlit.app`)
3. If enabling OIDC authentication, populate your client ID and secret in the Streamlit Cloud **Secrets** management panel using `.streamlit/secrets.toml.example` as a reference.

---

## Release Process & Versioning

Otaku Orbit strictly follows semantic versioning (`MAJOR.MINOR.PATCH`):
- **Major**: Breaking architectural changes or backwards-incompatible database schemas.
- **Minor**: Significant new features, layout enhancements, and export formats.
- **Patch**: Bug fixes, performance optimizations, and dependency maintenance.

### Release Checklist
1. Increment `APP_VERSION` in `app.py`.
2. Add a comprehensive release entry to `CHANGELOG.md` under the matching version heading.
3. Synchronize `Current version: \`X.Y.Z\`` in `README.md`.
4. Validate that all local tests and lint checks pass.
5. Create a release pull request; merging to `main` triggers automated version verification.

---

## License

Otaku Orbit is open-source software licensed under the MIT License.
