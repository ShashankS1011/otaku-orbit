# Otaku Orbit

> Your personal anime command centre — discover, track, and plan your next obsession.

**Otaku Orbit** is a fast, polished anime companion built with Python and Streamlit. It brings AniList discovery, seasonal browsing, personalized recommendations, watchlist progress, and useful viewing statistics into one calm, focused dashboard.

**Made by Shashank — powered by Saiyan spirit**

[Open Otaku Orbit](https://otaku-orbit.streamlit.app/)

Current version: `1.5.0`

## Deploy on Streamlit Community Cloud

Streamlit Community Cloud deployment settings:

- **Repository:** `ShashankS1011/otaku-orbit`
- **Branch:** `main`
- **Main file path:** `app.py`
- **App URL:** otaku-orbit.streamlit.app

Streamlit will build the app from this repository and provide a public `streamlit.app` URL. Future pushes to `main` will automatically update the deployed app.

## What it does

- Search AniList's anime catalogue with fast cached GraphQL requests
- Browse paginated search results, open full anime details, and use random discovery
- View high-resolution cover images, banner art, and trailer links
- Switch between visual Poster Grid and Detailed Card view modes
- Track upcoming broadcasts with the weekly Airing Calendar in your local timezone
- Navigate franchise relations (prequels, sequels) and community recommendations
- Filter results by genre, format, score, and mature-content preference
- Get personalized recommendations weighted by ratings and completion status
- Choose from sleek theme presets: Saiyan Neon, Cyberpunk Cyan, Sunset Flame, and Emerald Matrix
- Save anime locally or isolate by signed-in OIDC account
- Track planning, watching, rewatching, completed, and dropped titles with rewatch counts
- Organize your collection with custom tags and perform batch operations
- Export and restore your watchlist as portable JSON, spreadsheet CSV, or MyAnimeList (MAL) XML
- Set a daily episode goal and see upcoming airing reminders
- Delete user watchlist data and notes securely from privacy controls
- Explore a personal genre profile with lightweight charts
- Stay resilient with cached requests, exponential backoff retries, and clear API error states

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
streamlit run app.py
```

The app opens at `localhost:8501`.

The app uses a separate SQLite database file per signed-in OIDC account. Without OIDC configuration, guest watchlists are scoped to one browser session and do not sync across devices. To enable accounts, configure an OIDC provider in Streamlit Community Cloud secrets using `.streamlit/secrets.toml.example` as a template. Register the app's `oauth2callback` redirect URI with the provider. Never commit real credentials.

Streamlit Community Cloud storage may be ephemeral. Set `OTAKU_ORBIT_DB_PATH` to a file location on a persistent mounted volume when your host provides one. The API endpoint, request timeout, retry count, and cache duration can be adjusted with `ANILIST_API_URL`, `OTAKU_ORBIT_REQUEST_TIMEOUT`, `OTAKU_ORBIT_REQUEST_ATTEMPTS`, and `OTAKU_ORBIT_CACHE_TTL`.

## Test and quality checks

```powershell
python -m pytest -q
python -m py_compile app.py
python -m ruff check app.py tests
```

GitHub Actions runs tests, syntax checks, and Ruff on Python 3.11 and 3.12 for every push and pull request (`.github/workflows/ci.yml`).

## Release checklist

1. Update `APP_VERSION` in `app.py` using semantic versioning and add a changelog entry.
2. Run the test, compile, and Ruff commands above.
3. Update the current version in this README.
4. Push a release branch and merge it through a passing pull request.

## Contributors

- butteryjam — reported the mobile browser compatibility issue.

## Versioning

Otaku Orbit follows semantic versioning in `MAJOR.MINOR.PATCH` form:

- **Major:** breaking changes
- **Minor:** new backward-compatible features
- **Patch:** bug fixes and small maintenance updates

The application version is defined in `app.py` and updated with each release.

## License

Otaku Orbit is released under the MIT License.

## Technology

Python · Streamlit · AniList GraphQL · SQLite · pytest · GitHub Actions
