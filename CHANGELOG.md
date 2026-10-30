# Changelog

## 1.7.0

- Refactor application into a modular architecture across domain packages (`modules.config`, `modules.db`, `modules.api`, `modules.services`, `modules.ui`).
- Enhance UI/UX with glassmorphism design system featuring backdrop blur filters, dynamic neon glow accents, smooth card hover elevations, and responsive typography.
- Fix PWA manifest and meta tags rendering as raw code block at the top of the viewport by encapsulating them inside an invisible unindented container (fixes #37).
- Optimize database performance by introducing composite indexes (`idx_watchlist_media_status`, `idx_watch_history_anime`) for high-speed queries on large collections.
- Expand automated test suite to 86 comprehensive tests with 100% pass rate.
- Update GitHub Actions CI matrix to test and compile all modular domain packages across Python 3.11, 3.12, and 3.13.
- Enhance Bandit static analysis and dependency security workflows to cover all domain modules.

## 1.6.0

- Add Legal Streaming Availability & direct deeplinks (Crunchyroll, Netflix, Hulu, HIDIVE, Disney+, etc.) in anime detail modals.
- Add Character & Japanese Voice Actor (Seiyuu) gallery displaying character roles and portraits.
- Add Animation Studio and Source Material (Manga, Light Novel, Original, Web Novel) filtering on Discover and Seasonal views.
- Add Theme Song Jukebox with one-click direct links to Spotify and YouTube Music for OPs, EDs, and OSTs.
- Add interactive Analytics & Insights dashboard featuring score distributions, release era timelines, and genre profiles.
- Add timestamped watch history logging and a GitHub-style 30-day viewing activity heatmap.
- Add Binge Velocity pace tracking and automated completion date forecasts.
- Add Milestone Badges & Achievements system tracking viewing progression and streaks.
- Add iCalendar (.ics) export for upcoming episode broadcasts in the user's watchlist.
- Add live Airing Countdown ticker banner on the dashboard for upcoming broadcasts within 48 hours.
- Add interactive Tier List Maker organizing titles into S, A, B, C, and D tiers.
- Add 1-click AniList profile library synchronization for public user accounts.
- Add Manga & Light Novel tracking mode with chapters and volumes support.
- Add instant in-memory watchlist search filter across titles, tags, notes, and genres.
- Add Progressive Web App (PWA) manifest (`manifest.json`) and mobile installation support.
- Expand test suite to 79 unit tests covering all 16 new capabilities.

## 1.5.0

- Add Airing Calendar view for tracking upcoming weekly anime broadcasts in the user's timezone.
- Add Poster Grid layout alongside Detailed Cards in Discover and Seasonal views.
- Add dynamic theme presets: Saiyan Neon, Cyberpunk Cyan, Sunset Flame, and Emerald Matrix.
- Enhance AniList detail view with high-res banner art, franchise relation navigation, and community recommendations.
- Add Rewatches tracking and REWATCHING status in the watchlist.
- Add Custom Tags support and tag-based watchlist filtering.
- Add Batch Actions toolbar for bulk status updates, bulk tagging, and bulk removal.
- Add MyAnimeList (MAL) XML export support in addition to JSON and CSV formats.
- Add security and release verification GitHub Actions workflows.
- Expand test suite to 67 automated tests covering all new features and fix Streamlit AppTest empty state test.

## 1.4.0

- Isolate watchlist databases per OIDC account or anonymous browser session.
- Add explicit sign-in, sign-out, and owner data deletion controls when OIDC is configured.
- Prefer AniList's extra-large cover images and validate imported cover URLs.
- Add timezone-aware airing times, corrected winter season years, and watchlist sorting by personal score and remaining runtime.
- Weight recommendations by personal scores and watch status.
- Harden user input, backup versioning, CSV formula handling, AniList response validation, and retry backoff.
- Add cache timestamps, manual catalogue refresh, private storage documentation, and image accessibility labels.
