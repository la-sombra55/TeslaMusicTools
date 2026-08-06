from pathlib import Path

import streamlit as st

from tesla_music import analyzer
from tesla_music.apply import apply_changes
from tesla_music.backup import list_backup_sessions
from tesla_music.feat_normalizer import find_featured_artist_changes
from tesla_music.flattener import apply_flatten, build_flatten_plan
from tesla_music.planner import build_change_plan, build_plan
from tesla_music.recommendations import build_recommendations
from tesla_music.restore import apply_restore, build_restore_plan
from tesla_music.scanner import scan_library


def build_combined_plan(report):
    recommendations = build_recommendations(report["artist_groups"], report["artist_songs"])
    feat_changes = find_featured_artist_changes(report["artist_songs"])
    dedup_changes = build_change_plan(recommendations)["changes"] if recommendations else []
    plan = build_plan(dedup_changes + feat_changes)
    return recommendations, feat_changes, plan


st.set_page_config(page_title="Tesla Music Tools", page_icon="🚗")
st.title("🚗 Tesla Music Tools")

tab_cleanup, tab_flatten, tab_restore = st.tabs(
    ["Clean Up Library", "Flatten for USB", "Backups & Restore"]
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

        recommendations, feat_changes, plan = build_combined_plan(report)

        st.subheader("Proposed Changes")

        if not recommendations and not feat_changes:
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
