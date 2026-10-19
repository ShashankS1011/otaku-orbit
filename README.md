# Otaku Orbit

> Your personal anime command centre — discover, track, and plan your next obsession.

**Otaku Orbit** is a fast, polished anime companion built with Python and Streamlit. It brings AniList discovery, seasonal browsing, personalized recommendations, watchlist progress, and useful viewing statistics into one calm, focused dashboard.

**Made by Shashank — powered by Saiyan spirit**

Current version: `1.1.0`

## Deploy on Streamlit Community Cloud

[Deploy Otaku Orbit on Streamlit Community Cloud](https://share.streamlit.io/)

After signing in with GitHub, create a new app with these settings:

- **Repository:** `ShashankS1011/otaku-orbit`
- **Branch:** `main`
- **Main file path:** `app.py`
- **App URL:** choose `otaku-orbit` if it is available

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

## Test and quality checks

```powershell
python -m pytest -q
python -m py_compile app.py
```

GitHub Actions runs both checks for every push and pull request. The workflow is in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Versioning

Otaku Orbit follows semantic versioning in `MAJOR.MINOR.PATCH` form:

- **Major:** breaking changes
- **Minor:** new backward-compatible features
- **Patch:** bug fixes and small maintenance updates

The application version is defined in `app.py` and updated with each published push.

## Technology

Python · Streamlit · AniList GraphQL · SQLite · pytest · GitHub Actions
