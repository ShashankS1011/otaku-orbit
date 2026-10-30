# Changelog

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
