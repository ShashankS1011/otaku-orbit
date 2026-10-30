# Otaku Orbit

> **Your personal anime command centre — discover, track, and curate your next obsession.**

Otaku Orbit is an anime intelligence and library companion engineered with Python and Streamlit. Powered by the AniList GraphQL API, it unifies catalogue exploration, seasonal browsing, high-resolution media art, weekly airing schedules, personal watchlists, and viewing analytics into a responsive dashboard.

**Crafted by Shashank — powered by Saiyan spirit.**

[Open Otaku Orbit](https://otaku-orbit.streamlit.app/)

Current version: `1.8.0`

---

## Executive Overview

Otaku Orbit delivers a frictionless anime tracking experience with zero forced sign-ups, zero third-party tracking, and enterprise-grade privacy boundaries. Whether running as a lightweight personal desktop app or deployed to Streamlit Community Cloud with OIDC multi-user authentication, Otaku Orbit gives you full ownership of your data, library, and viewing history.

### Core Highlights

- **Modular Clean Architecture**: Refactored domain architecture cleanly decoupled across configuration (`modules.config`), database persistence (`modules.db`), AniList GraphQL integration (`modules.api`), domain business services (`modules.services`), and responsive presentation (`modules.ui`).
- **Glassmorphic Visual Design**: High-contrast modern glassmorphic interface with dynamic backdrop-blur filters, theme glow accents, card hover elevation transforms, and responsive mobile-first breakpoints.
- **Dynamic Visual Experience**: Choose between an immersive **Poster Grid** layout for visual browsing and a **Detailed Cards** layout for in-depth summaries.
- **Wheel of Fortune Backlog Decision Maker**: Filter your backlog by mood, status, or episode length and let fate select your next watch.
- **Curated Mood & Vibe Discovery**: Explore anime categorized into distinct emotional vibes (Cozy & Chill, Hype & Adrenaline, Dark & Psychological, Tearjerker & Emotional, Brainless Comedy, Mind-Bending & Sci-Fi).
- **Custom Shelves Management**: Organize your watchlist into customizable personal shelves (Favorites, Masterpiece, Guilty Pleasure, On-Hold, Dropped, Plan to Watch) with bulk shelf assignment.
- **Episode Notes & Timestamps**: Record granular episode reflections, key moments, and timestamps.
- **Franchise Chronological Watch Orders**: Step-by-step release order, story chronological order, and community tips for intricate multi-series universes (Fate, Monogatari, Steins;Gate, Attack on Titan, etc.).
- **Production Staff & Director Credits**: Inspect key industry talent behind your favorite anime, including head directors, character designers, and music composers.
- **Theme Previews & Jukebox**: One-click opening, ending, and soundtrack search links for Spotify, Apple Music, YouTube Music, and video previews via YouTube and AnimeThemes.
- **Seiyuu Cross-Over Matrix**: Discover shared voice actor relationships across different titles in your personal library.
- **Anti-Spoiler Smart Masks**: Protect plot twists and critical synopsis keywords behind blur overlays.
- **Otaku ID Passport & Library Card**: Generate and download high-resolution shareable vector SVG badges detailing your anime journey, stats, and rank.
- **5x5 Anime Watch Challenge Bingo**: Interactive 25-tile challenge matrix tracking diverse viewing achievements across genres, lengths, and eras.
- **Viewing Habit Rings**: Set weekly episode targets and track your weekly viewing pacing.
- **Rewatch Cycles & Counter**: Dedicated tracking of repeat watches with start and completion timestamps.
- **Two-User Taste Compatibility**: Compare your library JSON against a friend's library to compute a taste affinity percentage and reciprocal recommendations.
- **Visual Tier List Maker & SVG Export**: Organize completed and watching titles into visual S, A, B, C, and D tiers with standalone vector SVG exports.
- **Comprehensive Ecosystem Sync**: Two-way export and import for Kitsu JSON, SIMKL CSV, MyAnimeList (MAL) XML, spreadsheet CSV with formula sanitization, and atomic JSON backups.
- **Cloud Database Snapshot (Zero Data Loss)**: Base64 export and restore of raw SQLite databases for seamless migrations on ephemeral cloud environments.
- **Discord Webhook Broadcast**: Generate Discord-compatible embed notification payloads for community milestones.
- **Progressive Web App (PWA) & Offline Shell**: Web app manifest (`manifest.json`) and service worker support for offline caching and home screen installation.
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
| **Quality & Testing** | `pytest` test suite (100+ tests), Streamlit `AppTest`, Playwright mobile browser smoke tests |
| **CI / CD Pipelines** | GitHub Actions matrix test suite, CodeQL security analysis, release integrity verification |

---

## Feature Deep Dive

### 1. Discovery, Moods & Serendipity
- **Curated Mood & Vibe Filter**: Filter catalogue titles by mood tags (Cozy & Chill, Hype & Adrenaline, Dark & Psychological, Tearjerker, Brainless Comedy, Mind-Bending Sci-Fi).
- **Wheel of Fortune Decision Maker**: Randomly spins your unwatched queue to break backlog analysis paralysis based on mood or runtime constraints.
- **Intelligent Search**: Real-time debounced querying across the entire AniList catalogue with cached GraphQL requests.
- **Seasonal Lineup**: Interactive season selector (Winter, Spring, Summer, Fall) with year navigation dating back to classic eras.
- **Dual Layouts**: Switch dynamically between the high-density Poster Grid view and detailed narrative cards.

### 2. Media Modals & Franchise Navigation
- **Chronological Franchise Watch Orders**: In-depth viewing guides for complex franchises with release vs chronological ordering.
- **Key Production Staff**: Discover directors, series composers, and character designers.
- **Legal Streaming Deeplinks**: Direct watch buttons for verified legal platforms (Crunchyroll, Netflix, Hulu, HIDIVE, etc.).
- **Character & Voice Actor Gallery**: Detailed portrait gallery of characters paired with Japanese voice actors (Seiyuu).
- **Theme Song Jukebox & Video Previews**: Direct music and video links to stream Opening, Ending, and OST tracks.
- **Anti-Spoiler Synopsis Masking**: Keeps key plot surprises hidden until you choose to reveal them.

### 3. Airing Calendar, Countdown & Schedule Export
- **Weekly Schedule**: Aggregates upcoming episode broadcasts across seven days with countdown timers.
- **Local Timezone Conversion**: Automatically adapts UTC broadcast schedules into any configured local timezone.
- **Watchlist Badges & Countdown Ticker**: Highlights upcoming episodes for anime currently tracked in your personal library and displays a top alert banner for episodes broadcasting within 48 hours.
- **iCalendar (.ics) Export**: Export your personal airing schedule as an RFC 5545 standard `.ics` calendar file to subscribe via Google Calendar, Apple Calendar, or Outlook.

### 4. Watchlist & Library Operations
- **Custom Shelves**: Organize your queue into customizable shelves (Favorites, Masterpiece, Guilty Pleasure, etc.) with batch updates.
- **Episode Notes & Timestamps**: Capture granular notes on every episode.
- **Lifecycle Statuses**: Track titles across Planning, Watching, Rewatching, Completed, Paused, and Dropped states.
- **Quick Episode Increment (+1)**: Single-click progress updates that automatically log to watch history.
- **Manga & Light Novel Mode**: Toggle between anime episodes and manga chapters/volumes seamlessly.
- **Rewatch Cycles**: Full tracking of repeat watches with start/finish timestamps.
- **Batch Action Toolbar**: Select multiple anime simultaneously to update statuses, apply bulk tags, or batch remove titles.

### 5. Analytics, Gamification & Social
- **Otaku ID Passport Generator**: Download a shareable vector SVG card showcasing your anime level, favorite genres, and stats.
- **5x5 Anime Watch Bingo**: Interactive 25-challenge board evaluated against your real library.
- **Viewing Habit Rings**: Set weekly goals and visually track your progress.
- **Seiyuu Cross-Over Matrix**: View which voice actors appear most frequently across your saved titles.
- **Two-User Taste Compatibility**: Upload a friend's library to check taste affinity scores and discover cross-recommendations.
- **Interactive Tier List Maker**: Categorizes your collection into S, A, B, C, and D tiers with downloadable SVG graphics.
- **Viewing Activity Heatmap**: 30-day activity grid visualizing daily episode logs and active watching streaks.
- **Milestone Badges**: Unlockable achievements rewarding progression from initial discovery to centurion milestones.

### 6. Data Portability & Integrations
- **Cloud SQLite Database Snapshot**: Base64 database string backup and restore for zero data loss on ephemeral cloud deployments.
- **Kitsu & SIMKL Support**: Two-way export and import for Kitsu JSON and SIMKL CSV formats.
- **1-Click AniList Profile Sync**: Synchronize public anime libraries directly from AniList usernames.
- **MyAnimeList (MAL) XML Export**: Seamlessly migrate your watch history and scores to MyAnimeList or third-party ecosystem tools.
- **Spreadsheet CSV Export**: Export your complete library to CSV, hardened against spreadsheet formula injection (`=`, `@`, `+`, `-`).
- **Atomic JSON Backups**: Full snapshot export and import with backward-compatible schema validation.
- **Discord Webhook Payloads**: Generate formatted JSON embeds for publishing updates to your Discord channels.

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
# Run the unit and integration test suite (100+ tests):
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
