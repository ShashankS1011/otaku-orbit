from __future__ import annotations

import random
import time
from datetime import datetime

import requests
import streamlit as st

from modules import (
    ACHIEVEMENTS,
    AIRING_SCHEDULE_QUERY,
    ANILIST_STATUS_MAP,
    API_CACHE_TTL,
    API_URL,
    APP_NAME,
    APP_URL,
    AUTHOR_CREDIT,
    BACKUP_FORMAT_VERSION,
    DB_PATH,
    DETAIL_QUERY,
    MANGA_STATUSES,
    REQUEST_ATTEMPTS,
    REQUEST_TIMEOUT,
    SEARCH_QUERY,
    SUPPORT_LINK,
    SUPPORTED_TIMEZONES,
    THEME_PALETTES,
    TRENDING_QUERY,
    WATCH_STATUSES,
    AniListRateLimitError,
    _env_float,
    _env_int,
    _format_timestamp,
    _request_session,
    anilist_query,
    anilist_response,
    authentication_configured,
    banner_image_url,
    batch_add_tag,
    batch_remove_anime,
    batch_update_status,
    cache_age_label,
    calculate_runtime_display,
    calculate_watch_streak,
    calculate_watch_velocity,
    call_anilist_response,
    clean_description,
    cover_image_url,
    csv_safe_cell,
    current_owner_id,
    current_season_and_year,
    database_path_for_owner,
    db_rows,
    delete_owner_data,
    display_title,
    estimate_completion_date,
    evaluate_achievements,
    export_watchlist,
    export_watchlist_csv,
    export_watchlist_mal_xml,
    extract_characters_and_seiyuu,
    extract_streaming_links,
    fetch_airing_schedule,
    fetch_anime,
    fetch_anime_detail,
    fetch_anime_page,
    fetch_watch_history,
    filter_anime,
    format_airing,
    format_row_airing,
    format_trailer_url,
    generate_airing_ics,
    generate_music_links,
    get_db_path,
    get_next_airing_countdown,
    import_watchlist,
    increment_watchlist_progress,
    init_db,
    is_safe_cover_url,
    load_with_fallback,
    offline_mode_enabled,
    rank_recommendations,
    record_watch_history,
    remove_anime,
    render_airing_calendar,
    render_analytics,
    render_card,
    render_discover,
    render_filters,
    render_poster_grid,
    render_recommendations,
    render_seasonal,
    render_settings,
    render_stats,
    render_tier_list_maker,
    render_watchlist,
    safe_bar_chart,
    save_anime,
    show_anime_details,
    sync_anilist_profile,
    update_progress,
    validate_backup_row,
    validate_watchlist_state,
)

APP_VERSION = "1.9.0"

__all__ = [
    "ACHIEVEMENTS",
    "AIRING_SCHEDULE_QUERY",
    "ANILIST_STATUS_MAP",
    "API_CACHE_TTL",
    "API_URL",
    "APP_NAME",
    "APP_URL",
    "APP_VERSION",
    "AUTHOR_CREDIT",
    "BACKUP_FORMAT_VERSION",
    "DB_PATH",
    "DETAIL_QUERY",
    "MANGA_STATUSES",
    "REQUEST_ATTEMPTS",
    "REQUEST_TIMEOUT",
    "SEARCH_QUERY",
    "SUPPORT_LINK",
    "SUPPORTED_TIMEZONES",
    "THEME_PALETTES",
    "TRENDING_QUERY",
    "WATCH_STATUSES",
    "AniListRateLimitError",
    "_env_float",
    "_env_int",
    "_format_timestamp",
    "_request_session",
    "anilist_query",
    "anilist_response",
    "authentication_configured",
    "banner_image_url",
    "batch_add_tag",
    "batch_remove_anime",
    "batch_update_status",
    "cache_age_label",
    "calculate_runtime_display",
    "calculate_watch_streak",
    "calculate_watch_velocity",
    "call_anilist_response",
    "clean_description",
    "cover_image_url",
    "csv_safe_cell",
    "current_owner_id",
    "current_season_and_year",
    "database_path_for_owner",
    "datetime",
    "db_rows",
    "delete_owner_data",
    "display_title",
    "estimate_completion_date",
    "evaluate_achievements",
    "export_watchlist",
    "export_watchlist_csv",
    "export_watchlist_mal_xml",
    "extract_characters_and_seiyuu",
    "extract_streaming_links",
    "fetch_airing_schedule",
    "fetch_anime",
    "fetch_anime_detail",
    "fetch_anime_page",
    "fetch_watch_history",
    "filter_anime",
    "format_airing",
    "format_row_airing",
    "format_trailer_url",
    "generate_airing_ics",
    "generate_music_links",
    "get_db_path",
    "get_next_airing_countdown",
    "import_watchlist",
    "increment_watchlist_progress",
    "init_db",
    "is_safe_cover_url",
    "load_with_fallback",
    "offline_mode_enabled",
    "random",
    "rank_recommendations",
    "record_watch_history",
    "remove_anime",
    "render_airing_calendar",
    "render_analytics",
    "render_card",
    "render_discover",
    "render_filters",
    "render_poster_grid",
    "render_recommendations",
    "render_seasonal",
    "render_settings",
    "render_stats",
    "render_tier_list_maker",
    "render_watchlist",
    "safe_bar_chart",
    "save_anime",
    "show_anime_details",
    "st",
    "sync_anilist_profile",
    "time",
    "update_progress",
    "validate_backup_row",
    "validate_watchlist_state",
]


def main() -> None:
    st.set_page_config(
        page_title="Otaku Orbit",
        page_icon="🌌",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    auth_enabled = authentication_configured()
    owner_id = current_owner_id()
    if auth_enabled and owner_id is None:
        st.title("Otaku Orbit")
        st.write("Sign in to access your personal anime watch space.")
        if st.button("Sign in", type="primary"):
            st.login()
        st.stop()

    init_db(owner_id)
    selected_theme = st.session_state.get("theme_palette", "Saiyan Neon")
    theme = THEME_PALETTES.get(selected_theme, THEME_PALETTES["Saiyan Neon"])

    st.markdown(
        f"""<style>
    .block-container {{
        max-width: 1320px;
        padding-top: 2rem;
        padding-bottom: 5rem;
    }}
    [data-testid="stMetricValue"] {{
        color: {theme["metric"]};
        text-shadow: 0 0 16px {theme["glow"]};
    }}
    [data-testid="stSidebar"] {{
        background: {theme["sidebar"]};
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }}
    [data-testid="stHeader"] {{
        background: rgba(0,0,0,0);
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 18px;
        background: rgba(18, 16, 32, 0.45);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s ease, border-color 0.22s ease;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color: {theme["primary"]}66;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35), 0 0 20px {theme["glow"]};
    }}
    .orbit-hero {{
        padding: 1.6rem 1.8rem;
        margin-bottom: 1.4rem;
        border: 1px solid rgba(244, 184, 255, 0.22);
        border-radius: 22px;
        background: radial-gradient(circle at 85% 15%, {theme["glow"]}, transparent 42%), linear-gradient(135deg, #211939 0%, #151526 100%);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    }}
    .orbit-kicker {{
        font-size: .78rem;
        letter-spacing: .2em;
        text-transform: uppercase;
        color: {theme["primary"]};
        font-weight: 700;
    }}
    .orbit-hero h1 {{
        margin: .2rem 0 .4rem;
        font-size: clamp(2rem, 5vw, 3.5rem);
        background: linear-gradient(90deg, #ffffff 0%, {theme["primary"]} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .orbit-muted {{
        color: #b5b3c8;
        max-width: 720px;
        line-height: 1.5;
    }}
    .orbit-credit {{
        position: fixed;
        bottom: 12px;
        left: 0;
        right: 0;
        text-align: center;
        color: #858297;
        font-size: .75rem;
        z-index: 999;
    }}
    :focus-visible {{
        outline: 3px solid {theme["primary"]} !important;
        outline-offset: 2px;
    }}
    @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
            scroll-behavior: auto !important;
            animation-duration: .01ms !important;
            transition-duration: .01ms !important;
        }}
    }}
    @media (max-width: 768px) {{
        .block-container {{
            padding: 1rem .75rem 4rem;
        }}
        .orbit-hero {{
            padding: 1rem;
            border-radius: 16px;
        }}
        .orbit-hero h1 {{
            font-size: 2rem;
            line-height: 1.1;
        }}
        .orbit-credit {{
            font-size: .68rem;
            padding: 0 .5rem;
        }}
    }}
    </style>
<div style="display:none !important;">
<link rel="manifest" href="manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="{theme["primary"]}">
<meta name="application-name" content="Otaku Orbit">
</div>
    """,
        unsafe_allow_html=True,
    )
    rows = db_rows(owner_id)
    saved_ids = {row["anime_id"] for row in rows}

    with st.sidebar:
        st.markdown("# Otaku Orbit")
        st.caption(f"Your personal anime command centre | v{APP_VERSION}")
        st.link_button("Open live app", APP_URL, use_container_width=True)
        st.link_button("Open community support", SUPPORT_LINK, use_container_width=True)
        if auth_enabled:
            st.caption(f"Signed in as {st.user.get('email') or st.user.get('name') or 'account user'}")
            if st.button("Sign out", use_container_width=True):
                st.logout()
        else:
            st.info("Guest mode: data is isolated to this browser session and will not sync to another device.")

        media_mode = st.radio("Media Type", ["Anime", "Manga & Light Novels"], horizontal=True, key="global_media_mode")
        st.session_state["global_media_type"] = "MANGA" if media_mode == "Manga & Light Novels" else "ANIME"

        page = st.radio(
            "Navigate",
            ["Discover", "For you", "Airing Calendar", "Seasonal", "Watchlist", "Analytics & Insights", "Settings"],
            label_visibility="collapsed",
        )
        st.divider()
        st.metric("Saved titles", len(rows))
        st.selectbox("Theme preset", list(THEME_PALETTES.keys()), key="theme_palette")
        st.session_state["daily_goal"] = st.number_input(
            "Daily episode goal", min_value=1, max_value=20, value=st.session_state.get("daily_goal", 3)
        )
        st.session_state["compact_cards"] = st.toggle(
            "Compact cards", value=st.session_state.get("compact_cards", False)
        )
        st.toggle(
            "Show airing reminders",
            value=st.session_state.get("show_airing_reminders", True),
            key="show_airing_reminders",
        )
        st.selectbox(
            "Airing timezone",
            SUPPORTED_TIMEZONES,
            key="display_timezone",
            index=SUPPORTED_TIMEZONES.index(st.session_state.get("display_timezone", "Asia/Kolkata")),
        )
        if st.button("Refresh catalogue data", help="Clear cached AniList responses and fetch fresh data"):
            anilist_response.clear()
            fetch_anime_detail.clear()
            st.session_state.pop("offline_cache", None)
            st.session_state.pop("offline_cache_updated_at", None)
            st.rerun()
        with st.expander("System status"):
            st.caption(f"AniList endpoint: {API_URL}")
            st.caption(f"Request cache: {API_CACHE_TTL} seconds")
            st.caption(f"Local database: {DB_PATH.name}")
            st.caption("Storage mode: private per-account or per-session SQLite")
            st.caption("Cloud-hosted SQLite can reset on redeploy unless a persistent path is configured.")
            if st.button("Check AniList connection"):
                anilist_response.clear()
                with st.spinner("Checking AniList availability"):
                    try:
                        health_data = anilist_response(TRENDING_QUERY, {"type": st.session_state["global_media_type"]})
                        media_count = len(health_data.get("Page", {}).get("media", []))
                        st.success(f"AniList is reachable and returned {media_count} titles.")
                    except (requests.RequestException, RuntimeError) as error:
                        st.error(f"AniList health check failed: {error}")
    st.markdown(f'<div class="orbit-credit">{AUTHOR_CREDIT}</div>', unsafe_allow_html=True)

    reminders_enabled = st.session_state.get("show_airing_reminders", True)
    countdown = get_next_airing_countdown(rows)
    if countdown and reminders_enabled:
        st.info(
            f"📢 **Airing Soon:** **{countdown['title']}** (Episode {countdown['episode']}) broadcasts in **{countdown['hours']}h {countdown['minutes']}m**."
        )

    if page == "Watchlist":
        render_watchlist(owner_id)
    elif page == "Analytics & Insights":
        render_analytics(rows, owner_id)
    elif page == "Settings":
        render_settings(owner_id)
    elif page == "For you":
        render_recommendations(rows, saved_ids, owner_id)
    elif page == "Airing Calendar":
        render_airing_calendar(rows, saved_ids, owner_id)
    elif page == "Discover":
        render_discover(saved_ids, owner_id)
    else:
        render_seasonal(saved_ids, owner_id)


if __name__ == "__main__":
    main()
