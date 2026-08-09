import time
from pathlib import Path

import streamlit as st

from tesla_music import analyzer
from tesla_music.apply import apply_changes
from tesla_music.artwork import (
    LOW_CONFIDENCE_THRESHOLD,
    apply_artwork,
    build_artwork_plan,
    flatten_group,
    search_artwork_alternate,
)
from tesla_music.backup import list_backup_sessions
from tesla_music.feat_normalizer import find_featured_artist_changes
from tesla_music.flattener import apply_flatten, build_flatten_plan
from tesla_music.multi_artist import (
    SEPARATOR_AMPERSAND,
    SEPARATOR_SLASH,
    build_feature_choice,
    build_separator_choice,
    find_multi_artist_credits,
)
from tesla_music.planner import build_album_change_plan, build_change_plan, build_plan
from tesla_music.recommendations import build_album_recommendations, build_recommendations
from tesla_music.restore import apply_restore, build_restore_plan
from tesla_music.scanner import scan_library


def _make_progress_callback(progress_bar, label, unit, start_time):
    def on_progress(completed, total):
        elapsed = time.time() - start_time
        rate = elapsed / completed if completed else 0
        eta_seconds = round(rate * (total - completed))
        fraction = completed / total if total else 1.0

        eta_text = (
            f"~{eta_seconds}s remaining" if completed > 0 else "estimating time remaining..."
        )
        progress_bar.progress(
            fraction,
            text=f"{label}... {completed}/{total} {unit} ({eta_text})",
        )

    return on_progress


def build_combined_plan(report):
    recommendations = build_recommendations(report["artist_groups"], report["artist_songs"])
    feat_changes = find_featured_artist_changes(report["artist_songs"])
    album_recommendations = build_album_recommendations(
        report["album_groups"], report["artist_songs"]
    )

    dedup_changes = build_change_plan(recommendations)["changes"] if recommendations else []
    album_changes = (
        build_album_change_plan(album_recommendations)["changes"]
        if album_recommendations
        else []
    )

    plan = build_plan(dedup_changes + feat_changes + album_changes)
    return recommendations, feat_changes, album_recommendations, plan


st.set_page_config(page_title="Tesla Music Tools", page_icon="🚗")
st.title("🚗 Tesla Music Tools")

tab_cleanup, tab_flatten, tab_restore, tab_artwork, tab_multi_artist = st.tabs(
    [
        "Clean Up Library",
        "Flatten for USB",
        "Backups & Restore",
        "Add Artwork",
        "Multi-Artist Credits",
    ]
)

with tab_cleanup:
    st.header("Scan your library")

    library_path = st.text_input("Library path", value="data/input", key="library_path")

    if st.button("Scan Library", type="primary"):
        st.session_state.pop("apply_results", None)
        st.session_state["report"] = analyzer.run(library_path)

    report = st.session_state.get("report")

    if report is not None:
        st.subheader("Summary")

        col1, col2, col3 = st.columns(3)
        col1.metric("Songs scanned", report["songs_scanned"])
        col2.metric("Unique artists", len(report["artists"]))
        col3.metric("File formats", len(report["formats"]))

        with st.expander("File formats"):
            for extension, count in report["formats"].most_common():
                st.write(f"**{extension.upper()}**: {count} songs")

        recommendations, feat_changes, album_recommendations, plan = build_combined_plan(report)

        st.subheader("Proposed Changes")

        if not recommendations and not feat_changes and not album_recommendations:
            st.success("✅ Library is already clean — no changes recommended.")

        else:
            if recommendations:
                st.write("**Duplicate artist merges**")

                for rec in recommendations:
                    label = (
                        f'Keep "{rec["keep"]}" — {rec["confidence"]}% confidence '
                        f'({rec["reason"]})'
                    )
                    with st.expander(label):
                        for change in rec["change"]:
                            st.write(
                                f'"{change["artist"]}" → "{rec["keep"]}" '
                                f'({change["count"]} songs)'
                            )
                            for song in change["songs"]:
                                st.caption(song.path.name)

            if feat_changes:
                st.write("**Featured-artist cleanup**")

                for change in feat_changes:
                    with st.expander(Path(change["file"]).name):
                        st.write(f"Artist: {change['current_artist']} → {change['new_artist']}")
                        st.write(f"Title: {change['current_title']} → {change['new_title']}")

            if album_recommendations:
                st.write("**Duplicate album spellings**")

                for rec in album_recommendations:
                    label = (
                        f'{rec["artist"]} — Keep "{rec["keep"]}" — '
                        f'{rec["confidence"]}% confidence ({rec["reason"]})'
                    )
                    with st.expander(label):
                        for change in rec["change"]:
                            st.write(
                                f'"{change["album"]}" → "{rec["keep"]}" '
                                f'({change["count"]} songs)'
                            )
                            for song in change["songs"]:
                                st.caption(song.path.name)

            st.warning(f"{plan['total_changes']} file(s) will be changed.")

            confirm_apply = st.checkbox(
                "I understand this will modify my music files (a backup is made first)"
            )

            if st.button("Apply Changes", type="primary", disabled=not confirm_apply):
                st.session_state["apply_results"] = apply_changes(plan, dry_run=False)
                st.rerun()

    apply_results = st.session_state.get("apply_results")

    if apply_results:
        st.subheader("Apply Results")

        successful = sum(1 for r in apply_results if r["status"] == "updated")
        failed = sum(1 for r in apply_results if r["status"] == "failed")

        st.info(f"{successful} updated, {failed} failed")

        for result in apply_results:
            icon = "✅" if result["status"] == "updated" else "❌"
            st.write(f"{icon} {Path(result['file']).name} — {result['status']}")

with tab_flatten:
    st.header("Flatten for USB")
    st.write(
        "Copies every song out of its nested Artist/Album folders into one "
        "flat folder, keeping original filenames. Your library is untouched."
    )

    flatten_library_path = st.text_input(
        "Library path", value="data/input", key="flatten_library_path"
    )
    destination = st.text_input(
        "Destination folder", value="data/output/flattened", key="flatten_destination"
    )

    if st.button("Preview Flatten"):
        songs = scan_library(flatten_library_path)
        st.session_state["flatten_plan"] = build_flatten_plan(songs, destination)

    flatten_plan = st.session_state.get("flatten_plan")

    if flatten_plan is not None:
        st.info(
            f"{flatten_plan['total_files']} file(s) will be copied to "
            f"{flatten_plan['destination_folder']}"
        )

        with st.expander("Show files"):
            for change in flatten_plan["changes"]:
                st.caption(f"{Path(change['source']).name} → {Path(change['destination']).name}")

        if st.button("Copy Files", type="primary"):
            results = apply_flatten(flatten_plan, dry_run=False)
            copied = sum(1 for r in results if r["status"] == "copied")
            failed = sum(1 for r in results if r["status"] == "failed")

            message = f"Copied {copied} file(s)."
            if failed:
                message += f" {failed} failed."

            st.success(message)

with tab_restore:
    st.header("Backups & Restore")

    sessions = list_backup_sessions()

    if not sessions:
        st.info(
            "No backup sessions found yet. Backups are created automatically "
            "the first time you apply changes."
        )

    else:
        session = st.selectbox("Backup session", sessions)

        if st.button("Preview Restore"):
            st.session_state["restore_plan"] = build_restore_plan(session)

        restore_plan = st.session_state.get("restore_plan")

        if restore_plan is not None:
            st.info(
                f"{restore_plan['total_files']} file(s) will be restored from "
                f"{restore_plan['backup_session']}"
            )

            with st.expander("Show files"):
                for change in restore_plan["changes"]:
                    st.caption(change["original"])

            confirm_restore = st.checkbox(
                "I understand this will overwrite the current files with the backup"
            )

            if st.button("Restore Files", type="primary", disabled=not confirm_restore):
                results = apply_restore(restore_plan, dry_run=False)
                restored = sum(1 for r in results if r["status"] == "restored")
                failed = sum(1 for r in results if r["status"] == "failed")

                message = f"Restored {restored} file(s)."
                if failed:
                    message += f" {failed} failed."

                st.success(message)

with tab_artwork:
    st.header("Add Missing Album Art")
    st.write(
        "Searches Apple's iTunes catalog for songs missing embedded cover art, "
        "grouped by album (or by song title for singles/EPs with no album "
        "tag). Matches below the confidence threshold automatically get a "
        "second opinion from Deezer so you can compare and pick."
    )

    artwork_library_path = st.text_input(
        "Library path", value="data/input", key="artwork_library_path"
    )

    st.caption(
        "Searching can take a while on a large library — roughly 1 second per "
        "unique album/single, to stay polite to Apple's and Deezer's APIs."
    )

    if st.button("Search for Missing Artwork"):
        with st.spinner("Scanning library..."):
            artwork_report = analyzer.run(artwork_library_path)

        progress_bar = st.progress(0, text="Starting artwork search...")

        st.session_state["artwork_plan"] = build_artwork_plan(
            artwork_report["artist_songs"],
            on_progress=_make_progress_callback(
                progress_bar, "Searching artwork", "albums/singles", time.time()
            ),
        )

        progress_bar.empty()

    artwork_plan = st.session_state.get("artwork_plan")

    if artwork_plan is not None:
        if artwork_plan["total_files"] == 0:
            st.success("✅ No missing artwork found (or no matches anywhere).")

        else:
            groups = sorted(artwork_plan["groups"], key=lambda g: g["primary"]["confidence"])

            st.info(
                f"Found artwork for {artwork_plan['total_files']} song(s) across "
                f"{len(groups)} album(s)/single(s). Flagged ones (below "
                f"{LOW_CONFIDENCE_THRESHOLD}% confidence) are listed first."
            )

            selected_changes = []

            for i, group in enumerate(groups):
                confidence = group["primary"]["confidence"]
                is_flagged = confidence < LOW_CONFIDENCE_THRESHOLD
                song_count = len(group["songs"])
                title_label = group["album"] or f'(Single) "{group["songs"][0].title}"'
                flag = "⚠️ " if is_flagged else ""

                with st.container(border=True):
                    st.markdown(
                        f"{flag}**{group['artist']} — {title_label}** "
                        f"({song_count} song{'s' if song_count != 1 else ''})"
                    )

                    image_cols = st.columns(2)

                    with image_cols[0]:
                        st.image(group["primary"]["artwork_url"], width=150)
                        st.caption(f"Apple — {confidence}% confidence")

                    with image_cols[1]:
                        if group["alternate"] is not None:
                            st.image(group["alternate"]["artwork_url"], width=150)
                            st.caption(f"Deezer — {group['alternate']['confidence']}% confidence")

                        else:
                            st.caption("No alternate fetched.")

                            if st.button("🔍 Search Deezer for a different image", key=f"search_alt_{i}"):
                                with st.spinner("Searching Deezer..."):
                                    alt_match = search_artwork_alternate(
                                        group["artist"],
                                        group["album"] or "Unknown",
                                        group["songs"][0].title,
                                    )

                                if alt_match is not None:
                                    alt_url, alt_confidence = alt_match
                                    group["alternate"] = {
                                        "artwork_url": alt_url,
                                        "confidence": alt_confidence,
                                        "source": "Deezer",
                                    }
                                else:
                                    st.warning("No Deezer match found.")

                                st.rerun()

                    options = ["Use Apple image"]
                    if group["alternate"] is not None:
                        options.append("Use Deezer image")
                    options.append("Skip this one")

                    default_index = options.index("Skip this one") if is_flagged else 0

                    choice = st.radio(
                        "Which image should be used?",
                        options,
                        index=default_index,
                        key=f"artwork_choice_{i}",
                        horizontal=True,
                    )

                    if choice == "Use Apple image":
                        selected_changes.extend(flatten_group(group, use_alternate=False))
                    elif choice == "Use Deezer image":
                        selected_changes.extend(flatten_group(group, use_alternate=True))

                    with st.expander(f"{song_count} song(s) in this group"):
                        for song in group["songs"]:
                            st.caption(song.path.name)

            st.warning(f"{len(selected_changes)} song(s) will have artwork added.")

            confirm_artwork = st.checkbox(
                "I've reviewed the images above and want to add artwork to the "
                "selected songs (a backup is made first)"
            )

            if st.button(
                "Add Artwork",
                type="primary",
                disabled=not confirm_artwork or not selected_changes,
            ):
                selected_plan = {
                    "total_files": len(selected_changes),
                    "changes": selected_changes,
                }

                embed_progress_bar = st.progress(0, text="Starting artwork embedding...")

                artwork_results = apply_artwork(
                    selected_plan,
                    dry_run=False,
                    on_progress=_make_progress_callback(
                        embed_progress_bar, "Embedding artwork", "songs", time.time()
                    ),
                )

                embed_progress_bar.empty()

                added = sum(1 for r in artwork_results if r["status"] == "added")
                failed = sum(1 for r in artwork_results if r["status"] == "failed")

                message = f"Added artwork to {added} file(s)."
                if failed:
                    message += f" {failed} failed."

                st.success(message)

with tab_multi_artist:
    st.header("Resolve multi-artist credits")
    st.write(
        "Finds Artist tags that look like more than one artist sharing a single "
        "credit (joined by \"&\", \",\", \"and\", \"/\", or \"vs\"), excluding "
        "anything the featuring cleanup already handles. Some of these are "
        "genuine duets that should feature one artist in the title; others are "
        "real group names that should just stay as one credit — you decide "
        "each one."
    )

    multi_artist_library_path = st.text_input(
        "Library path", value="data/input", key="multi_artist_library_path"
    )

    if st.button("Find Multi-Artist Credits"):
        multi_artist_report = analyzer.run(multi_artist_library_path)
        st.session_state["multi_artist_candidates"] = find_multi_artist_credits(
            multi_artist_report["artist_songs"]
        )

    multi_artist_candidates = st.session_state.get("multi_artist_candidates")

    if multi_artist_candidates is not None:
        if not multi_artist_candidates:
            st.success("✅ No ambiguous multi-artist credits found.")

        else:
            st.info(
                f"Found {len(multi_artist_candidates)} credit(s). Each one defaults "
                "to \"Keep as-is\" — nothing changes unless you pick something else."
            )

            multi_artist_changes = []

            for i, group in enumerate(multi_artist_candidates):
                song_count = len(group["songs"])
                plural = "s" if song_count != 1 else ""
                label = f"{group['artist']} ({song_count} song{plural})"

                with st.expander(label):
                    st.caption(f"Parsed as: {', '.join(group['candidates'])}")

                    action = st.segmented_control(
                        "Action",
                        ["Keep as-is", "Feature one artist", "Join with &", "Join with /"],
                        default="Keep as-is",
                        required=True,
                        key=f"multi_artist_action_{i}",
                    )

                    if action == "Feature one artist":
                        primary_name = st.selectbox(
                            "Which artist stays in the Artist field?",
                            group["candidates"],
                            key=f"multi_artist_primary_{i}",
                        )
                        primary_index = group["candidates"].index(primary_name)
                        remaining = [
                            name
                            for j, name in enumerate(group["candidates"])
                            if j != primary_index
                        ]
                        st.caption(
                            f'Preview: Artist → "{primary_name}"; Title gets '
                            f'"(feat. {", ".join(remaining)})" appended'
                        )
                        multi_artist_changes.extend(build_feature_choice(group, primary_index))

                    elif action == "Join with &":
                        new_artist = SEPARATOR_AMPERSAND.join(group["candidates"])
                        st.caption(f'Preview: Artist → "{new_artist}"')
                        multi_artist_changes.extend(
                            build_separator_choice(group, SEPARATOR_AMPERSAND)
                        )

                    elif action == "Join with /":
                        new_artist = SEPARATOR_SLASH.join(group["candidates"])
                        st.caption(f'Preview: Artist → "{new_artist}"')
                        multi_artist_changes.extend(
                            build_separator_choice(group, SEPARATOR_SLASH)
                        )

            st.warning(f"{len(multi_artist_changes)} file(s) will be changed.")

            confirm_multi_artist = st.checkbox(
                "I've reviewed my choices above and want to apply them "
                "(a backup is made first)",
                key="confirm_multi_artist",
            )

            if st.button(
                "Apply Multi-Artist Changes",
                type="primary",
                disabled=not confirm_multi_artist or not multi_artist_changes,
            ):
                multi_artist_plan = {
                    "total_changes": len(multi_artist_changes),
                    "changes": multi_artist_changes,
                }

                multi_artist_results = apply_changes(multi_artist_plan, dry_run=False)

                successful = sum(1 for r in multi_artist_results if r["status"] == "updated")
                failed = sum(1 for r in multi_artist_results if r["status"] == "failed")

                message = f"Updated {successful} file(s)."
                if failed:
                    message += f" {failed} failed."

                st.success(message)
