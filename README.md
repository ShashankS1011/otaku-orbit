# Otaku Orbit

> Your personal anime command centre — discover, track, and plan your next obsession.

**Otaku Orbit** is a fast, polished anime companion built with Python and Streamlit. It brings AniList discovery, seasonal browsing, personalized recommendations, watchlist progress, and useful viewing statistics into one calm, focused dashboard.

**Made by Shashank — powered by Saiyan spirit**

[Open the live Streamlit app](https://otaku-orbit.streamlit.app/)

Current version: `1.3.0`

## Deploy on Streamlit Community Cloud

[Deploy Otaku Orbit on Streamlit Community Cloud](https://share.streamlit.io/)

After signing in with GitHub, create a new app with these settings:

- **Repository:** `ShashankS1011/otaku-orbit`
- **Branch:** `main`
- **Main file path:** `app.py`
- **App URL:** https://otaku-orbit.streamlit.app/

Streamlit will build the app from this repository and provide a public `streamlit.app` URL. Future pushes to `main` will automatically update the deployed app.

## What it does

- Search AniList's anime catalogue with fast cached GraphQL requests
- Browse paginated search results, open full anime details, and use random discovery
- Browse trending titles and the current seasonal lineup
- Filter results by genre, format, score, and mature-content preference
- Get recommendations based on the genres in your watchlist
- Save anime locally without needing an account
- Track planning, watching, completed, and dropped titles
- Track episode progress and estimate watch time
- Continue watching view plus search and status filters for your library
- Export and restore your watchlist as a portable JSON backup
- Set a daily episode goal and see upcoming airing reminders
- Choose compact cards for a more focused layout
- Explore a personal genre profile with lightweight charts
- Stay resilient with cached requests, retries, and clear API error states

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Your watchlist is stored in `anime_companion.db` and is intentionally ignored by Git.

For deployment, local SQLite storage is best for personal use and can be reset by an ephemeral hosting environment. Set `OTAKU_ORBIT_DB_PATH` to a persistent mounted path when your host provides one. The API endpoint, request timeout, retry count, and cache duration can be adjusted with `ANILIST_API_URL`, `OTAKU_ORBIT_REQUEST_TIMEOUT`, `OTAKU_ORBIT_REQUEST_ATTEMPTS`, and `OTAKU_ORBIT_CACHE_TTL`.

## Test and quality checks

```powershell
python -m pytest -q
python -m py_compile app.py
python -m ruff check app.py tests
```

GitHub Actions runs tests, syntax checks, and Ruff for every push and pull request. The workflow is in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Release checklist

1. Update `APP_VERSION` in `app.py` using semantic versioning.
2. Run the test, compile, and Ruff commands above.
3. Update the current version in this README.
4. Push a release branch and merge it through a passing pull request.

## Contributors

- [butteryjam](https://github.com/butteryjam) — reported the mobile browser compatibility issue.

## Community support

[Open the Otaku Orbit support thread on Discord](https://discord.com/channels/@me/1252520070043668561/1562171196617785464)

## Versioning

Otaku Orbit follows semantic versioning in `MAJOR.MINOR.PATCH` form:

- **Major:** breaking changes
- **Minor:** new backward-compatible features
- **Patch:** bug fixes and small maintenance updates

The application version is defined in `app.py` and updated with each published push.

## License

Otaku Orbit is released under the [MIT License](./LICENSE).

## Technology

Python · Streamlit · AniList GraphQL · SQLite · pytest · GitHub Actions
