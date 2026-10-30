from __future__ import annotations

import logging
import random
import sys
import threading
import time
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import requests
import streamlit as st

from modules.config import (
    ANILIST_STATUS_MAP,
    API_CACHE_TTL,
    API_URL,
    APP_VERSION,
    REQUEST_ATTEMPTS,
    REQUEST_TIMEOUT,
)

logger = logging.getLogger("otaku_orbit")
_http_thread_state = threading.local()


class AniListRateLimitError(requests.RequestException):
    """Raised when AniList asks the app to slow down."""


def _request_session() -> requests.Session:
    app_mod = sys.modules.get("app")
    if app_mod is not None and hasattr(app_mod, "_request_session"):
        candidate = getattr(app_mod, "_request_session")
        if candidate is not _request_session:
            return candidate()
    session = getattr(_http_thread_state, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": f"OtakuOrbit/{APP_VERSION}"})
        _http_thread_state.session = session
    return session


SEARCH_QUERY = """
query ($search: String, $season: MediaSeason, $seasonYear: Int, $page: Int, $isAdult: Boolean, $type: MediaType) {
  Page(page: $page, perPage: 24) {
    pageInfo { hasNextPage }
    media(search: $search, season: $season, seasonYear: $seasonYear, isAdult: $isAdult,
          type: $type, sort: POPULARITY_DESC) {
      id siteUrl title { romaji english native } coverImage { extraLarge large } bannerImage trailer { id site }
      description(asHtml: false) episodes chapters volumes duration status
      averageScore popularity genres season seasonYear format isAdult source
      nextAiringEpisode { airingAt episode }
      studios(isMain: true) { nodes { name } }
    }
  }
}
"""

DETAIL_QUERY = """
query ($id: Int, $type: MediaType) {
  Media(id: $id, type: $type) {
    id siteUrl title { romaji english native } coverImage { extraLarge large } bannerImage trailer { id site }
    description(asHtml: false) episodes chapters volumes duration status averageScore genres
    season seasonYear format isAdult source nextAiringEpisode { airingAt episode }
    studios(isMain: true) { nodes { name } }
    externalLinks { id site url type icon color }
    streamingEpisodes { title thumbnail url site }
    characters(sort: ROLE, perPage: 6) {
      edges {
        role
        node { id name { full native } image { large medium } }
        voiceActors(language: JAPANESE, sort: RELEVANCE) { id name { full native } image { large medium } languageV2 }
      }
      nodes { name { full } }
    }
    staff(sort: RELEVANCE, perPage: 8) { nodes { name { full } primaryOccupations } }
    relations {
      edges {
        relationType(version: 2)
        node {
          id
          title { romaji english native }
          format
          status
          coverImage { extraLarge large }
        }
      }
    }
    recommendations(sort: RATING_DESC, perPage: 6) {
      nodes {
        mediaRecommendation {
          id
          title { romaji english native }
          coverImage { extraLarge large }
          averageScore
          format
        }
      }
    }
  }
}
"""

TRENDING_QUERY = """
query ($type: MediaType) { Page(page: 1, perPage: 24) {
  media(type: $type, sort: TRENDING_DESC) {
    id siteUrl title { romaji english native } coverImage { extraLarge large } bannerImage trailer { id site }
    description(asHtml: false) episodes chapters volumes duration status averageScore popularity genres
    season seasonYear format isAdult source nextAiringEpisode { airingAt episode }
    studios(isMain: true) { nodes { name } }
  }
} }
"""

AIRING_SCHEDULE_QUERY = """
query ($airingAt_greater: Int, $airingAt_lesser: Int) {
  Page(page: 1, perPage: 50) {
    airingSchedules(airingAt_greater: $airingAt_greater, airingAt_lesser: $airingAt_lesser, sort: TIME) {
      id
      airingAt
      episode
      media {
        id siteUrl title { romaji english native } coverImage { extraLarge large } bannerImage trailer { id site }
        description(asHtml: false) episodes chapters volumes duration status averageScore popularity genres format isAdult source
      }
    }
  }
}
"""


@st.cache_data(ttl=API_CACHE_TTL, show_spinner=False)
def anilist_response(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    request_body = {"query": query, "variables": variables or {}}
    response: requests.Response | None = None
    for attempt in range(REQUEST_ATTEMPTS):
        try:
            response = _request_session().post(API_URL, json=request_body, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            break
        except requests.RequestException as error:
            status_code = getattr(response, "status_code", None)
            if status_code == 429:
                logger.warning("AniList rate limit reached on attempt %s", attempt + 1)
                raise AniListRateLimitError(
                    "AniList is rate-limiting requests. Please wait a minute and try again."
                ) from error
            retryable_status = status_code is None or status_code == 429 or status_code >= 500
            if attempt == REQUEST_ATTEMPTS - 1 or not retryable_status:
                logger.error("AniList request failed after %s attempt(s): %s", attempt + 1, error)
                raise
            logger.info("Retrying AniList request after transient failure: attempt %s", attempt + 2)
            backoff = min(8.0, 0.35 * (2**attempt))
            time.sleep(backoff + random.uniform(0.0, backoff * 0.25))
    if response is None:
        raise requests.RequestException("AniList did not return a response")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("AniList returned an invalid response format.")
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "AniList returned an error"))
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise RuntimeError("AniList returned an invalid data payload.")
    return data


def call_anilist_response(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    app_mod = sys.modules.get("app")
    if app_mod is not None and hasattr(app_mod, "anilist_response"):
        fn = getattr(app_mod, "anilist_response")
        if fn != anilist_response:
            return fn(query, variables)
    return anilist_response(query, variables)


def anilist_query(query: str, variables: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = call_anilist_response(query, variables)
    if data.get("Media"):
        return [data["Media"]]
    return data.get("Page", {}).get("media", [])


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_anime_detail(anime_id: int, media_type: str = "ANIME") -> dict[str, Any] | None:
    payload = anilist_query(DETAIL_QUERY, {"id": anime_id, "type": media_type})
    return payload[0] if payload else None


def current_season_and_year(today: date | None = None) -> tuple[str, int]:
    today = today or date.today()
    month = today.month
    season = (
        "WINTER"
        if month in (12, 1, 2)
        else "SPRING"
        if month in (3, 4, 5)
        else "SUMMER"
        if month in (6, 7, 8)
        else "FALL"
    )
    return season, today.year + (1 if month == 12 else 0)


def fetch_anime(
    search: str = "",
    season: str | None = None,
    year: int | None = None,
    page: int = 1,
    is_adult: bool | None = False,
    media_type: str = "ANIME",
) -> list[dict[str, Any]]:
    results, _ = fetch_anime_page(search, season, year, page, is_adult=is_adult, media_type=media_type)
    return results


def fetch_anime_page(
    search: str = "",
    season: str | None = None,
    year: int | None = None,
    page: int = 1,
    is_adult: bool | None = False,
    media_type: str = "ANIME",
) -> tuple[list[dict[str, Any]], bool]:
    variables: dict[str, Any] = {
        "search": search or None,
        "page": page,
        "isAdult": is_adult if is_adult is not None else False,
        "type": media_type,
    }
    if season:
        variables["season"], variables["seasonYear"] = season, year
    data = call_anilist_response(SEARCH_QUERY, variables)
    page_data = data.get("Page", {})
    return page_data.get("media", []), bool(page_data.get("pageInfo", {}).get("hasNextPage"))


def fetch_airing_schedule(start_timestamp: int, end_timestamp: int) -> list[dict[str, Any]]:
    variables = {"airingAt_greater": start_timestamp, "airingAt_lesser": end_timestamp}
    data = call_anilist_response(AIRING_SCHEDULE_QUERY, variables)
    return data.get("Page", {}).get("airingSchedules", [])


def load_with_fallback(cache_key: str, loader: Callable[[], Any]) -> tuple[Any, bool]:
    """Load remote data and fall back to this session's last successful result."""
    offline_cache = st.session_state.setdefault("offline_cache", {})
    try:
        result = loader()
    except (requests.RequestException, RuntimeError):
        if cache_key not in offline_cache:
            raise
        logger.warning("Serving session-cached data after a remote request failed")
        return offline_cache[cache_key], True
    offline_cache[cache_key] = result
    st.session_state.setdefault("offline_cache_updated_at", {})[cache_key] = datetime.now().isoformat(
        timespec="seconds"
    )
    return result, False


def cache_age_label(cache_key: str) -> str:
    cached_at = st.session_state.get("offline_cache_updated_at", {}).get(cache_key)
    if not cached_at:
        return "an unknown time"
    try:
        age_seconds = max(0, int((datetime.now() - datetime.fromisoformat(cached_at)).total_seconds()))
    except (TypeError, ValueError):
        return "an unknown time"
    if age_seconds < 60:
        return "less than a minute ago"
    if age_seconds < 3600:
        return f"{age_seconds // 60} minute(s) ago"
    return f"{age_seconds // 3600} hour(s) ago"


def sync_anilist_profile(username: str, media_type: str = "ANIME", owner_id: str | None = None) -> int:
    from modules.db import save_anime, update_progress

    query = """
    query ($userName: String, $type: MediaType) {
      MediaListCollection(userName: $userName, type: $type) {
        lists {
          entries {
            status
            progress
            score(format: POINT_100)
            repeat
            notes
            media {
              id
              siteUrl
              title { romaji english native }
              coverImage { extraLarge large }
              bannerImage
              episodes
              duration
              averageScore
              genres
              nextAiringEpisode { airingAt episode }
            }
          }
        }
      }
    }
    """
    data = call_anilist_response(query, {"userName": username, "type": media_type})
    collection = data.get("MediaListCollection", {})
    lists = collection.get("lists", [])
    synced = 0
    for lst in lists:
        for entry in lst.get("entries", []):
            media = entry.get("media")
            if not media:
                continue
            anilist_status = entry.get("status", "PLANNING")
            status = ANILIST_STATUS_MAP.get(anilist_status, "PLANNING")
            progress = entry.get("progress") or 0
            score = entry.get("score")
            repeat = entry.get("repeat") or 0
            notes = entry.get("notes") or ""
            save_anime(media, status=status, progress=progress, owner_id=owner_id, rewatches=repeat)
            if score or notes:
                update_progress(
                    media["id"],
                    progress,
                    status,
                    user_score=int(score) if score else None,
                    notes=notes,
                    rewatches=repeat,
                    owner_id=owner_id,
                )
            synced += 1
    return synced
