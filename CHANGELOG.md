# Changelog

## 2.0.0

- Add Daily Otaku Trivia Battle (`TRIVIA_QUESTION_BANK`, `generate_daily_trivia_question`, `evaluate_trivia_answer`, `record_trivia_score`, `fetch_trivia_streak`) with deterministic daily questions, multi-choice answer validation, score accumulation, and streak tracking.
- Add OST Quiz / Blind Audio Challenge (`OST_QUIZ_BANK`, `generate_ost_quiz_question`, `evaluate_ost_quiz_answer`) featuring iconic anime theme song matching and interactive UI trivia games.
- Add Daily & Weekly Otaku Quests (`DAILY_QUESTS_TEMPLATE`, `generate_daily_quests`, `record_quest_progress`, `fetch_daily_quest_states`, `check_quest_completion`) delivering gamified daily tracking goals and XP rewards.
- Add Native Web Share API Integration (`generate_web_share_html`) enabling one-tap native mobile sharing of watchlists and recommendations.
- Add Binge Budget Planner (`plan_binge_schedule`) calculating exact episode allotments fitting user daily or weekly free-time budgets.
- Add Playback Speed Adjusted Watchtime Calculator (`calculate_speed_adjusted_runtime`) dynamically showing actual viewing hours and hours saved across 1.0x to 2.5x speeds.
- Add Manga Chapter Sync / Anime-to-Manga Bridge (`MANGA_ANIME_SYNC_MAP`, `get_manga_chapter_sync`) estimating exact source manga chapters corresponding to current anime episodes (*Frieren*, *JJK*, *Demon Slayer*, *Chainsaw Man*, *One Piece*).
- Add Watchlist Decay & Stagnation Auditor (`audit_watchlist_decay`) identifying forgotten backlog entries dormant for >180 days with total backlog recovery hours.
- Add Ambient Anime Lo-Fi Radio Player (`ANIME_LOFI_STREAMS`, `render_lofi_player_html`) embedding aesthetic lo-fi streams directly into the command centre.
- Add Dynamic Trailer Theater Embed Modal (`generate_trailer_theater_embed`) supporting responsive YouTube and AniList preview embeds.
- Add Anime Poster Wallpaper Generator (`generate_wallpaper_poster_svg`) producing high-definition 1080p and 4K vector SVG poster wallpapers with community ratings and studio marks.
- Add Character Quote of the Day (`CHARACTER_QUOTES`, `get_character_quote`) delivering iconic anime quotes on daily cycles.
- Add Story Arc Progression Visualizer (`FRANCHISE_ARCS`, `generate_arc_progression_data`) tracking milestone arcs and chapter ranges for major anime series.
- Add Multi-Axis Anime Genre Radar Chart (`GLOBAL_GENRE_BENCHMARKS`, `calculate_genre_radar_metrics`) benchmarking personal library preferences against global anime community averages.
- Add Watchtime Milestones & Real-World Equivalents (`TIME_EQUIVALENCE_RATES`, `calculate_time_equivalence_milestones`) visualizing viewing hours as international flights, classic literature reads, and Earth orbits.
- Add Voice Actor (Seiyuu) Network Graph (`build_voice_actor_network`) mapping co-star relationships and shared titles across voice casts.
- Add Headless API / Lightweight JSON Mode (`handle_headless_request`) providing REST-like JSON endpoints (`/api/v1/health`, `/api/v1/watchlist`, `/api/v1/stats`, `/api/v1/progress/increment`) for headless scripting.
- Add Automated Visual Regression & Glassmorphism Contract Verification (`verify_visual_glassmorphism_contract`, `tests/test_visual_regression.py`) guaranteeing backdrop-blur, radius, and glow token integrity.
- Add Cloud Storage Sync Payloads (`prepare_s3_backup_payload`) formatting atomic backups for AWS S3 and Cloudflare R2 bucket distribution.
- Add Offline IndexedDB Mirror Generator (`generate_indexeddb_mirror_js`) generating client-side JavaScript mirroring SQLite libraries into browser IndexedDB storage for progressive web apps.

## 1.9.0

- Add Curated Filler Guides & Canon Detection (`FILLER_GUIDES`, `get_filler_guide`, `is_episode_filler`, `get_next_canon_episode`) for classic long-running anime (*Naruto*, *Bleach*, *One Piece*, *Gintama*, *DBZ*).
- Add Natural Language "Vibe & Premise" Semantic Search (`search_by_vibe`) matching free-form synopsis and thematic queries.
- Add Character Tropes & Dynamic Chemistry Matcher (`CHARACTER_TROPES`, `match_anime_by_trope`) categorizing titles by beloved character tropes.
- Add Adaptive Backlog Prioritizer (`calculate_backlog_priority`) smartly sorting user queues by taste score and pacing.
- Add Franchise Sequel & Spinoff Alert Radar (`detect_franchise_sequels`) discovering uncompleted next seasons and side-stories for completed titles.
- Add Dynamic Ambient Glow Background Generator (`generate_ambient_glow_css`) matching page background accents to active anime cover art.
- Add Custom Theme Studio & Palette Designer (`create_custom_theme_palette`) allowing full personalization of neon primary, glow, and metric colors.
- Add Cinematic Modal Presentation layout (`generate_cinematic_modal_html`) featuring wide banner backdrops and typography.
- Add Persistent Mini-Dock Widget state helper (`get_mini_dock_state`) tracking currently active series with 1-click progress increment.
- Add Audio Feedback & Synthesizer Data URIs (`get_sound_effects_data_uris`) for UI chimes and feedback.
- Add Spotify-Style "Anime Wrapped" Year-in-Review Dossier (`generate_anime_wrapped_data`, `generate_anime_wrapped_svg`) generating vector infographic cards and assigning user anime archetypes.
- Add Anime Season Fantasy League (`record_fantasy_prediction`, `fetch_fantasy_predictions`, `evaluate_fantasy_score`) scoring seasonal rank predictions.
- Add Printable Bullet Journal Watch Tracker (`generate_bujo_tracker_markdown`, `generate_bujo_tracker_html`) for offline and Notion tracking.
- Add Community Tier List Preset Templates (`TIER_LIST_TEMPLATES`, `get_tier_list_template`) for Openings, Antagonists, and Masterpieces.
- Add Watch Party Synchronized Timestamp Links (`generate_watch_party_sync_link`, `parse_watch_party_sync_link`) for remote shared viewing.
- Add Animation Studio Loyalty Radar & Director Index (`calculate_studio_loyalty_index`) tracking stats across MAPPA, Ufotable, Bones, KyoAni, etc.
- Add Cumulative Seiyuu (Voice Actor) Screen-Time Calculator (`calculate_seiyuu_screen_time`) computing total hours listened per voice actor.
- Add The 3-Episode Rule & Drop-off Statistics (`calculate_drop_off_statistics`) analyzing drop curves and median drop episodes.
- Add Historical Era & Decade Chronology Breakdown (`HISTORICAL_ERAS`, `calculate_era_distribution`) bucketing titles across 80s, 90s, 2000s, 2010s, and 2020s.
- Add Watch Velocity Pacing Alert & Habit Evaluator (`evaluate_pacing_alert`) providing pacing status and motivating tips.
- Add Custom Webhook Automation (`generate_custom_webhook_payload`) dispatching JSON payloads to external endpoints on episode completion.
- Add Multi-Profile Household Switcher (`list_user_profiles`, `create_user_profile`, `delete_user_profile`) supporting distinct isolated libraries.
- Add Direct API Token Session Management (`save_api_token`, `fetch_api_token`, `generate_direct_sync_request`) for authenticated synchronization.
- Add GitHub Gist / Cloud Backup Export Payload (`prepare_gist_backup_payload`).
- Add Personal Watchlist RSS 2.0 Airing Feed Generator (`generate_watchlist_rss_feed`) generating standard XML episode release feeds.
- Refresh README.md with an electric, community-first anime fan introduction while upholding the strict single external link constraint.
- Expand automated test suite to 115+ unit and integration tests.

## 1.8.0

- Add Anime Wheel of Fortune Backlog Decision Maker (`pick_random_backlog`) to pick the next title based on mood, status, or duration filters.
- Add Taste Match Compatibility Scorer (`calculate_taste_match_score`) matching user library preferences against candidate titles.
- Add Curated Mood & Vibe Filter (`filter_by_mood`, `ANIME_MOODS`) supporting 6 distinct emotional vibes across discovery views.
- Add Custom Shelves System (`CUSTOM_SHELVES`, `update_anime_shelf`, `batch_update_shelf`) for granular library organization (Favorites, Masterpiece, Guilty Pleasure, etc.).
- Add Episode-Level Notes & Timestamps (`log_episode_note`, `fetch_episode_notes`) for granular episode reflections.
- Add Key Production Staff & Directors display (`extract_staff_and_directors`) highlighting directors, character designers, and music composers.
- Add Franchise Chronological Watch Order Roadmaps (`FRANCHISE_WATCH_ORDERS`, `get_franchise_watch_order`) for complex universes (Fate, Monogatari, Steins;Gate, etc.).
- Add Dynamic Artwork Accent Palette derivation (`derive_artwork_accent_color`) for visual theme adaptation.
- Add Opening & Ending Theme Song Video Previews (`get_theme_video_links`) with direct links to YouTube and AnimeThemes.
- Add Seiyuu Cross-Over & Character Relationship Matrix (`build_seiyuu_character_matrix`) identifying shared voice actors in the user's library.
- Add Anti-Spoiler Smart Masks (`apply_spoiler_mask`) protecting plot twists and critical synopsis keywords.
- Add Otaku ID Passport & Library Card SVG Generator (`generate_otaku_passport_svg`) for shareable visual badges.
- Add 5x5 Anime Watch Challenge Bingo Matrix (`BINGO_CHALLENGES`, `evaluate_bingo_card`) with automated completion evaluation.
- Add Viewing Habit Rings & Weekly Episode Targets (`set_viewing_goal`, `fetch_viewing_goal`) with real-time goal progress tracking.
- Add Rewatch Cycles & History Tracking (`record_rewatch_cycle`, `fetch_rewatch_cycles`) recording start/completion dates and repetition counts.
- Add Two-User Taste Compatibility Matcher (`calculate_user_taste_compatibility`) calculating taste match percentages and cross-recommendations.
- Add Visual Drag-and-Drop Tier List SVG Generator (`generate_tier_list_svg`) generating standalone graphic exports.
- Add Direct AniList Profile Sync Payload Generator (`prepare_anilist_sync_payload`) for bi-directional status, score, and progress sync.
- Add Kitsu Library Format Two-Way Export & Import (`export_kitsu_json`, `import_kitsu_json`).
- Add SIMKL CSV Format Two-Way Export & Import (`export_simkl_csv`, `import_simkl_csv`).
- Add Cloud SQLite Database Snapshot Base64 Export & Restore (`export_sqlite_backup_base64`, `restore_sqlite_backup_base64`) for zero-loss cloud migrations.
- Add Discord Webhook Broadcast Notification Payloads (`generate_discord_webhook_payload`) for community activity sharing.
- Add Media Subtypes Tagging (`MEDIA_SUBTYPES`) for TV, Movies, OVAs, ONAs, Specials, and Light Novels.
- Add Interactive Keyboard Navigation Shortcuts cheatsheet in settings.
- Add PWA Service Worker script generation (`generate_service_worker_js`) supporting offline asset caching.
- Expand automated test suite to 110+ comprehensive unit and integration tests.

## 1.7.0

- Refactor application into a modular architecture across domain packages (`modules.config`, `modules.db`, `modules.api`, `modules.services`, `modules.ui`).
- Enhance UI/UX with glassmorphism design system featuring backdrop blur filters, dynamic neon glow accents, smooth card hover elevations, and responsive typography.
- Fix PWA manifest and meta tags rendering as raw code block at the top of the viewport by encapsulating them inside an invisible unindented container (fixes #37).
- Resolve Analytics & Insights runtime chart failure when upstream Altair/Vega library throws TypeError by implementing a resilient native fallback (fixes #39).
- Optimize database performance by introducing composite indexes (`idx_watchlist_media_status`, `idx_watch_history_anime`) for high-speed queries on large collections.
- Expand automated test suite to 89 comprehensive tests with 100% pass rate.
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
