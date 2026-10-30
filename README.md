# Otaku Orbit

> **Your personal anime command centre — discover, track, and curate your next obsession.**

Otaku Orbit is an anime intelligence and library companion engineered with Python and Streamlit. Powered by the AniList GraphQL API, it unifies catalogue exploration, seasonal browsing, high-resolution media art, weekly airing schedules, personal watchlists, and viewing analytics into a responsive dashboard.

**Crafted by Shashank — powered by Saiyan spirit.**

[Open Otaku Orbit](https://otaku-orbit.streamlit.app/)

Current version: `1.7.0`

---

## Executive Overview

Otaku Orbit delivers a frictionless anime tracking experience with zero forced sign-ups, zero third-party tracking, and enterprise-grade privacy boundaries. Whether running as a lightweight personal desktop app or deployed to Streamlit Community Cloud with OIDC multi-user authentication, Otaku Orbit gives you full ownership of your data, library, and viewing history.

### Core Highlights

- **Modular Clean Architecture**: Refactored domain architecture cleanly decoupled across configuration (`modules.config`), database persistence (`modules.db`), AniList GraphQL integration (`modules.api`), domain business services (`modules.services`), and responsive presentation (`modules.ui`).
- **Glassmorphic Visual Design**: High-contrast modern glassmorphic interface with dynamic backdrop-blur filters, theme glow accents, card hover elevation transforms, and responsive mobile-first breakpoints.
- **Dynamic Visual Experience**: Choose between an immersive **Poster Grid** layout for visual browsing and a **Detailed Cards** layout for in-depth summaries.
- **High-DPI Artwork & Cast Gallery**: Native retrieval of AniList `extraLarge` cover art, high-definition banner images, and a visual **Character & Voice Actor (Seiyuu)** gallery with portraits and roles.
- **Where to Stream Legally**: Direct official streaming badges and deeplinks for **Crunchyroll**, **Netflix**, **Hulu**, **HIDIVE**, **Disney+**, **Amazon Prime Video**, and **Bilibili**.
- **Broadcast Intelligence & Calendar**: Real-time weekly **Airing Calendar** grouped by day in your local timezone, **iCalendar (.ics)** schedule export, and an automated **Airing Countdown Ticker** banner for upcoming watchlist broadcasts.
- **Franchise & Recommendation Graphs**: Explore franchise trees (prequels, sequels, side-stories) and AniList community recommendations directly from media modals.
- **Advanced Filtering**: Filter by animation studios (e.g. MAPPA, Ufotable, Bones) and source material (Manga, Light Novel, Original, Web Novel) on Discover and Seasonal views.
- **Theme Song Jukebox**: One-click opening, ending, and soundtrack search links for Spotify, Apple Music, and YouTube Music.
- **Comprehensive Library Management**: Dedicated tracking statuses (`PLANNING`, `WATCHING`, `REWATCHING`, `COMPLETED`, `PAUSED`, `DROPPED`), rewatch counters, custom tags, instant in-memory search, and a batch operations toolbar for bulk editing.
- **Manga & Light Novel Tracking**: Global toggle switching between Anime and Manga modes, supporting chapter and volume tracking.
- **1-Click AniList Profile Sync**: Import and synchronize public anime libraries directly from AniList usernames in one click.
- **Viewing Analytics & Gamification**: Dedicated **Analytics & Insights** dashboard featuring score distribution histograms, release era timelines, genre profile charts, a 30-day GitHub-style viewing activity heatmap, active watch streaks, binge velocity pacing, and an intelligent **Completion Date Forecast**.
- **Interactive Tier List Maker**: Organize completed and watching titles into visual S, A, B, C, and D tiers with customizable snapshot exports.
- **Milestone Badges & Achievements**: 8 unlockable progression achievements rewarding milestones like watch count, binge sprints, and genre exploration.
- **Robust Data Portability**: Two-way JSON backups with atomic schema validation, spreadsheet-compatible CSV export with formula injection sanitization, and MyAnimeList (MAL) XML format support.
- **Personalized Theming**: Four dynamic UI themes — *Saiyan Neon*, *Cyberpunk Cyan*, *Sunset Flame*, and *Emerald Matrix*.
- **Progressive Web App (PWA)**: Web app manifest (`manifest.json`) and mobile meta tags supporting full installation to home screens on iOS, Android, and Desktop.
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
| **Quality & Testing** | `pytest` test suite (86 tests), Streamlit `AppTest`, Playwright mobile browser smoke tests |
| **CI / CD Pipelines** | GitHub Actions matrix test suite, CodeQL security analysis, release integrity verification |

---

## Feature Deep Dive

### 1. Discovery & Seasonal Exploration
- **Intelligent Search**: Real-time debounced querying across the entire AniList catalogue with cached GraphQL requests.
- **Seasonal Lineup**: Interactive season selector (Winter, Spring, Summer, Fall) with year navigation dating back to classic eras.
- **Filter Matrix**: Granular filtering by format (TV, Movie, OVA, ONA, Special), genre, studio, source material, minimum community score, and mature content preference.
- **Random Discovery**: One-click serendipitous exploration discovering hidden gems across genres.
- **Dual Layouts**: Switch dynamically between the high-density Poster Grid view and detailed narrative cards.

### 2. Media Modals & Franchise Navigation
- **High-Definition Media Details**: Rich modal overlays featuring high-resolution banner artwork, studio credits, broadcast status, and synopsis.
- **Legal Streaming Deeplinks**: Direct watch buttons for verified legal platforms (Crunchyroll, Netflix, Hulu, HIDIVE, etc.).
- **Character & Voice Actor Gallery**: Detailed portrait gallery of main and supporting characters paired with their Japanese voice actors (Seiyuu).
- **Theme Song Jukebox**: Direct music links to stream Opening, Ending, and OST tracks on Spotify and YouTube Music.
- **Franchise Tree**: Navigate directly between prequels, sequels, and spin-offs without leaving the modal.
- **Community Recommendations**: View crowdsourced "Fans Also Liked" suggestions complete with user recommendation counts and quick-add shortcuts.

### 3. Airing Calendar, Countdown & Schedule Export
- **Weekly Schedule**: Aggregates upcoming episode broadcasts across seven days with countdown timers.
- **Local Timezone Conversion**: Automatically adapts UTC broadcast schedules into any configured local timezone (e.g., UTC, America/New_York, Europe/London, Asia/Tokyo).
- **Watchlist Badges & Countdown Ticker**: Highlights upcoming episodes for anime currently tracked in your personal library and displays a top alert banner for episodes broadcasting within 48 hours.
- **iCalendar (.ics) Export**: Export your personal airing schedule as an RFC 5545 standard `.ics` calendar file to subscribe via Google Calendar, Apple Calendar, or Outlook.

### 4. Watchlist & Backlog Operations
- **Lifecycle Statuses**: Track titles across Planning, Watching, Rewatching, Completed, Paused, and Dropped states.
- **Quick Episode Increment (+1)**: Single-click progress updates that automatically log to watch history and transition titles to `COMPLETED` when the final episode is watched.
- **Manga & Light Novel Mode**: Toggle between anime episodes and manga chapters/volumes seamlessly.
- **Rewatch Counter**: Dedicated counter tracking full rewatch cycles for evergreen favorites.
- **Custom Tagging & Instant Search**: Assign custom tags and filter your library instantly by title, tag, notes, or genre without server reloads.
- **Batch Action Toolbar**: Select multiple anime simultaneously to update statuses, apply bulk tags, or batch remove titles.
- **Personal Notes & 1–10 Scoring**: Record personal reflections, reviews, and ratings for every tracked title.

### 5. Analytics, Pacing & Gamification
- **Viewing Activity Heatmap**: 30-day activity grid visualizing daily episode logs and active watching streaks.
- **Binge Velocity & Completion Forecast**: Calculates average viewing velocity (episodes per active day) and forecasts the exact completion date for in-progress series.
- **Rating Distribution Curve**: Visual distribution chart comparing personal user ratings against AniList global community ratings.
- **Interactive Tier List Maker**: Categorizes your collection into S, A, B, C, and D tiers based on personal scores with visual poster previews.
- **Milestone Badges**: 8 unlockable achievements rewarding progression from initial discovery to centurion milestones.
- **Backlog Watch-Time Calculator**: Calculates total runtime remaining across your queue.

### 6. Data Portability & Integrations
- **1-Click AniList Profile Sync**: Synchronize public anime libraries directly from AniList usernames.
- **MyAnimeList (MAL) XML Export**: Seamlessly migrate your watch history and scores to MyAnimeList or third-party ecosystem tools.
- **Spreadsheet CSV Export**: Export your complete library to CSV, hardened against spreadsheet formula injection (`=`, `@`, `+`, `-`).
- **Atomic JSON Backups**: Full snapshot export and import with backward-compatible schema validation.
- **User Privacy & Account Isolation**: When OIDC authentication is configured, user libraries are stored in isolated per-account databases. Unauthenticated guest sessions remain transient in memory/session.

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
# Run the unit and integration test suite (86 tests):
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
