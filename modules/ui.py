from __future__ import annotations

import json
import random
import time
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests
import streamlit as st

from modules.api import (
    TRENDING_QUERY,
    cache_age_label,
    call_anilist_response,
    current_season_and_year,
    fetch_airing_schedule,
    fetch_anime,
    fetch_anime_detail,
    fetch_anime_page,
    load_with_fallback,
)
from modules.config import (
    ANIME_MOODS,
    CHARACTER_TROPES,
    WATCH_STATUSES,
    offline_mode_enabled,
)
from modules.db import (
    batch_add_tag,
    batch_remove_anime,
    batch_update_status,
    create_user_profile,
    db_rows,
    delete_owner_data,
    export_sqlite_backup_base64,
    fetch_viewing_goal,
    fetch_watch_history,
    import_watchlist,
    increment_watchlist_progress,
    list_user_profiles,
    remove_anime,
    restore_sqlite_backup_base64,
    save_anime,
    set_viewing_goal,
    update_progress,
)
from modules.services import (
    banner_image_url,
    build_seiyuu_character_matrix,
    calculate_drop_off_statistics,
    calculate_era_distribution,
    calculate_runtime_display,
    calculate_seiyuu_screen_time,
    calculate_studio_loyalty_index,
    calculate_user_taste_compatibility,
    calculate_watch_streak,
    calculate_watch_velocity,
    clean_description,
    cover_image_url,
    create_custom_theme_palette,
    display_title,
    estimate_completion_date,
    evaluate_achievements,
    evaluate_bingo_card,
    export_kitsu_json,
    export_simkl_csv,
    export_watchlist,
    export_watchlist_csv,
    export_watchlist_mal_xml,
    extract_characters_and_seiyuu,
    extract_staff_and_directors,
    extract_streaming_links,
    filter_anime,
    filter_by_mood,
    format_airing,
    format_row_airing,
    format_trailer_url,
    generate_airing_ics,
    generate_anime_wrapped_data,
    generate_anime_wrapped_svg,
    generate_bujo_tracker_html,
    generate_bujo_tracker_markdown,
    generate_music_links,
    generate_otaku_passport_svg,
    generate_watchlist_rss_feed,
    get_filler_guide,
    get_franchise_watch_order,
    get_theme_video_links,
    pick_random_backlog,
    rank_recommendations,
)


def render_filters(results: list[dict[str, Any]], key_prefix: str) -> list[dict[str, Any]]:
    genres = sorted({genre for anime in results for genre in anime.get("genres", [])})
    formats = sorted({anime.get("format") for anime in results if anime.get("format")})
    sources = sorted({anime.get("source") for anime in results if anime.get("source")})
    studios = sorted(
        {s["name"] for anime in results for s in anime.get("studios", {}).get("nodes", []) if s.get("name")}
    )
    with st.expander("Filter results & Moods", expanded=False):
        c1, c2, c3 = st.columns(3)
        genre = c1.selectbox("Genre", ["All genres", *genres], key=f"genre-{key_prefix}")
        format_name = c2.selectbox("Format", ["All formats", *formats], key=f"format-{key_prefix}")
        source_val = c3.selectbox("Source Material", ["All sources", *sources], key=f"source-{key_prefix}")

        m_col1, m_col2 = st.columns(2)
        mood_val = m_col1.selectbox("Mood & Vibe", ["All moods", *ANIME_MOODS.keys()], key=f"mood-{key_prefix}")
        if mood_val != "All moods":
            results = filter_by_mood(results, mood_val)

        c4, c5, c6 = st.columns(3)
        studio_val = c4.selectbox("Studio", ["All studios", *studios], key=f"studio-{key_prefix}")
        minimum_score = c5.slider("Minimum score", 0, 90, 0, 5, key=f"score-{key_prefix}")
        include_adult = c6.checkbox("Include mature titles", key=f"adult-{key_prefix}")
    filtered = filter_anime(
        results,
        genre,
        format_name,
        minimum_score,
        include_adult,
        source=source_val,
        studio=studio_val,
    )
    st.caption(f"Showing {len(filtered)} of {len(results)} titles")
    return filtered


@st.dialog("Anime details")
def show_anime_details(anime_id: int) -> None:
    media_type = st.session_state.get("global_media_type", "ANIME")
    try:
        anime = fetch_anime_detail(anime_id, media_type=media_type)
    except (requests.RequestException, RuntimeError) as error:
        st.error(f"Could not load details: {error}")
        return
    if not anime:
        st.info("No details were found for this title.")
        return
    banner_url = banner_image_url(anime)
    if banner_url:
        st.image(banner_url, use_container_width=True)
    title = display_title(anime)
    st.subheader(title)
    cover_col, info_col = st.columns([1, 2], gap="medium")
    with cover_col:
        cover_url = cover_image_url(anime)
        if cover_url:
            st.image(cover_url, caption=f"Cover art for {title}", use_container_width=True)
    with info_col:
        score = anime.get("averageScore")
        source = anime.get("source") or "Original"
        st.caption(
            f"**Format:** {anime.get('format', 'ANIME')} · **Status:** {anime.get('status', 'UNKNOWN')} · **Score:** {score or '—'}/100 · **Source:** {source}"
        )
        st.write(clean_description(anime.get("description")))
        ep_count = anime.get("episodes") or anime.get("chapters")
        count_label = "Episodes" if media_type == "ANIME" else "Chapters"
        st.write(f"**{count_label}:** {ep_count or 'Unknown'} · **Duration:** {anime.get('duration') or 'Unknown'} min")
        st.caption(f"Estimated watch time: {calculate_runtime_display(anime.get('episodes'), anime.get('duration'))}")
        studios = [studio["name"] for studio in anime.get("studios", {}).get("nodes", []) if studio.get("name")]
        if studios:
            st.write("**Studio:** " + ", ".join(studios))

    characters_and_seiyuu = extract_characters_and_seiyuu(anime)
    if characters_and_seiyuu:
        st.divider()
        st.subheader("Characters & Voice Cast (Seiyuu)")
        cast_cols = st.columns(min(len(characters_and_seiyuu[:4]), 4))
        for col, item in zip(cast_cols, characters_and_seiyuu[:4]):
            with col:
                with st.container(border=True):
                    if item.get("char_img"):
                        st.image(item["char_img"], use_container_width=True)
                    st.markdown(f"**{item['character']}**")
                    st.caption(f"Role: {item['role']}")
                    if item.get("seiyuu"):
                        st.caption(f"🎙️ VA: {item['seiyuu']}")

    streaming_links = extract_streaming_links(anime)
    if streaming_links:
        st.divider()
        st.subheader("Where to Stream Legally")
        stream_cols = st.columns(min(len(streaming_links[:4]), 4))
        for col, s_link in zip(stream_cols, streaming_links[:4]):
            col.link_button(f"▶ {s_link['site']}", s_link["url"], use_container_width=True)

    music_links = generate_music_links(title)
    video_links = get_theme_video_links(title)
    st.divider()
    st.subheader("OST & Theme Song Previews")
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.link_button("🎵 Opening on Spotify", music_links["Spotify OP"], use_container_width=True)
    m_col2.link_button("🎵 Ending on Spotify", music_links["Spotify ED"], use_container_width=True)
    m_col3.link_button("▶️ YouTube Music OST", music_links["YouTube Music"], use_container_width=True)

    v_col1, v_col2 = st.columns(2)
    v_col1.link_button("📺 Watch OP on YouTube", video_links["YouTube Search"], use_container_width=True)
    v_col2.link_button("🎬 AnimeThemes Video Previews", video_links["AnimeThemes"], use_container_width=True)

    staff_members = extract_staff_and_directors(anime)
    if staff_members:
        st.divider()
        st.subheader("🎬 Key Production Staff & Directors")
        st.write(", ".join(f"**{m['name']}** ({m['role']})" for m in staff_members[:6]))

    filler_guide = get_filler_guide(title)
    if filler_guide:
        st.divider()
        st.subheader("⚡ Canon vs. Filler Guide")
        st.caption(f"💡 **Tip:** {filler_guide['tip']}")
        f1, f2, f3 = st.columns(3)
        f1.metric("Total Episodes", filler_guide["total"])
        f2.metric("Filler Episodes", filler_guide["filler_count"])
        f3.metric("Filler Percentage", f"{filler_guide['filler_percentage']}%")
        with st.expander("Inspect Filler Ranges & Canon Breakdowns", expanded=False):
            st.write("**Non-Canon Filler Ranges:**")
            st.write(
                ", ".join(
                    f"Episodes {start}-{end}" if start != end else f"Episode {start}"
                    for start, end in filler_guide["filler_ranges"]
                )
            )

    franchise_info = get_franchise_watch_order(title)
    if franchise_info:
        st.divider()
        st.subheader("🗺️ Franchise Chronological Watch Order Guide")
        st.caption(f"💡 **Tip:** {franchise_info['tip']}")
        t_rel, t_chr = st.tabs(["Release Order", "Chronological Story Order"])
        with t_rel:
            for idx, entry in enumerate(franchise_info["release"], 1):
                st.write(f"**{idx}.** {entry}")
        with t_chr:
            for idx, entry in enumerate(franchise_info["chronological"], 1):
                st.write(f"**{idx}.** {entry}")

    relations = [
        edge for edge in anime.get("relations", {}).get("edges", []) if edge.get("node") and edge.get("relationType")
    ]
    if relations:
        st.divider()
        st.subheader("Related Titles")
        rel_cols = st.columns(min(len(relations[:4]), 4))
        for col, edge in zip(rel_cols, relations[:4]):
            rel_node = edge["node"]
            rel_type = edge.get("relationType", "").replace("_", " ").title()
            with col:
                rel_cover = cover_image_url(rel_node)
                if rel_cover:
                    st.image(rel_cover, use_container_width=True)
                st.caption(f"**{rel_type}**\n{display_title(rel_node)}")

    recs = [
        node.get("mediaRecommendation")
        for node in anime.get("recommendations", {}).get("nodes", [])
        if node.get("mediaRecommendation")
    ]
    if recs:
        st.divider()
        st.subheader("Fans Also Liked")
        rec_cols = st.columns(min(len(recs[:4]), 4))
        for col, rec in zip(rec_cols, recs[:4]):
            with col:
                rec_cover = cover_image_url(rec)
                if rec_cover:
                    st.image(rec_cover, use_container_width=True)
                rec_score = f"★ {rec.get('averageScore')}" if rec.get("averageScore") else ""
                st.caption(f"{display_title(rec)} {rec_score}")

    site_url = anime.get("siteUrl") or f"https://anilist.co/anime/{anime_id}"
    trailer_url = format_trailer_url(anime.get("trailer"))
    btn_cols = st.columns(2 if trailer_url else 1)
    btn_cols[0].link_button("View on AniList", site_url, use_container_width=True)
    if trailer_url:
        btn_cols[1].link_button("Watch Trailer", trailer_url, use_container_width=True)


def render_card(anime: dict[str, Any], saved_ids: set[int], key_prefix: str, owner_id: str | None = None) -> None:
    title = display_title(anime)
    compact = st.session_state.get("compact_cards", False)
    image, details = st.columns([0.9, 2.3] if compact else [1, 2.2], gap="medium")
    with image:
        cover_url = cover_image_url(anime)
        if cover_url:
            st.image(cover_url, caption=f"Cover art for {title}", use_container_width=True)
    with details:
        st.subheader(title)
        score = anime.get("averageScore")
        source = anime.get("source") or "Original"
        meta = (
            f"{anime.get('format', 'ANIME')}  ·  {anime.get('status', 'UNKNOWN')}  ·  {score or '—'}/100  ·  {source}"
        )
        st.caption(meta)
        st.write(clean_description(anime.get("description"))[:420] + "…")
        genres = anime.get("genres", [])
        if genres:
            st.caption(" · ".join(genres))
        if anime.get("nextAiringEpisode"):
            st.info(format_airing(anime, st.session_state.get("display_timezone", "Asia/Kolkata")))
        if st.button(
            f"Details: {title}",
            key=f"details-{key_prefix}-{anime['id']}",
            help=f"Open full details for {title}",
            use_container_width=True,
        ):
            show_anime_details(anime["id"])
        if anime["id"] in saved_ids:
            st.success("In your watchlist")
        else:
            if st.button(
                f"Add {title} to watchlist",
                key=f"add-{key_prefix}-{anime['id']}",
                help=f"Save {title} to your watchlist",
                use_container_width=True,
            ):
                save_anime(anime, owner_id=owner_id)
                st.rerun()


def render_poster_grid(
    results: list[dict[str, Any]],
    saved_ids: set[int],
    key_prefix: str,
    owner_id: str | None = None,
    columns_per_row: int = 4,
) -> None:
    if not results:
        st.info("No titles match the current filters.")
        return
    for i in range(0, len(results), columns_per_row):
        cols = st.columns(columns_per_row)
        for col, anime in zip(cols, results[i : i + columns_per_row]):
            with col:
                with st.container(border=True):
                    title = display_title(anime)
                    cover_url = cover_image_url(anime)
                    if cover_url:
                        st.image(
                            cover_url, caption=title[:30] + ("…" if len(title) > 30 else ""), use_container_width=True
                        )
                    score = anime.get("averageScore")
                    score_badge = f"★ {score}" if score else "Unrated"
                    st.caption(f"{anime.get('format', 'TV')} · {score_badge}")
                    btn_a, btn_b = st.columns(2)
                    if btn_a.button("Details", key=f"pdet-{key_prefix}-{anime['id']}", use_container_width=True):
                        show_anime_details(anime["id"])
                    if anime["id"] in saved_ids:
                        btn_b.caption("✓ In List")
                    else:
                        if btn_b.button("+ Add", key=f"padd-{key_prefix}-{anime['id']}", use_container_width=True):
                            save_anime(anime, owner_id=owner_id)
                            st.rerun()


def render_airing_calendar(rows: list[dict[str, Any]], saved_ids: set[int], owner_id: str | None = None) -> None:
    st.title("Airing Calendar")
    st.caption("Track new anime episodes releasing this week in your timezone.")
    timezone_name = st.session_state.get("display_timezone", "Asia/Kolkata")
    now_ts = int(time.time())
    start_ts = now_ts - 7200
    end_ts = now_ts + 7 * 86400

    ics_content = generate_airing_ics(rows)
    st.download_button(
        "📅 Export Airing Schedule (.ics)",
        ics_content,
        "otaku_orbit_airing.ics",
        "text/calendar",
        help="Subscribe in Apple Calendar, Google Calendar, or Outlook",
    )

    if offline_mode_enabled():
        st.info("Offline mode is enabled; airing schedule requests are disabled.")
        return
    try:
        schedules, from_cache = load_with_fallback(
            f"airing_schedule:{start_ts // 86400}",
            lambda: fetch_airing_schedule(start_ts, end_ts),
        )
        if from_cache:
            st.info(f"Showing cached airing schedule from {cache_age_label(f'airing_schedule:{start_ts // 86400}')}.")
    except (requests.RequestException, RuntimeError) as error:
        st.error(f"Could not load airing schedule: {error}")
        return
    if not schedules:
        st.info("No upcoming episodes scheduled for this week.")
        return
    watchlist_only = st.toggle("Show only anime in my watchlist", value=False, key="calendar_watchlist_only")
    filtered_schedules = []
    for item in schedules:
        media = item.get("media") or {}
        if watchlist_only and media.get("id") not in saved_ids:
            continue
        filtered_schedules.append(item)
    if not filtered_schedules:
        st.info("No airing episodes found matching the filter.")
        return
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in filtered_schedules:
        airing_at = item.get("airingAt", 0)
        dt = datetime.fromtimestamp(airing_at, tz)
        day_key = dt.strftime("%A, %d %b")
        today_str = datetime.now(tz).strftime("%A, %d %b")
        day_label = f"🔥 Today ({day_key})" if day_key == today_str else day_key
        grouped.setdefault(day_label, []).append(item)
    for day_label, items in grouped.items():
        st.subheader(day_label)
        cols_per_row = 3
        for i in range(0, len(items), cols_per_row):
            row_cols = st.columns(cols_per_row)
            for col, item in zip(row_cols, items[i : i + cols_per_row]):
                media = item.get("media") or {}
                anime_id = media.get("id")
                episode = item.get("episode")
                airing_at = item.get("airingAt", 0)
                dt = datetime.fromtimestamp(airing_at, tz)
                time_str = dt.strftime("%H:%M")
                with col:
                    with st.container(border=True):
                        title = display_title(media)
                        cover_url = cover_image_url(media)
                        if cover_url:
                            st.image(cover_url, use_container_width=True)
                        st.markdown(f"**{title}**")
                        st.caption(f"**Ep {episode}** · **{time_str}** ({timezone_name})")
                        if anime_id in saved_ids:
                            st.success("★ In your watchlist")
                        else:
                            if st.button("Add to watchlist", key=f"cal-add-{item.get('id')}", use_container_width=True):
                                save_anime(media, owner_id=owner_id)
                                st.rerun()
                        if st.button("Details", key=f"cal-det-{item.get('id')}", use_container_width=True):
                            show_anime_details(anime_id)
        st.divider()


def render_tier_list_maker(rows: list[dict[str, Any]]) -> None:
    st.subheader("Tier List Maker")
    st.caption("Organize your collection into S, A, B, C, and D tiers based on your ratings.")
    tiers: dict[str, list[dict[str, Any]]] = {
        "S Tier (Masterpiece)": [],
        "A Tier (Great)": [],
        "B Tier (Good)": [],
        "C Tier (Average)": [],
        "D Tier (Disappointing)": [],
    }
    for row in rows:
        score = row.get("user_score")
        if score is not None and score >= 90:
            tiers["S Tier (Masterpiece)"].append(row)
        elif score is not None and score >= 80:
            tiers["A Tier (Great)"].append(row)
        elif score is not None and score >= 70:
            tiers["B Tier (Good)"].append(row)
        elif score is not None and score >= 50:
            tiers["C Tier (Average)"].append(row)
        elif score is not None and score > 0:
            tiers["D Tier (Disappointing)"].append(row)
        else:
            tiers["B Tier (Good)"].append(row)

    tier_colors = {
        "S Tier (Masterpiece)": "#ff7f7f",
        "A Tier (Great)": "#ffbf7f",
        "B Tier (Good)": "#ffff7f",
        "C Tier (Average)": "#7fff7f",
        "D Tier (Disappointing)": "#7fbfff",
    }
    for tier_name, tier_items in tiers.items():
        color = tier_colors[tier_name]
        st.markdown(
            f'<div style="background:{color}; color:#111; font-weight:bold; padding:6px 14px; border-radius:8px; margin:10px 0 6px;">{tier_name} ({len(tier_items)})</div>',
            unsafe_allow_html=True,
        )
        if tier_items:
            t_cols = st.columns(min(len(tier_items), 6))
            for col, item in zip(t_cols, tier_items[:6]):
                with col:
                    img = item.get("image")
                    if img:
                        st.image(img, use_container_width=True)
                    st.caption(item.get("title", "")[:24])
        else:
            st.caption("No titles placed in this tier.")


def safe_bar_chart(data: dict[str, Any]) -> None:
    """Render st.bar_chart with a native Streamlit fallback if Altair/Vega fails."""
    try:
        st.bar_chart(data)
    except Exception:
        max_val = max((float(v) for v in data.values() if isinstance(v, (int, float))), default=1.0)
        max_val = max(max_val, 1.0)
        for label, val in data.items():
            val_num = float(val) if isinstance(val, (int, float)) else 0.0
            ratio = min(1.0, max(0.0, val_num / max_val))
            c_label, c_bar = st.columns([1, 3])
            c_label.write(f"**{label}** ({val})")
            c_bar.progress(ratio)


def render_analytics(rows: list[dict[str, Any]], owner_id: str | None = None) -> None:
    st.title("Analytics & Insights")
    st.caption("Deep dive into your viewing journey, habits, achievements, and pacing.")
    if not rows:
        st.info("Add titles to your watchlist to unlock viewing analytics.")
        return
    history = fetch_watch_history(days=60, owner_id=owner_id)
    completed_episodes = sum(row.get("progress", 0) for row in rows)
    watched_minutes = sum(
        min(row.get("progress", 0), row.get("episodes") or row.get("progress", 0)) * (row.get("duration") or 24)
        for row in rows
    )
    streak = calculate_watch_streak(history)
    velocity = calculate_watch_velocity(history)
    rated_rows = [r for r in rows if r.get("user_score")]
    avg_user_score = round(sum(r["user_score"] for r in rated_rows) / len(rated_rows), 1) if rated_rows else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Titles Tracked", len(rows))
    c2.metric("Episodes Logged", completed_episodes)
    c3.metric("Time Watched", f"{watched_minutes // 60}h")
    c4.metric("Active Streak", f"{streak} day{'s' if streak != 1 else ''}", delta="🔥")
    c5.metric("Watching Pace", f"{velocity} eps/day")

    st.divider()

    active_watching = [r for r in rows if r.get("status") in {"WATCHING", "REWATCHING"} and r.get("episodes")]
    if active_watching:
        st.subheader("Completion Forecast")
        st.caption(f"Based on your current velocity (~{velocity} eps/day):")
        f_cols = st.columns(min(len(active_watching[:3]), 3))
        for col, row in zip(f_cols, active_watching[:3]):
            rem_eps = max(row["episodes"] - row["progress"], 0)
            est_date = estimate_completion_date(rem_eps, velocity)
            with col:
                with st.container(border=True):
                    st.markdown(f"**{row['title']}**")
                    st.caption(f"Progress: {row['progress']}/{row['episodes']} ({rem_eps} left)")
                    st.write(f"🎯 Est. Finish: **{est_date or 'Complete!'}**" if est_date else "Complete!")
        st.divider()

    if rated_rows:
        st.subheader("Rating Distribution")
        score_bins = {f"{i * 10}-{(i + 1) * 10}": 0 for i in range(1, 10)}
        score_bins["90-100"] = 0
        for r in rated_rows:
            s = r["user_score"]
            if s >= 90:
                score_bins["90-100"] += 1
            else:
                b_key = f"{(s // 10) * 10}-{(s // 10 + 1) * 10}"
                if b_key in score_bins:
                    score_bins[b_key] += 1
        safe_bar_chart(score_bins)
        st.caption(f"Mean personal score: **{avg_user_score}/100** across {len(rated_rows)} rated titles.")
        st.divider()

    genre_counts: dict[str, int] = {}
    for row in rows:
        for genre in filter(None, (row.get("genres") or "").split(", ")):
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    if genre_counts:
        st.subheader("Genre Profile")
        safe_bar_chart(dict(sorted(genre_counts.items(), key=lambda item: item[1], reverse=True)[:10]))
        st.divider()

    st.subheader("Viewing Activity Log (Recent 30 Days)")
    if history:
        day_counts: dict[str, int] = {}
        for h in history:
            day = h.get("watched_at", "")[:10]
            if day:
                day_counts[day] = day_counts.get(day, 0) + 1
        recent_30_days = [(date.today() - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
        heatmap_data = {d: day_counts.get(d, 0) for d in recent_30_days}
        safe_bar_chart(heatmap_data)
    else:
        st.info("Watch history will record daily as you log progress with +1 Ep.")
    st.divider()

    st.subheader("Achievements & Milestones")
    achievements = evaluate_achievements(rows, history)
    cols_per_row = 4
    for i in range(0, len(achievements), cols_per_row):
        b_cols = st.columns(cols_per_row)
        for col, ach in zip(b_cols, achievements[i : i + cols_per_row]):
            with col:
                with st.container(border=True):
                    badge_status = "✨ Unlocked" if ach["unlocked"] else "🔒 Locked"
                    st.markdown(f"### {ach['icon']} {ach['title']}")
                    st.caption(ach["desc"])
                    if ach["unlocked"]:
                        st.success(badge_status)
                    else:
                        st.caption(badge_status)
    st.divider()

    with st.expander("🎯 Anime Bingo Challenge Matrix (5x5)", expanded=False):
        st.caption("Complete rows, columns, or diagonals across these 25 challenges:")
        bingo_items = evaluate_bingo_card(rows, history)
        for r_idx in range(5):
            b_cols = st.columns(5)
            for c_idx in range(5):
                item = bingo_items[r_idx * 5 + c_idx]
                badge = "✅" if item["completed"] else "⬜"
                b_cols[c_idx].markdown(f"**{badge}** {item['text']}")

    with st.expander("⏱️ Weekly Viewing Habit Goal", expanded=False):
        goal_data = fetch_viewing_goal(owner_id)
        current_target = goal_data["target_count"] if goal_data else 10
        g_col1, g_col2 = st.columns([2, 1])
        new_target = g_col1.number_input(
            "Target episodes per week", min_value=1, max_value=100, value=current_target, key="habit_goal_target"
        )
        if g_col2.button("Save Habit Target", use_container_width=True):
            set_viewing_goal(new_target, "WEEKLY", owner_id)
            st.success("Target updated!")
        this_week_logged = sum(
            1 for h in history if (datetime.now() - datetime.fromisoformat(h.get("watched_at", "2000-01-01"))).days <= 7
        )
        ratio = min(1.0, this_week_logged / max(1, current_target))
        st.write(f"**Weekly Progress:** {this_week_logged} / {current_target} episodes ({int(ratio * 100)}%)")
        st.progress(ratio)

    with st.expander("🎙️ Seiyuu Character Relationship Matrix", expanded=False):
        matrix = build_seiyuu_character_matrix(rows)
        multi_voice = {k: v for k, v in matrix.items() if len(v) >= 2}
        if multi_voice:
            for actor, roles in list(multi_voice.items())[:8]:
                roles_fmt = " · ".join(f"**{r['character']}** (*{r['anime']}*)" for r in roles)
                st.write(f"🎙️ **{actor}**: {roles_fmt}")
        else:
            st.info("Log more titles with Japanese voice actors to view your personal cast cross-over matrix.")

    with st.expander("🎁 Spotify-Style Anime Wrapped (Annual Dossier)", expanded=False):
        st.caption("Generate your shareable annual anime infographic card:")
        wrapped_data = generate_anime_wrapped_data(rows, history)
        wrapped_svg = generate_anime_wrapped_svg(wrapped_data)
        st.download_button(
            "🎴 Download Anime Wrapped Infographic (.svg)",
            wrapped_svg,
            file_name="otaku_orbit_wrapped.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )
        st.write(
            f"**Assigned Archetype:** {wrapped_data['archetype']['icon']} **{wrapped_data['archetype']['title']}** ({wrapped_data['archetype']['tagline']})"
        )
        st.write(
            f"**Total Screen Time:** {wrapped_data['total_hours']} Hours across {wrapped_data['total_episodes']} episodes"
        )

    with st.expander("🏢 Animation Studio Loyalty & Seiyuu Screen-Time", expanded=False):
        loyalty = calculate_studio_loyalty_index(rows)
        if loyalty:
            for studio_name, s_data in list(loyalty.items())[:6]:
                score_str = f"⭐ {s_data['avg_score']}/100" if s_data["avg_score"] else "Unrated"
                st.write(
                    f"**{studio_name}**: {s_data['titles']} titles tracked · {s_data['episodes']} eps · {score_str}"
                )
        st.divider()
        st.caption("🎙️ Cumulative Seiyuu (Voice Actor) Listening Time:")
        seiyuu_times = calculate_seiyuu_screen_time(rows)
        for st_item in seiyuu_times[:5]:
            st.write(f"🎙️ **{st_item['actor']}**: {st_item['hours']} hours ({st_item['minutes']} mins)")

    with st.expander("📉 The 3-Episode Rule & Drop-off Statistics", expanded=False):
        drop_stats = calculate_drop_off_statistics(rows)
        st.write(f"**Total Dropped Series:** {drop_stats['dropped_count']} ({drop_stats['drop_rate_pct']}% drop rate)")
        st.write(f"**The 3-Episode Rule Drop Rate:** {drop_stats['rule_of_three_pct']}% dropped on or before ep 3")
        st.write(f"**Median Drop Episode:** Episode {drop_stats['median_drop_episode']}")

    with st.expander("⏳ Historical Era & Decade Chronology", expanded=False):
        eras = calculate_era_distribution(rows)
        for era_name, count in eras.items():
            st.write(f"**{era_name}**: {count} titles")

    render_tier_list_maker(rows)


def render_watchlist(owner_id: str | None = None) -> None:
    rows = db_rows(owner_id)
    st.title("Your library")
    if not rows:
        with st.container(border=True):
            st.markdown("### 🌱 Your training arc starts here!")
            st.info("Your watchlist is empty. Discover new anime and manga to track your progress.")
            st.caption("Tip: Use the Discover or Seasonal tabs to explore top-rated shows and add them to your orbit.")
        return
    counts = {status: sum(row["status"] == status for row in rows) for status in WATCH_STATUSES}
    cols = st.columns(len(WATCH_STATUSES))
    for column, (label, value) in zip(cols, counts.items()):
        column.metric(label.title(), value)
    with st.expander("Batch actions", expanded=False):
        batch_options = [f"{row['title']} (ID: {row['anime_id']})" for row in rows]
        selected_labels = st.multiselect("Select titles for batch actions", batch_options, key="batch_selected")
        selected_ids = []
        for label in selected_labels:
            try:
                anime_id = int(label.split("(ID: ")[-1].rstrip(")"))
                selected_ids.append(anime_id)
            except (ValueError, IndexError):
                pass
        b_col1, b_col2, b_col3 = st.columns(3)
        batch_new_status = b_col1.selectbox("Set status", WATCH_STATUSES, key="batch_new_status")
        if b_col1.button("Apply status", use_container_width=True) and selected_ids:
            batch_update_status(selected_ids, batch_new_status, owner_id)
            st.success(f"Updated status for {len(selected_ids)} title(s).")
            st.rerun()
        batch_new_tag = b_col2.text_input("Add tag", placeholder="e.g. Masterpiece", key="batch_new_tag")
        if b_col2.button("Apply tag", use_container_width=True) and selected_ids and batch_new_tag.strip():
            batch_add_tag(selected_ids, batch_new_tag.strip(), owner_id)
            st.success(f"Added tag '{batch_new_tag.strip()}' to {len(selected_ids)} title(s).")
            st.rerun()
        if b_col3.button("Remove selected", type="secondary", use_container_width=True) and selected_ids:
            batch_remove_anime(selected_ids, owner_id)
            st.success(f"Removed {len(selected_ids)} title(s).")
            st.rerun()
    st.divider()
    sort_order = st.selectbox(
        "Sort saved titles",
        ["Recently updated", "Title", "AniList score", "My rating", "Progress", "Runtime remaining"],
        key="watchlist-sort",
    )
    if sort_order == "Recently updated":
        rows.sort(key=lambda row: row.get("updated_at") or "", reverse=True)
    elif sort_order == "Title":
        rows.sort(key=lambda row: row["title"].lower())
    elif sort_order == "AniList score":
        rows.sort(key=lambda row: row["score"] or 0, reverse=True)
    elif sort_order == "My rating":
        rows.sort(key=lambda row: row.get("user_score") or 0, reverse=True)
    elif sort_order == "Progress":
        rows.sort(key=lambda row: row["progress"], reverse=True)
    elif sort_order == "Runtime remaining":
        rows.sort(
            key=lambda row: (
                max((row.get("episodes") or row["progress"]) - row["progress"], 0) * (row.get("duration") or 24)
            )
        )
    active = [row for row in rows if row["status"] in {"WATCHING", "REWATCHING"}]
    goal = st.session_state.get("daily_goal", 3)
    if active:
        st.subheader("Continue watching")
        st.caption(f"Your next episodes are always at the top of the orbit. Goal: {goal} episode(s) per day.")
        for row in active[:3]:
            total = row["episodes"] or 0
            progress = row["progress"]
            remaining = max(total - progress, 0) if total else "?"
            st.write(f"**{row['title']}** · episode {progress + 1} next · {remaining} remaining")
            if total:
                st.caption(f"Remaining watch time: {calculate_runtime_display(total, row.get('duration'), progress)}")
        st.divider()
    timezone_name = st.session_state.get("display_timezone", "Asia/Kolkata")
    reminders_enabled = st.session_state.get("show_airing_reminders", True)
    reminders = [
        (row["title"], format_row_airing(row, timezone_name))
        for row in rows
        if reminders_enabled and format_row_airing(row, timezone_name)
    ]
    if reminders:
        st.subheader("Upcoming airing reminders")
        for title, airing in reminders[:5]:
            st.info(f"**{title}** · {airing}")
        st.divider()
    st.subheader("All saved titles")
    all_tags = sorted({t.strip() for r in rows for t in (r.get("tags") or "").split(",") if t.strip()})
    f_col1, f_col2, f_col3 = st.columns(3)
    search = f_col1.text_input("🔍 Quick filter watchlist", placeholder="Filter by title, tag, or notes…")
    status_filter = f_col2.selectbox("Status", ["All statuses", *WATCH_STATUSES])
    tag_filter = f_col3.selectbox("Tag", ["All tags", *all_tags] if all_tags else ["All tags"])
    visible_rows = [
        row
        for row in rows
        if (
            not search
            or search.lower() in row["title"].lower()
            or search.lower() in (row.get("tags") or "").lower()
            or search.lower() in (row.get("notes") or "").lower()
            or search.lower() in (row.get("genres") or "").lower()
        )
        and (status_filter == "All statuses" or row["status"] == status_filter)
        and (
            tag_filter == "All tags"
            or tag_filter in [t.strip() for t in (row.get("tags") or "").split(",") if t.strip()]
        )
    ]
    st.caption(f"Showing {len(visible_rows)} of {len(rows)} titles")
    for row in visible_rows:
        left, right = st.columns([3, 2])
        with left:
            if row.get("image"):
                c_img, c_info = st.columns([1, 3.5])
                with c_img:
                    st.image(row["image"], use_container_width=True)
                with c_info:
                    st.subheader(row["title"])
            else:
                st.subheader(row["title"])
            total = row["episodes"] or 0
            progress = row["progress"]
            st.progress(min(progress / total, 1.0) if total else 0.0, text=f"Episode {progress}/{total or '?'}")
            user_score_display = f"{row['user_score']}/100" if row.get("user_score") else "Not rated"
            meta_parts = [f"AniList: {row['score'] or '—'}", f"My score: {user_score_display}"]
            if row.get("rewatches"):
                meta_parts.append(f"Rewatched: {row['rewatches']}x")
            if row.get("tags"):
                meta_parts.append(f"Tags: {row['tags']}")
            st.caption(" · ".join(meta_parts))
            st.caption(f"{row['genres'] or 'Genre unknown'}")
            if row.get("notes"):
                st.caption(f"Notes: {row['notes']}")
        with right:
            status = st.selectbox(
                "Status", WATCH_STATUSES, index=WATCH_STATUSES.index(row["status"]), key=f"status-{row['anime_id']}"
            )
            p_col, r_col = st.columns(2)
            new_progress = p_col.number_input(
                "Episodes watched",
                min_value=0,
                max_value=row["episodes"] or 9999,
                value=row["progress"],
                key=f"progress-{row['anime_id']}",
            )
            rewatches_val = r_col.number_input(
                "Rewatch count",
                min_value=0,
                max_value=999,
                value=int(row.get("rewatches") or 0),
                key=f"rewatch-{row['anime_id']}",
            )
            my_score = st.number_input(
                "My rating (0-100)",
                min_value=0,
                max_value=100,
                value=int(row.get("user_score") or 0),
                key=f"userscore-{row['anime_id']}",
            )
            tags_val = st.text_input(
                "Tags",
                value=row.get("tags") or "",
                placeholder="e.g. Masterpiece, Cozy",
                max_chars=500,
                key=f"tags-{row['anime_id']}",
            )
            notes_val = st.text_input(
                "Notes",
                value=row.get("notes") or "",
                placeholder="Thoughts, reviews…",
                max_chars=5000,
                key=f"notes-{row['anime_id']}",
            )
            a, b, c = st.columns([1, 1, 1])
            if a.button("+1 Ep", key=f"inc-{row['anime_id']}", use_container_width=True):
                increment_watchlist_progress(row["anime_id"], owner_id)
                st.rerun()
            if b.button("Save", key=f"save-{row['anime_id']}", use_container_width=True):
                update_progress(
                    row["anime_id"],
                    int(new_progress),
                    status,
                    user_score=int(my_score),
                    notes=notes_val.strip(),
                    rewatches=int(rewatches_val),
                    tags=tags_val.strip(),
                    owner_id=owner_id,
                )
                st.rerun()
            if c.button("Remove", key=f"remove-{row['anime_id']}", use_container_width=True):
                remove_anime(row["anime_id"], owner_id)
                st.rerun()
        st.divider()
    if not visible_rows:
        st.info("No saved titles match those filters.")
    with st.expander("Backup your watchlist & Export Passport"):
        st.caption("Export a portable backup, generate your Otaku ID Passport, or export to Kitsu / SIMKL.")
        passport_svg = generate_otaku_passport_svg("Otaku Explorer", rows)
        st.download_button(
            "🪪 Download Otaku ID Passport (.svg)",
            passport_svg,
            file_name="otaku_orbit_passport.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )
        d_col1, d_col2, d_col3 = st.columns(3)
        d_col1.download_button(
            "Download JSON",
            export_watchlist(rows),
            "otaku-orbit-watchlist.json",
            "application/json",
            use_container_width=True,
        )
        d_col2.download_button(
            "Download CSV",
            export_watchlist_csv(rows),
            "otaku-orbit-watchlist.csv",
            "text/csv",
            use_container_width=True,
        )
        d_col3.download_button(
            "Download MAL XML",
            export_watchlist_mal_xml(rows),
            "otaku-orbit-mal.xml",
            "application/xml",
            use_container_width=True,
        )
        c_kitsu, c_simkl = st.columns(2)
        c_kitsu.download_button(
            "Export Kitsu JSON",
            export_kitsu_json(rows),
            file_name="otaku_orbit_kitsu.json",
            mime="application/json",
            use_container_width=True,
        )
        c_simkl.download_button(
            "Export SIMKL CSV",
            export_simkl_csv(rows),
            file_name="otaku_orbit_simkl.csv",
            mime="text/csv",
            use_container_width=True,
        )
        c_bujo1, c_bujo2 = st.columns(2)
        c_bujo1.download_button(
            "📓 Printable Bullet Journal (.md)",
            generate_bujo_tracker_markdown(rows),
            file_name="otaku_orbit_bullet_journal.md",
            mime="text/markdown",
            use_container_width=True,
        )
        c_bujo2.download_button(
            "🖨️ Printable Tracker (.html)",
            generate_bujo_tracker_html(rows),
            file_name="otaku_orbit_tracker.html",
            mime="text/html",
            use_container_width=True,
        )
        st.download_button(
            "📡 Personal Airing Schedule RSS Feed (.xml)",
            generate_watchlist_rss_feed(rows),
            file_name="otaku_orbit_watchlist_rss.xml",
            mime="application/rss+xml",
            use_container_width=True,
        )

        uploaded = st.file_uploader("Restore JSON backup", type="json")
        if uploaded is not None and st.button("Restore backup", use_container_width=True):
            try:
                count = import_watchlist(uploaded.getvalue().decode("utf-8"), owner_id)
                st.success(f"Restored {count} title(s).")
                st.rerun()
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
                st.error(f"Could not restore that backup: {error}")


def render_stats(rows: list[dict[str, Any]]) -> None:
    st.title("Your anime statistics")
    if not rows:
        st.info("Add a few anime to see your personal statistics.")
        return
    completed_episodes = sum(row["progress"] for row in rows)
    minutes = sum((row["episodes"] or 0) * (row.get("duration") or 24) for row in rows)
    watched_minutes = sum(
        min(row["progress"], row["episodes"] or row["progress"]) * (row.get("duration") or 24) for row in rows
    )
    cols = st.columns(4)
    cols[0].metric("Titles", len(rows))
    cols[1].metric("Episodes watched", completed_episodes)
    cols[2].metric("Time watched", f"{watched_minutes // 60}h")
    cols[3].metric("Time in backlog", f"{max(minutes - watched_minutes, 0) // 60}h")
    genre_counts: dict[str, int] = {}
    for row in rows:
        for genre in filter(None, row["genres"].split(", ")):
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    if genre_counts:
        st.subheader("Your genre profile")
        safe_bar_chart(dict(sorted(genre_counts.items(), key=lambda item: item[1], reverse=True)[:10]))


def render_recommendations(rows: list[dict[str, Any]], saved_ids: set[int], owner_id: str | None = None) -> None:
    st.title("Picked for you")
    with st.expander("🎡 Anime Wheel of Fortune (Backlog Decision Maker)", expanded=False):
        st.caption("Can't decide what to watch next from your backlog? Let fate choose!")
        w1, w2 = st.columns(2)
        w_mood = w1.selectbox("Filter by Mood", ["Any Mood", *ANIME_MOODS.keys()], key="wheel_mood_select")
        w_dur = w2.number_input(
            "Max Episode Duration (mins)", min_value=1, max_value=180, value=30, key="wheel_dur_input"
        )
        if st.button("🎰 Spin the Wheel!", type="primary", use_container_width=True):
            picked = pick_random_backlog(rows, mood=w_mood if w_mood != "Any Mood" else None, max_duration=w_dur)
            if picked:
                st.session_state["wheel_picked_title"] = picked
        if st.session_state.get("wheel_picked_title"):
            p = st.session_state["wheel_picked_title"]
            st.success(
                f"🎯 **Your Next Destiny:** **{p.get('title')}** (Status: {p.get('status')} | {p.get('genres', '')})"
            )
    if not rows:
        st.info("Save a few anime first and your recommendations will learn your taste.")
        return
    preferred = {genre.strip() for row in rows for genre in row["genres"].split(",") if genre.strip()}
    st.write(
        "Recommendations are weighted by your ratings, progress, and favorite genres: "
        + ", ".join(sorted(preferred))
        + "."
    )
    try:
        candidates = call_anilist_response(TRENDING_QUERY, {"type": "ANIME"}).get("Page", {}).get("media", [])
    except (requests.RequestException, RuntimeError) as error:
        st.error(f"Could not load recommendations right now: {error}")
        return
    for anime in rank_recommendations(rows, candidates, saved_ids):
        with st.container(border=True):
            render_card(anime, saved_ids, "recommendation", owner_id)


def render_settings(owner_id: str | None = None) -> None:
    st.title("Settings & Integrations")
    st.caption("Configure personal preferences, theme presets, integrations, and mobile settings.")

    with st.expander("AniList 1-Click Library Synchronization", expanded=True):
        st.caption("Import your public library directly from AniList into your Otaku Orbit database.")
        from modules.api import sync_anilist_profile

        anilist_user = st.text_input("AniList Username", placeholder="e.g. ShashankS1011")
        sync_type = st.radio("Sync Media", ["ANIME", "MANGA"], horizontal=True, key="sync_media_type")
        if st.button("Synchronize Library", type="primary") and anilist_user.strip():
            with st.spinner("Fetching AniList library..."):
                try:
                    count = sync_anilist_profile(anilist_user.strip(), sync_type, owner_id)
                    st.success(f"Synchronized {count} title(s) from AniList.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Synchronization failed: {error}")

    with st.expander("👥 Two-User Taste Compatibility Matcher"):
        st.caption("Compare your anime library against a friend's library backup JSON to see your match score:")
        friend_file = st.file_uploader("Upload Friend's Library JSON", type=["json"], key="friend_lib_upload")
        if friend_file:
            try:
                friend_data = json.loads(friend_file.read().decode("utf-8"))
                f_items = friend_data.get("items", friend_data)
                rows_current = db_rows(owner_id)
                compat = calculate_user_taste_compatibility(rows_current, f_items)
                st.success(f"💖 **Taste Compatibility: {compat['compatibility_pct']}%**")
                st.caption(compat["summary"])
                if compat["recommendations"]:
                    st.write(
                        "**Top picks from your friend's library for you:** " + ", ".join(compat["recommendations"])
                    )
            except Exception as error:
                st.error(f"Could not compare libraries: {error}")

    with st.expander("☁️ Cloud SQLite Database Snapshot (Zero Data Loss)"):
        st.caption("Export or restore the entire raw SQLite database as an encoded base64 string:")
        b64_db = export_sqlite_backup_base64(owner_id)
        st.download_button(
            "Download Raw Database Snapshot (.db.b64)",
            b64_db,
            file_name="otaku_orbit_snapshot.db.b64",
            mime="text/plain",
        )
        restore_str = st.text_area(
            "Paste Base64 Database Snapshot to Restore", placeholder="Paste base64 string here..."
        )
        if st.button("Restore Database Snapshot") and restore_str.strip():
            ok = restore_sqlite_backup_base64(restore_str.strip(), owner_id)
            if ok:
                st.success("Database restored successfully!")
                st.rerun()
            else:
                st.error("Invalid database snapshot string.")

    with st.expander("🎨 Custom Theme Studio"):
        st.caption("Design and save custom neon color accents:")
        th_c1, th_c2, th_c3 = st.columns(3)
        p_hex = th_c1.color_picker("Primary Neon", "#f4b8ff")
        g_glow = th_c2.color_picker("Glow Accent", "#6f4cff")
        m_hex = th_c3.color_picker("Metric Color", "#f4b8ff")
        if st.button("Apply Custom Theme"):
            st.session_state["custom_theme"] = create_custom_theme_palette(p_hex, f"{g_glow}55", m_hex)
            st.success("Custom theme applied!")

    with st.expander("👥 Multi-Profile Household Switcher"):
        st.caption("Switch between distinct local library profiles:")
        profiles = list_user_profiles(owner_id)
        st.selectbox("Current Profile", profiles, index=0)
        p_name_input = st.text_input("New Profile Name", placeholder="e.g. Manga Only, Family SFW")
        if st.button("Create Profile") and p_name_input:
            if create_user_profile(p_name_input, owner_id):
                st.success(f"Profile '{p_name_input}' created!")
                st.rerun()

    with st.expander("⌨️ Keyboard Navigation Shortcuts"):
        st.markdown("""
        - `/` : Focus title search bar
        - `Esc` : Close detail modal
        - `+` / `-` : Quick increment / decrement progress
        - `w` : Switch between Anime and Manga modes
        - `?` : Open shortcuts cheatsheet
        """)

    with st.expander("Progressive Web App (PWA) & Offline Setup"):
        st.caption("Install Otaku Orbit directly to your phone or desktop home screen:")
        st.markdown("""
        - **Android (Chrome/Edge):** Tap the browser menu `⋮` and select **'Add to Home screen'** or **'Install app'**.
        - **iOS (Safari):** Tap the Share button `⎋` and tap **'Add to Home Screen'** `[+]`.
        - **Desktop (Chrome/Edge):** Click the install icon in the address bar to run as a dedicated desktop app.
        """)

    with st.expander("Privacy Controls & Data Management"):
        st.caption("Permanently delete this account's watchlist and viewing history.")
        if st.button("Delete my data", key="settings-del-data"):
            st.session_state["confirm_delete_owner_data"] = True
        if st.session_state.get("confirm_delete_owner_data"):
            st.warning("This action cannot be undone. All saved titles, history, and notes will be wiped.")
            c1, c2 = st.columns(2)
            if c1.button("Confirm Wiping Data", key="conf-wipe-btn"):
                delete_owner_data(owner_id)
                st.session_state.pop("confirm_delete_owner_data", None)
                st.success("Your data has been wiped.")
                st.rerun()
            if c2.button("Cancel", key="canc-wipe-btn"):
                st.session_state.pop("confirm_delete_owner_data", None)
                st.rerun()


def render_discover(saved_ids: set[int], owner_id: str | None = None) -> None:
    st.markdown(
        '<div class="orbit-hero"><div class="orbit-kicker">Anime discovery, upgraded</div>'
        "<h1>Find your next obsession</h1>"
        '<div class="orbit-muted">Search AniList, save what catches your eye, and let your watchlist become your personal anime map.</div></div>',
        unsafe_allow_html=True,
    )
    s_col1, s_col2 = st.columns([1.5, 1])
    query = s_col1.text_input("Search titles", placeholder="Try Frieren, One Piece, or Cowboy Bebop")
    s_col2.selectbox("🎭 Character Dynamic / Trope", ["All Tropes", *CHARACTER_TROPES.keys()])
    m_type = st.session_state.get("global_media_type", "ANIME")
    if offline_mode_enabled():
        results = []
        st.info("Offline mode is enabled; AniList requests are disabled.")
    elif query:
        search_state = st.session_state.setdefault(
            "discover_search",
            {
                "query": "",
                "results": [],
                "page": 0,
                "has_next": True,
            },
        )
        if search_state["query"] != query:
            search_state.update({"query": query, "results": [], "page": 0, "has_next": True})
        try:
            if not search_state["results"]:
                (first_page, has_next), from_cache = load_with_fallback(
                    f"search:{query}:1:{m_type}", lambda: fetch_anime_page(query, page=1, media_type=m_type)
                )
                search_state.update({"results": first_page, "page": 1, "has_next": has_next})
                if from_cache:
                    st.info(
                        f"Showing cached results from {cache_age_label(f'search:{query}:1:{m_type}')} because AniList is unavailable."
                    )
            results = search_state["results"]
            if search_state["has_next"] and st.button(
                "Load more results", help="Fetch the next page of search results"
            ):
                next_page = search_state["page"] + 1
                (next_results, has_next), _ = load_with_fallback(
                    f"search:{query}:{next_page}:{m_type}",
                    lambda: fetch_anime_page(query, page=next_page, media_type=m_type),
                )
                search_state["results"] = [*search_state["results"], *next_results]
                search_state.update({"page": next_page, "has_next": has_next})
                st.rerun()
        except requests.RequestException as error:
            st.error(str(error))
            results = []
        except RuntimeError as error:
            st.error(str(error))
            results = []
    else:
        st.subheader("Trending now")
        try:
            results, from_cache = load_with_fallback(
                f"trending:{m_type}",
                lambda: call_anilist_response(TRENDING_QUERY, {"type": m_type}).get("Page", {}).get("media", []),
            )
            if from_cache:
                st.info(
                    f"AniList is unavailable; showing trending results cached {cache_age_label(f'trending:{m_type}')}."
                )
        except (requests.RequestException, RuntimeError) as error:
            st.warning(f"AniList is unavailable and no cached trending results exist yet: {error}")
            results = []
    if st.button("Surprise me", help="Show one random title from the current results") and results:
        results = [random.choice(results)]
        st.info("A random pick from the anime universe.")
    results = render_filters(results, "discover")
    d_mode = st.radio("View layout", ["Poster Grid", "Detailed Cards"], horizontal=True, key="discover_layout")
    if d_mode == "Poster Grid":
        render_poster_grid(results, saved_ids, "discover", owner_id)
    else:
        for anime in results:
            with st.container(border=True):
                render_card(anime, saved_ids, "discover", owner_id)


def render_seasonal(saved_ids: set[int], owner_id: str | None = None) -> None:
    curr_season, curr_year = current_season_and_year()
    season_cols = st.columns([1, 1, 2])
    season_names = ["WINTER", "SPRING", "SUMMER", "FALL"]
    season = season_cols[0].selectbox(
        "Season", season_names, index=season_names.index(curr_season), key="seasonal-season"
    )
    years = list(range(curr_year + 1, curr_year - 6, -1))
    year = season_cols[1].selectbox(
        "Year", years, index=years.index(curr_year) if curr_year in years else 1, key="seasonal-year"
    )
    st.title(f"{season.title()} {year}")
    st.write(f"Explore the anime lineup for {season.title()} {year}.")
    m_type = st.session_state.get("global_media_type", "ANIME")
    if offline_mode_enabled():
        results = []
        st.info("Offline mode is enabled; AniList requests are disabled.")
    else:
        try:
            results, from_cache = load_with_fallback(
                f"season:{season}:{year}:{m_type}",
                lambda: fetch_anime(season=season, year=year, media_type=m_type),
            )
            if from_cache:
                st.info(
                    f"AniList is unavailable; showing seasonal results cached {cache_age_label(f'season:{season}:{year}:{m_type}')}."
                )
        except (requests.RequestException, RuntimeError) as error:
            st.error(f"Could not load the seasonal lineup: {error}")
            results = []
    results = render_filters(results, "seasonal")
    s_mode = st.radio("View layout", ["Poster Grid", "Detailed Cards"], horizontal=True, key="seasonal_layout")
    if s_mode == "Poster Grid":
        render_poster_grid(results, saved_ids, "seasonal", owner_id)
    else:
        for anime in results:
            with st.container(border=True):
                render_card(anime, saved_ids, "seasonal", owner_id)
