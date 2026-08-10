import subprocess
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
from tesla_music.drm_files import apply_drm_moves, build_drm_plan, find_drm_songs
from tesla_music.duplicates import (
    DUPLICATE_SCAN_EXTENSIONS,
    apply_duplicate_moves,
    build_duplicate_plan,
    find_duplicate_songs,
)
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

DEFAULT_LIBRARY_PATH = "data/input"


# --- Shared helpers ---


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


def _pick_folder_macos():
    """
    Opens a native macOS "Choose Folder" dialog via AppleScript and returns
    the chosen path, or None if unavailable/cancelled. macOS-only.
    """
    script = (
        'tell application "System Events"\n'
        "activate\n"
        'return POSIX path of (choose folder with prompt '
        '"Select your music library folder")\n'
        "end tell"
    )

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    path = result.stdout.strip()

    return path or None


def _print_apply_results(results):
    successful = sum(1 for r in results if r["status"] == "updated")
    failed = sum(1 for r in results if r["status"] == "failed")

    st.subheader("Apply Results")
    st.info(f"{successful} updated, {failed} failed")

    for result in results:
        icon = "✅" if result["status"] == "updated" else "❌"
        st.write(f"{icon} {Path(result['file']).name} — {result['status']}")


def _run_import(library_path):
    report = analyzer.run(library_path)

    recommendations = build_recommendations(report["artist_groups"], report["artist_songs"])
    feat_changes = find_featured_artist_changes(report["artist_songs"])
    album_recommendations = build_album_recommendations(
        report["album_groups"], report["artist_songs"]
    )
    multi_artist_candidates = find_multi_artist_credits(report["artist_songs"])

    duplicate_scan_songs = scan_library(library_path, extensions=DUPLICATE_SCAN_EXTENSIONS)
    _, duplicate_artist_songs = analyzer.analyze_artists(duplicate_scan_songs)
    duplicate_groups = find_duplicate_songs(duplicate_artist_songs)
    duplicate_plan = build_duplicate_plan(duplicate_groups)

    drm_songs = find_drm_songs(library_path)
    drm_plan = build_drm_plan(drm_songs)

    st.session_state["library_path"] = library_path
    st.session_state["report"] = report
    st.session_state["recommendations"] = recommendations
    st.session_state["feat_changes"] = feat_changes
    st.session_state["album_recommendations"] = album_recommendations
    st.session_state["multi_artist_candidates"] = multi_artist_candidates
    st.session_state["duplicate_plan"] = duplicate_plan
    st.session_state["drm_plan"] = drm_plan

    for key in [
        "normalize_apply_results",
        "duplicate_artist_apply_results",
        "multi_artist_apply_results",
        "artwork_plan",
        "flatten_plan",
        "restore_plan",
    ]:
        st.session_state.pop(key, None)


# --- Clean Up Tools: individual tool renderers ---


def _render_normalize_tool():
    st.subheader("Normalize")
    st.write(
        "Moves featured-artist credits out of the Artist tag and into the "
        "Title (e.g. \"Chris Brown Featuring T-Pain\" → Artist: \"Chris "
        "Brown\", Title: \"...(feat. T-Pain)\"), and merges duplicate "
        "spellings of the same album within each artist."
    )

    feat_changes = st.session_state.get("feat_changes", [])
    album_recommendations = st.session_state.get("album_recommendations", [])

    if not feat_changes and not album_recommendations:
        st.success("✅ Nothing to normalize — no featuring credits or duplicate albums found.")
        return

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
                        f'"{change["album"]}" → "{rec["keep"]}" ({change["count"]} songs)'
                    )
                    for song in change["songs"]:
                        st.caption(song.path.name)

    album_changes = (
        build_album_change_plan(album_recommendations)["changes"]
        if album_recommendations
        else []
    )
    plan = build_plan(feat_changes + album_changes)

    st.warning(f"{plan['total_changes']} file(s) will be changed.")

    confirm = st.checkbox(
        "I understand this will modify my music files (a backup is made first)",
        key="confirm_normalize",
    )

    if st.button(
        "Apply Normalize Changes", type="primary", disabled=not confirm, key="apply_normalize"
    ):
        st.session_state["normalize_apply_results"] = apply_changes(plan, dry_run=False)
        st.rerun()

    results = st.session_state.get("normalize_apply_results")

    if results:
        _print_apply_results(results)


def _render_duplicate_artist_tool():
    st.subheader("Duplicate Artist")
    st.write("Merges different spellings of the same artist name.")

    recommendations = st.session_state.get("recommendations", [])

    if not recommendations:
        st.success("✅ No duplicate artist spellings found.")
        return

    for rec in recommendations:
        label = f'Keep "{rec["keep"]}" — {rec["confidence"]}% confidence ({rec["reason"]})'
        with st.expander(label):
            for change in rec["change"]:
                st.write(f'"{change["artist"]}" → "{rec["keep"]}" ({change["count"]} songs)')
                for song in change["songs"]:
                    st.caption(song.path.name)

    plan = build_change_plan(recommendations)

    st.warning(f"{plan['total_changes']} file(s) will be changed.")

    confirm = st.checkbox(
        "I understand this will modify my music files (a backup is made first)",
        key="confirm_duplicate_artist",
    )

    if st.button(
        "Apply Artist Merges",
        type="primary",
        disabled=not confirm,
        key="apply_duplicate_artist",
    ):
        st.session_state["duplicate_artist_apply_results"] = apply_changes(plan, dry_run=False)
        st.rerun()

    results = st.session_state.get("duplicate_artist_apply_results")

    if results:
        _print_apply_results(results)


def _render_drm_tool():
    st.subheader("DRM Files")
    st.write(
        "Finds `.m4p` files — Apple's old FairPlay-protected purchases from "
        "before iTunes dropped DRM in 2009. These can't play in a Tesla, and "
        "this tool will never write to them (stripping DRM would mean "
        "circumventing copy protection, which isn't something this tool "
        "does). If you still have the Apple ID that bought these, most can "
        "be re-downloaded DRM-free from your purchase history."
    )
    st.caption("Files are moved to data/output/drm_review — nothing is deleted.")

    if st.button("Re-scan for DRM Files", key="rescan_drm"):
        with st.spinner("Scanning library..."):
            drm_songs = find_drm_songs(st.session_state["library_path"])
            st.session_state["drm_plan"] = build_drm_plan(drm_songs)

    drm_plan = st.session_state.get("drm_plan", {"total_files": 0, "changes": []})

    if drm_plan["total_files"] == 0:
        st.success("✅ No DRM-protected files found.")
        return

    st.info(f"Found {drm_plan['total_files']} DRM-protected file(s).")

    with st.expander("Show files", expanded=True):
        for change in drm_plan["changes"]:
            st.write(f"**{change['artist']} — {change['title']}**")
            st.caption(change["source"])

    confirm_drm = st.checkbox(
        "I've reviewed the list above and want to move these out of my "
        "library (nothing is deleted)",
        key="confirm_drm",
    )

    if st.button(
        "Move DRM Files to Review Folder",
        type="primary",
        disabled=not confirm_drm,
        key="apply_drm",
    ):
        drm_results = apply_drm_moves(drm_plan, dry_run=False)

        moved = sum(1 for r in drm_results if r["status"] == "moved")
        failed = sum(1 for r in drm_results if r["status"] == "failed")

        message = f"Moved {moved} file(s) to data/output/drm_review."
        if failed:
            message += f" {failed} failed."

        st.success(message)


def _render_duplicate_files_tool():
    st.subheader("Duplicate Files")
    st.write(
        "Finds songs that look like the same recording appearing more than "
        "once — same title and duration within a couple seconds — scoped "
        "per artist so two different songs that happen to share a generic "
        "title (like \"Intro\") are never confused. Also checks `.m4p` "
        "(DRM) files for read-only comparison."
    )
    st.caption(
        "Duplicates are moved to data/output/duplicates_review — nothing is "
        "deleted. The copy judged the best (not DRM, not an auto-renamed "
        "\" 1\"/\"(1)\" file) is kept in place."
    )

    if st.button("Re-scan for Duplicate Files", key="rescan_duplicates"):
        with st.spinner("Scanning library..."):
            duplicate_songs = scan_library(
                st.session_state["library_path"], extensions=DUPLICATE_SCAN_EXTENSIONS
            )
            _, duplicate_artist_songs = analyzer.analyze_artists(duplicate_songs)
            duplicate_groups = find_duplicate_songs(duplicate_artist_songs)
            st.session_state["duplicate_plan"] = build_duplicate_plan(duplicate_groups)

    duplicate_plan = st.session_state.get("duplicate_plan", {"total_files": 0, "changes": []})

    if duplicate_plan["total_files"] == 0:
        st.success("✅ No duplicate songs found.")
        return

    st.info(f"Found {duplicate_plan['total_files']} duplicate file(s) to review.")

    with st.expander("Show duplicates", expanded=True):
        for change in duplicate_plan["changes"]:
            st.write(f"**{change['artist']} — {change['title']}**")
            st.caption(f"Keep: {change['keep']}")
            st.caption(f"Move: {change['source']}")

    confirm_duplicates = st.checkbox(
        "I've reviewed the list above and want to move these duplicates out "
        "of my library (nothing is deleted)",
        key="confirm_duplicates",
    )

    if st.button(
        "Move Duplicates to Review Folder",
        type="primary",
        disabled=not confirm_duplicates,
        key="apply_duplicates",
    ):
        duplicate_results = apply_duplicate_moves(duplicate_plan, dry_run=False)

        moved = sum(1 for r in duplicate_results if r["status"] == "moved")
        failed = sum(1 for r in duplicate_results if r["status"] == "failed")

        message = f"Moved {moved} file(s) to data/output/duplicates_review."
        if failed:
            message += f" {failed} failed."

        st.success(message)


def _render_multi_artist_tool():
    st.subheader("Multi-Artist Credits")
    st.write(
        "Finds Artist tags that look like more than one artist sharing a "
        "single credit (joined by \"&\", \",\", \"and\", \"/\", or \"vs\"), "
        "excluding anything Normalize already handles. Some of these are "
        "genuine duets that should feature one artist in the title; others "
        "are real group names that should just stay as one credit — you "
        "decide each one."
    )

    multi_artist_candidates = st.session_state.get("multi_artist_candidates", [])

    if not multi_artist_candidates:
        st.success("✅ No ambiguous multi-artist credits found.")
        return

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
                    name for j, name in enumerate(group["candidates"]) if j != primary_index
                ]
                st.caption(
                    f'Preview: Artist → "{primary_name}"; Title gets '
                    f'"(feat. {", ".join(remaining)})" appended'
                )
                multi_artist_changes.extend(build_feature_choice(group, primary_index))

            elif action == "Join with &":
                new_artist = SEPARATOR_AMPERSAND.join(group["candidates"])
                st.caption(f'Preview: Artist → "{new_artist}"')
                multi_artist_changes.extend(build_separator_choice(group, SEPARATOR_AMPERSAND))

            elif action == "Join with /":
                new_artist = SEPARATOR_SLASH.join(group["candidates"])
                st.caption(f'Preview: Artist → "{new_artist}"')
                multi_artist_changes.extend(build_separator_choice(group, SEPARATOR_SLASH))

    st.warning(f"{len(multi_artist_changes)} file(s) will be changed.")

    confirm_multi_artist = st.checkbox(
        "I've reviewed my choices above and want to apply them (a backup "
        "is made first)",
        key="confirm_multi_artist",
    )

    if st.button(
        "Apply Multi-Artist Changes",
        type="primary",
        disabled=not confirm_multi_artist or not multi_artist_changes,
        key="apply_multi_artist",
    ):
        multi_artist_plan = {
            "total_changes": len(multi_artist_changes),
            "changes": multi_artist_changes,
        }

        st.session_state["multi_artist_apply_results"] = apply_changes(
            multi_artist_plan, dry_run=False
        )
        st.rerun()

    results = st.session_state.get("multi_artist_apply_results")

    if results:
        _print_apply_results(results)


def _render_artwork_tool():
    st.subheader("Artwork")
    st.write(
        "Searches Apple's iTunes catalog for songs missing embedded cover "
        "art, grouped by album (or by song title for singles/EPs with no "
        "album tag). Matches below the confidence threshold automatically "
        "get a second opinion from Deezer so you can compare and pick."
    )
    st.caption(
        "Not run automatically at import — this needs live network lookups "
        "and can take a while on a large library (roughly 1 second per "
        "unique album/single)."
    )

    if st.button("Search for Missing Artwork", type="primary"):
        progress_bar = st.progress(0, text="Starting artwork search...")

        st.session_state["artwork_plan"] = build_artwork_plan(
            st.session_state["report"]["artist_songs"],
            on_progress=_make_progress_callback(
                progress_bar, "Searching artwork", "albums/singles", time.time()
            ),
        )

        progress_bar.empty()

    artwork_plan = st.session_state.get("artwork_plan")

    if artwork_plan is None:
        return

    if artwork_plan["total_files"] == 0:
        st.success("✅ No missing artwork found (or no matches anywhere).")
        return

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

                    if st.button(
                        "🔍 Search Deezer for a different image", key=f"search_alt_{i}"
                    ):
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


CLEAN_UP_TOOLS = {
    "Normalize": _render_normalize_tool,
    "Duplicate Artist": _render_duplicate_artist_tool,
    "DRM Files": _render_drm_tool,
    "Duplicate Files": _render_duplicate_files_tool,
    "Multi-Artist Credits": _render_multi_artist_tool,
    "Artwork": _render_artwork_tool,
}


# --- Page ---

st.set_page_config(page_title="Tesla Music Tools", page_icon="🚗")
st.title("🚗 Tesla Music Tools")

tab_import, tab_review, tab_cleanup_tools, tab_restore, tab_export = st.tabs(
    ["Import", "Review", "Clean Up Tools", "Restore", "Export"]
)

with tab_import:
    st.header("Import your library")
    st.write(
        "Point this at the folder containing your music. Importing scans "
        "everything and runs every fast check up front, so the Review tab "
        "and Clean Up Tools are ready as soon as it finishes."
    )

    if "library_path_input" not in st.session_state:
        st.session_state["library_path_input"] = DEFAULT_LIBRARY_PATH

    picker_col, button_col = st.columns([4, 1])

    # Filled out of visual order on purpose: the button's session_state
    # update must happen before the text_input below is instantiated,
    # since Streamlit forbids writing to a widget's key after that widget
    # has already been created in the current script run.
    with button_col:
        browse_clicked = st.button("Browse...")

    if browse_clicked:
        chosen_folder = _pick_folder_macos()

        if chosen_folder:
            st.session_state["library_path_input"] = chosen_folder

    with picker_col:
        st.text_input(
            "Library folder",
            key="library_path_input",
            label_visibility="collapsed",
        )

    st.caption(
        "\"Browse...\" opens a native macOS folder picker. If it's "
        "unavailable (e.g. on another OS), type the path directly above."
    )

    if st.button("Import Library", type="primary"):
        library_path = st.session_state["library_path_input"]

        if not Path(library_path).is_dir():
            st.error(f"Folder not found: {library_path}")

        else:
            with st.spinner("Importing and analyzing your library..."):
                _run_import(library_path)

            st.success(
                "Import complete! Head to the Review tab for a summary, or "
                "Clean Up Tools to start fixing things."
            )

    if st.session_state.get("report") is not None:
        st.info(
            f"Currently imported: {st.session_state['library_path']} "
            f"({st.session_state['report']['songs_scanned']} songs)"
        )

with tab_review:
    st.header("Review")

    report = st.session_state.get("report")

    if report is None:
        st.info("Import a library first on the Import tab.")

    else:
        st.subheader("Summary")

        col1, col2, col3 = st.columns(3)
        col1.metric("Songs scanned", report["songs_scanned"])
        col2.metric("Unique artists", len(report["artists"]))
        col3.metric("File formats", len(report["formats"]))

        with st.expander("File formats"):
            for extension, count in report["formats"].most_common():
                st.write(f"**{extension.upper()}**: {count} songs")

        st.subheader("What the tool found")

        overview_rows = [
            ("Duplicate artist spellings", len(st.session_state.get("recommendations", []))),
            ("Featuring credits to clean up", len(st.session_state.get("feat_changes", []))),
            (
                "Duplicate album spellings",
                len(st.session_state.get("album_recommendations", [])),
            ),
            (
                "Multi-artist credits to review",
                len(st.session_state.get("multi_artist_candidates", [])),
            ),
            (
                "Duplicate song files",
                st.session_state.get("duplicate_plan", {"total_files": 0})["total_files"],
            ),
            (
                "DRM-protected files",
                st.session_state.get("drm_plan", {"total_files": 0})["total_files"],
            ),
        ]

        metric_cols = st.columns(3)

        for i, (label, count) in enumerate(overview_rows):
            with metric_cols[i % 3]:
                st.metric(label, count)

        if all(count == 0 for _, count in overview_rows):
            st.success("✅ Nothing to clean up — your library looks great!")
        else:
            st.caption(
                "Head to the Clean Up Tools tab to review and act on any of these."
            )

        st.caption(
            "Album art isn't checked automatically (it needs live network "
            "lookups) — run it from Clean Up Tools → Artwork when you're ready."
        )

with tab_cleanup_tools:
    st.header("Clean Up Tools")

    if st.session_state.get("report") is None:
        st.info("Import a library first on the Import tab.")

    else:
        selected_tool = st.selectbox("Choose a tool", list(CLEAN_UP_TOOLS.keys()))

        st.divider()

        CLEAN_UP_TOOLS[selected_tool]()

with tab_restore:
    st.header("Restore")

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

with tab_export:
    st.header("Export")
    st.write(
        "Copies every song out of its nested Artist/Album folders into one "
        "flat folder, keeping original filenames. Your library is untouched."
    )

    export_library_path = st.text_input(
        "Library path",
        value=st.session_state.get("library_path", DEFAULT_LIBRARY_PATH),
        key="export_library_path",
    )
    destination = st.text_input(
        "Destination folder", value="data/output/flattened", key="flatten_destination"
    )

    if st.button("Preview Export"):
        songs = scan_library(export_library_path)
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
