import subprocess
import threading
import time
from collections import Counter
from datetime import datetime, timedelta
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
from tesla_music.audio_quality import (
    HIGH_BITRATE_THRESHOLD_KBPS,
    LOW_BITRATE_THRESHOLD_KBPS,
    summarize_bitrate_quality,
)
from tesla_music.backup import count_backup_files, get_backup_library_path, list_backup_sessions
from tesla_music.disk_info import format_bytes, get_volume_status
from tesla_music.drm_files import apply_drm_moves, build_drm_plan, find_drm_songs
from tesla_music.duplicates import (
    DUPLICATE_SCAN_EXTENSIONS,
    apply_duplicate_moves,
    build_duplicate_plan,
    find_duplicate_songs,
)
from tesla_music.csv_export import build_csv_rows, write_csv_export
from tesla_music.feat_normalizer import find_featured_artist_changes
from tesla_music.feat_title_consistency import (
    build_artist_spelling_changes,
    find_artist_spelling_groups,
)
from tesla_music.flattener import (
    apply_flatten,
    build_artist_folder_plan,
    build_flatten_plan,
    build_playlist_export_plan,
)
from tesla_music.import_history import record_import_session
from tesla_music.multi_artist import (
    SEPARATOR_AMPERSAND,
    SEPARATOR_SLASH,
    build_feature_choice,
    build_separator_choice,
    find_multi_artist_credits,
)
from tesla_music.normalizer import find_similar_genres
from tesla_music.planner import (
    build_album_change_plan,
    build_change_plan,
    build_genre_change_plan,
    build_plan,
)
from tesla_music.playlists import (
    delete_playlist,
    find_songs_added_between,
    list_playlists,
    resolve_playlist_songs,
    save_playlist,
    search_library,
)
from tesla_music.recommendations import (
    build_album_recommendations,
    build_genre_recommendations,
    build_recommendations,
)
from tesla_music.restore import apply_restore, build_restore_plan
from tesla_music.scanner import scan_library

DEFAULT_LIBRARY_PATH = "data/input"

# Merges/renames scored below this need a human look before being trusted
# (currently just the fuzzy spelling-variation tier) -- their checkbox
# defaults to unchecked instead of being bundled into "apply everything".
DEDUP_REVIEW_THRESHOLD = 85

PLAYLIST_RESULTS_PER_PAGE = 20


# --- Shared helpers ---


def _format_eta(seconds):
    minutes, seconds = divmod(max(0, round(seconds)), 60)
    return f"{minutes}:{seconds:02d}"


def _format_backup_session_label(session, current_library_path, earliest_session_for_current_library):
    try:
        timestamp = datetime.strptime(session, "%Y%m%d_%H%M%S")
        hour_12 = timestamp.hour % 12 or 12
        period = "AM" if timestamp.hour < 12 else "PM"
        when = f"{timestamp:%B} {timestamp.day}, {timestamp.year} at {hour_12}:{timestamp:%M:%S} {period}"
    except ValueError:
        when = session

    file_count = count_backup_files(session)
    plural = "s" if file_count != 1 else ""
    label = f"{when} — {file_count} file{plural}"

    backup_library_path = get_backup_library_path(session)

    if backup_library_path is None:
        label += " (library unknown — made before this was tracked)"
    elif backup_library_path != current_library_path:
        label += f" (library: {Path(backup_library_path).name})"

    if session == earliest_session_for_current_library:
        label += " ⭐ (original backup for this library)"

    return label


TRASH_CAPTION = (
    "💡 macOS keeps deleted files in a hidden Trash on removable drives "
    "until you empty it — if \"available\" looks lower than expected, try "
    "Finder → Empty Trash on this drive."
)


def _render_volume_storage_info(path, needed_bytes=None):
    """
    Shows used/available space for a removable drive (USB stick, etc.) at
    the given path. Does nothing for internal storage or an unresolvable
    path. If needed_bytes is given, also warns when there isn't enough free
    space for an export of that size.
    """
    status = get_volume_status(path)

    if status is None or not status["is_removable"]:
        return

    label = status["volume_name"] or "this drive"
    used = format_bytes(status["used_bytes"])
    free = format_bytes(status["free_bytes"])
    total = format_bytes(status["total_bytes"])

    st.info(f"🔌 **{label}** — {used} used, {free} available (of {total})")
    st.caption(TRASH_CAPTION)

    if needed_bytes is None:
        return

    needed = format_bytes(needed_bytes)

    if needed_bytes > status["free_bytes"]:
        st.error(
            f"⚠️ This export needs about {needed}, but only {free} is "
            f"available on {label}. Free up space (see note above) or "
            "choose a different destination."
        )
    else:
        st.success(f"✅ This export needs about {needed} — {free} is available on {label}.")


def _make_progress_callback(progress_bar, label, unit, start_time):
    def on_progress(completed, total):
        elapsed = time.time() - start_time
        rate = elapsed / completed if completed else 0
        eta_seconds = rate * (total - completed)
        fraction = completed / total if total else 1.0

        eta_text = (
            f"~{_format_eta(eta_seconds)} remaining" if completed > 0 else "estimating time remaining..."
        )
        progress_bar.progress(
            fraction,
            text=f"{label}... {completed}/{total} {unit} ({eta_text})",
        )

    return on_progress


class _ArtworkSearchState:
    def __init__(self):
        self.start_time = time.time()
        self.completed = 0
        self.total = 0
        self.done = False
        self.result = None
        self.error = None


def _start_artwork_search(artist_songs):
    """
    Runs the (slow, rate-limited) artwork search on a background thread so
    the rest of the app stays fully usable while it works. The thread only
    touches a plain state object -- session_state is written back to from
    proper Streamlit execution contexts (see _finish_artwork_search_if_done).
    """
    state = _ArtworkSearchState()

    def worker():
        try:
            def on_progress(completed, total):
                state.completed = completed
                state.total = total

            state.result = build_artwork_plan(artist_songs, on_progress=on_progress)

        except Exception as error:
            state.error = str(error)

        finally:
            state.done = True

    threading.Thread(target=worker, daemon=True).start()

    st.session_state["artwork_search_state"] = state


def _finish_artwork_search_if_done():
    """
    Checks the background artwork search, if any. If it just finished,
    moves its result into artwork_plan and clears the running state.
    Returns the state object if a search is still running, otherwise None.
    """
    state = st.session_state.get("artwork_search_state")

    if state is None or not state.done:
        return state

    if state.error:
        st.error(f"Artwork search failed: {state.error}")
    else:
        st.session_state["artwork_plan"] = state.result

    st.session_state["artwork_search_state"] = None

    return None


@st.fragment(run_every="2s")
def _render_artwork_progress_fragment():
    running_state = _finish_artwork_search_if_done()

    if running_state is None:
        st.rerun()
        return

    elapsed = time.time() - running_state.start_time
    rate = elapsed / running_state.completed if running_state.completed else 0
    eta_seconds = rate * (running_state.total - running_state.completed)
    fraction = running_state.completed / running_state.total if running_state.total else 0.0
    eta_text = (
        f"~{_format_eta(eta_seconds)} remaining" if running_state.completed > 0
        else "estimating time remaining..."
    )

    st.progress(
        fraction,
        text=(
            f"Searching artwork... {running_state.completed}/{running_state.total} "
            f"albums/singles ({eta_text})"
        ),
    )


def _pick_folder_macos(prompt="Select a folder"):
    """
    Opens a native macOS "Choose Folder" dialog via AppleScript and returns
    the chosen path, or None if unavailable/cancelled. macOS-only.
    """
    script = (
        'tell application "System Events"\n'
        "activate\n"
        f'return POSIX path of (choose folder with prompt "{prompt}")\n'
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


def _folder_picker_input(label, key, default_value, prompt="Select a folder"):
    """
    Renders a text input + "Browse..." button pair for picking a folder,
    wiring the native macOS picker into the given session_state key.
    The button's handling runs before the text_input is instantiated, since
    Streamlit forbids writing to a widget's key after that widget has
    already been created in the current script run.
    """
    if key not in st.session_state:
        st.session_state[key] = default_value

    picker_col, button_col = st.columns([4, 1])

    with button_col:
        browse_clicked = st.button("Browse...", key=f"{key}_browse")

    if browse_clicked:
        chosen_folder = _pick_folder_macos(prompt)

        if chosen_folder:
            st.session_state[key] = chosen_folder

    with picker_col:
        st.text_input(label, key=key, label_visibility="collapsed")

    return st.session_state[key]


def _print_apply_results(results):
    successful = sum(1 for r in results if r["status"] == "updated")
    failed = sum(1 for r in results if r["status"] == "failed")

    st.subheader("Apply Results")
    st.info(f"{successful} updated, {failed} failed")

    for result in results:
        icon = "✅" if result["status"] == "updated" else "❌"
        st.write(f"{icon} {Path(result['file']).name} — {result['status']}")

        if result["status"] == "failed":
            st.caption(result.get("error", "Unknown error"))


def _render_failure_details(results, path_key, verb="processed"):
    """
    Shows detail for any failed results. Successes aren't itemized here
    since the calling tool already reports a summary count.
    """
    failed_results = [r for r in results if r["status"] == "failed"]

    if not failed_results:
        return

    with st.expander(f"{len(failed_results)} file(s) failed to be {verb}", expanded=True):
        for result in failed_results:
            st.write(f"❌ {Path(result[path_key]).name}")
            st.caption(result.get("error", "Unknown error"))


# Per-recommendation widget keys are index-based (e.g. "..._keep_3"), so if
# the underlying recommendation list changes shape after a refresh, a stale
# value at the same index would silently apply to a different recommendation
# than the one the user actually chose it for.
STALE_WIDGET_KEY_PREFIXES = (
    "multi_artist_action_",
    "multi_artist_primary_",
    "duplicate_artist_keep_",
    "duplicate_artist_include_",
    "album_dedup_keep_",
    "album_dedup_include_",
    "genre_keep_",
    "genre_include_",
    "genre_custom_",
    "genre_manual_",
    "title_feat_group_include_",
    "title_feat_preferred_",
    "playlist_export_plan_",
    "playlist_export_all_plan",
)


def _refresh_library_state():
    """
    Re-scans the library and rebuilds every tool's candidate list from the
    current disk state. Needed after any operation that physically moves
    files (Duplicate Files, DRM Files) so other tools' already-computed
    plans don't reference paths that no longer exist there.
    """
    for key in list(st.session_state.keys()):
        if key.startswith(STALE_WIDGET_KEY_PREFIXES):
            del st.session_state[key]

    _run_import(st.session_state["library_path"])


def _run_import(library_path):
    scan_progress_bar = st.progress(0, text="Starting import...")

    report = analyzer.run(
        library_path,
        on_progress=_make_progress_callback(
            scan_progress_bar, "Reading library", "songs", time.time()
        ),
    )

    recommendations = build_recommendations(report["artist_groups"], report["artist_songs"])
    feat_changes = find_featured_artist_changes(report["artist_songs"])
    album_recommendations = build_album_recommendations(
        report["album_groups"], report["artist_songs"]
    )
    multi_artist_candidates = find_multi_artist_credits(report["artist_songs"])
    artist_spelling_groups = find_artist_spelling_groups(report["artist_songs"])

    genre_counts = Counter(
        song.genre for songs in report["artist_songs"].values() for song in songs
    )
    genre_groups = find_similar_genres(genre_counts)
    genre_recommendations = build_genre_recommendations(genre_groups, report["artist_songs"])

    duplicate_scan_songs = scan_library(library_path, extensions=DUPLICATE_SCAN_EXTENSIONS)
    _, duplicate_artist_songs = analyzer.analyze_artists(
        duplicate_scan_songs,
        on_progress=_make_progress_callback(
            scan_progress_bar, "Checking for duplicates", "songs", time.time()
        ),
    )
    duplicate_groups = find_duplicate_songs(duplicate_artist_songs)
    duplicate_plan = build_duplicate_plan(duplicate_groups)

    drm_songs = find_drm_songs(library_path)
    drm_plan = build_drm_plan(drm_songs)

    all_paths = [song.path for songs in report["artist_songs"].values() for song in songs]
    record_import_session(all_paths)

    scan_progress_bar.empty()

    st.session_state["library_path"] = library_path
    st.session_state["report"] = report
    st.session_state["recommendations"] = recommendations
    st.session_state["feat_changes"] = feat_changes
    st.session_state["album_recommendations"] = album_recommendations
    st.session_state["multi_artist_candidates"] = multi_artist_candidates
    st.session_state["artist_spelling_groups"] = artist_spelling_groups
    st.session_state["genre_recommendations"] = genre_recommendations
    st.session_state["genre_counts"] = genre_counts
    st.session_state["duplicate_plan"] = duplicate_plan
    st.session_state["drm_plan"] = drm_plan
    st.session_state["drm_songs"] = drm_songs

    for key in [
        "normalize_apply_results",
        "duplicate_artist_apply_results",
        "multi_artist_apply_results",
        "title_feat_apply_results",
        "genre_apply_results",
        "genre_manual_groups",
        "artwork_plan",
        "flatten_plan",
        "restore_plan",
        "playlist_export_all_plan",
        "playlist_export_all_skipped",
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

    selected_album_recommendations = []

    if album_recommendations:
        st.write("**Duplicate album spellings**")

        for i, rec in enumerate(album_recommendations):
            needs_review = rec["confidence"] < DEDUP_REVIEW_THRESHOLD
            candidates = rec["candidates"]
            candidate_names = [c["album"] for c in candidates]
            variants_preview = " / ".join(candidate_names)
            label = (
                f'{rec["artist"]} — {variants_preview} — '
                f'{rec["confidence"]}% confidence ({rec["reason"]})'
            )
            candidate_labels = {
                c["album"]: f'{c["album"]} ({c["count"]} song{"s" if c["count"] != 1 else ""})'
                for c in candidates
            }

            with st.expander(label, expanded=needs_review):
                if needs_review:
                    st.caption(
                        "⚠️ Lower-confidence match — double-check these are "
                        "really the same album before including it."
                    )

                keep_album = st.selectbox(
                    "Standardize to",
                    candidate_names,
                    format_func=lambda name: candidate_labels[name],
                    key=f"album_dedup_keep_{i}",
                )

                for candidate in candidates:
                    if candidate["album"] == keep_album:
                        continue

                    st.write(
                        f'"{candidate["album"]}" → "{keep_album}" ({candidate["count"]} songs)'
                    )
                    for song in candidate["songs"]:
                        st.caption(song.path.name)

                include = st.checkbox(
                    "Include this merge", value=not needs_review, key=f"album_dedup_include_{i}"
                )

            if include:
                selected_album_recommendations.append(
                    {
                        "artist": rec["artist"],
                        "keep": keep_album,
                        "change": [c for c in candidates if c["album"] != keep_album],
                        "confidence": rec["confidence"],
                        "reason": rec["reason"],
                    }
                )

    album_changes = (
        build_album_change_plan(selected_album_recommendations)["changes"]
        if selected_album_recommendations
        else []
    )

    plan = build_plan(feat_changes + album_changes)

    st.warning(f"{plan['total_changes']} file(s) will be changed.")

    confirm = st.checkbox(
        "I understand this will modify my music files (a backup is made first)",
        key="confirm_normalize",
    )

    if st.button(
        "Apply Normalize Changes",
        type="primary",
        disabled=not confirm or plan["total_changes"] == 0,
        key="apply_normalize",
    ):
        st.session_state["normalize_apply_results"] = apply_changes(
            plan, dry_run=False, library_path=st.session_state["library_path"]
        )
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

    selected_recommendations = []

    for i, rec in enumerate(recommendations):
        needs_review = rec["confidence"] < DEDUP_REVIEW_THRESHOLD
        candidates = rec["candidates"]
        candidate_names = [c["artist"] for c in candidates]
        variants_preview = " / ".join(candidate_names)
        label = f'{variants_preview} — {rec["confidence"]}% confidence ({rec["reason"]})'
        candidate_labels = {
            c["artist"]: f'{c["artist"]} ({c["count"]} song{"s" if c["count"] != 1 else ""})'
            for c in candidates
        }

        with st.expander(label, expanded=needs_review):
            if needs_review:
                st.caption(
                    "⚠️ Lower-confidence match — double-check these are really "
                    "the same artist before including it."
                )

            keep_name = st.selectbox(
                "Standardize to",
                candidate_names,
                format_func=lambda name: candidate_labels[name],
                key=f"duplicate_artist_keep_{i}",
            )

            for candidate in candidates:
                if candidate["artist"] == keep_name:
                    continue

                st.write(f'"{candidate["artist"]}" → "{keep_name}" ({candidate["count"]} songs)')
                for song in candidate["songs"]:
                    st.caption(song.path.name)

            include = st.checkbox(
                "Include this merge", value=not needs_review, key=f"duplicate_artist_include_{i}"
            )

        if include:
            selected_recommendations.append(
                {
                    "keep": keep_name,
                    "change": [c for c in candidates if c["artist"] != keep_name],
                    "confidence": rec["confidence"],
                    "reason": rec["reason"],
                }
            )

    plan = build_change_plan(selected_recommendations)

    st.warning(f"{plan['total_changes']} file(s) will be changed.")

    confirm = st.checkbox(
        "I understand this will modify my music files (a backup is made first)",
        key="confirm_duplicate_artist",
    )

    if st.button(
        "Apply Artist Merges",
        type="primary",
        disabled=not confirm or plan["total_changes"] == 0,
        key="apply_duplicate_artist",
    ):
        st.session_state["duplicate_artist_apply_results"] = apply_changes(
            plan, dry_run=False, library_path=st.session_state["library_path"]
        )
        st.rerun()

    results = st.session_state.get("duplicate_artist_apply_results")

    if results:
        _print_apply_results(results)


GENRE_CUSTOM_OPTION = "✎ Type your own..."
GENRE_PLAYLIST_TARGET = 20


def _render_genre_tool():
    st.subheader("Genre")
    st.write(
        "Cleans up genre spellings and lets you combine similar genres "
        "into fewer, bigger buckets — handy since the Tesla music player "
        "lets you browse by genre, so a small set of genres can double as "
        "playlists."
    )

    recommendations = st.session_state.get("genre_recommendations", [])
    genre_counts = st.session_state.get("genre_counts", {})

    if not genre_counts:
        st.success("✅ No genres found.")
        return

    songs_by_genre = {}
    for songs in st.session_state["report"]["artist_songs"].values():
        for song in songs:
            songs_by_genre.setdefault(song.genre, []).append(song)

    all_genre_names = sorted(genre_counts.keys(), key=str.casefold)
    genre_options = all_genre_names + [GENRE_CUSTOM_OPTION]

    if len(all_genre_names) <= GENRE_PLAYLIST_TARGET:
        st.info(f"You currently have {len(all_genre_names)} distinct genre(s).")
    else:
        st.warning(
            f"You currently have {len(all_genre_names)} distinct genres — "
            f"combine some below to get closer to {GENRE_PLAYLIST_TARGET} or "
            "fewer if you want genres to double as playlists in the car."
        )

    def _format_genre_option(name):
        if name == GENRE_CUSTOM_OPTION:
            return name

        count = genre_counts.get(name, 0)
        return f'{name} ({count} song{"s" if count != 1 else ""})'

    if "genre_manual_groups" not in st.session_state:
        st.session_state["genre_manual_groups"] = []

    manual_groups = st.session_state["genre_manual_groups"]
    manually_grouped_genres = {genre for group in manual_groups for genre in group["sources"]}

    selected_recommendations = []

    if recommendations:
        st.write("**Suggested merges**")
        st.caption("Different spellings of what's probably the same genre.")

        for i, rec in enumerate(recommendations):
            needs_review = rec["confidence"] < DEDUP_REVIEW_THRESHOLD
            candidates = rec["candidates"]
            candidate_names = [c["genre"] for c in candidates]
            variants_preview = " / ".join(candidate_names)
            label = f'{variants_preview} — {rec["confidence"]}% confidence ({rec["reason"]})'

            with st.expander(label, expanded=needs_review):
                if needs_review:
                    st.caption(
                        "⚠️ Lower-confidence match — double-check these are really "
                        "the same genre before including it."
                    )

                default_genre = rec["keep"]
                default_index = (
                    genre_options.index(default_genre) if default_genre in genre_options else 0
                )

                selection = st.selectbox(
                    "Standardize to",
                    genre_options,
                    index=default_index,
                    format_func=_format_genre_option,
                    key=f"genre_keep_{i}",
                )

                if selection == GENRE_CUSTOM_OPTION:
                    keep_name = st.text_input("New genre name", key=f"genre_custom_{i}").strip()
                else:
                    keep_name = selection

                for candidate in candidates:
                    if candidate["genre"] == keep_name:
                        continue

                    display_name = keep_name or "?"
                    st.write(
                        f'"{candidate["genre"]}" → "{display_name}" ({candidate["count"]} songs)'
                    )
                    for song in candidate["songs"]:
                        st.caption(song.path.name)

                include = st.checkbox(
                    "Include this merge",
                    value=not needs_review,
                    key=f"genre_include_{i}",
                    disabled=not keep_name,
                )

            if include and keep_name:
                change_candidates = [
                    c
                    for c in candidates
                    if c["genre"] != keep_name and c["genre"] not in manually_grouped_genres
                ]

                if change_candidates:
                    selected_recommendations.append(
                        {
                            "keep": keep_name,
                            "change": change_candidates,
                            "confidence": rec["confidence"],
                            "reason": rec["reason"],
                        }
                    )

    st.divider()
    st.write("**Combine genres manually**")
    st.caption(
        "Pick any set of genres that should really be one genre — useful "
        "when they're not just spelling differences, like \"Trap\", "
        "\"Gangsta Rap\", and \"Hip Hop\" all becoming \"Hip-Hop\"."
    )

    selection_options = [name for name in all_genre_names if name not in manually_grouped_genres]

    selected_genres = st.multiselect(
        "Genres to combine",
        selection_options,
        format_func=_format_genre_option,
        key="genre_manual_selection",
    )

    manual_target_index = 0
    if selected_genres:
        default_target = max(selected_genres, key=lambda name: genre_counts.get(name, 0))
        if default_target in genre_options:
            manual_target_index = genre_options.index(default_target)

    manual_selection = st.selectbox(
        "Combine into",
        genre_options,
        index=manual_target_index,
        format_func=_format_genre_option,
        key="genre_manual_target",
    )

    if manual_selection == GENRE_CUSTOM_OPTION:
        manual_target = st.text_input("New genre name", key="genre_manual_target_custom").strip()
    else:
        manual_target = manual_selection

    if st.button(
        "Add Group",
        key="genre_manual_add",
        disabled=len(selected_genres) < 2 or not manual_target,
    ):
        st.session_state["genre_manual_groups"].append(
            {"target": manual_target, "sources": selected_genres}
        )
        st.session_state.pop("genre_manual_selection", None)
        st.session_state.pop("genre_manual_target_custom", None)
        st.rerun()

    if manual_groups:
        st.write("Staged groups:")

        for i, group in enumerate(manual_groups):
            total_songs = sum(genre_counts.get(name, 0) for name in group["sources"])
            group_col, remove_col = st.columns([5, 1])

            with group_col:
                sources_preview = " / ".join(group["sources"])
                st.caption(f'{sources_preview} → "{group["target"]}" ({total_songs} songs)')

            with remove_col:
                if st.button("Remove", key=f"genre_manual_remove_{i}"):
                    st.session_state["genre_manual_groups"].pop(i)
                    st.rerun()

        for group in manual_groups:
            change_candidates = [
                {
                    "genre": name,
                    "count": genre_counts.get(name, 0),
                    "songs": songs_by_genre.get(name, []),
                }
                for name in group["sources"]
                if name != group["target"]
            ]

            if change_candidates:
                selected_recommendations.append(
                    {
                        "keep": group["target"],
                        "change": change_candidates,
                        "confidence": 100,
                        "reason": "Manually combined",
                    }
                )

    st.divider()

    plan = build_genre_change_plan(selected_recommendations)

    st.warning(f"{plan['total_changes']} file(s) will be changed.")

    confirm = st.checkbox(
        "I understand this will modify my music files (a backup is made first)",
        key="confirm_genre",
    )

    if st.button(
        "Apply Genre Merges",
        type="primary",
        disabled=not confirm or plan["total_changes"] == 0,
        key="apply_genre",
    ):
        genre_progress_bar = st.progress(0, text="Starting genre merge...")

        genre_results = apply_changes(
            plan,
            dry_run=False,
            library_path=st.session_state["library_path"],
            on_progress=_make_progress_callback(
                genre_progress_bar, "Applying genre changes", "files", time.time()
            ),
        )

        genre_progress_bar.empty()

        with st.spinner("Refreshing library data..."):
            _refresh_library_state()

        st.session_state["genre_apply_results"] = genre_results
        st.rerun()

    results = st.session_state.get("genre_apply_results")

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

    destination = _folder_picker_input(
        "Destination folder",
        key="drm_destination",
        default_value="data/output/drm_review",
        prompt="Select a destination folder",
    )
    st.caption(
        "Nothing is deleted — files are moved here. Change the destination "
        "then click \"Re-scan\" to use it."
    )

    if st.button("Re-scan for DRM Files", key="rescan_drm"):
        with st.spinner("Scanning library..."):
            drm_songs = find_drm_songs(st.session_state["library_path"])
            st.session_state["drm_songs"] = drm_songs
            st.session_state["drm_plan"] = build_drm_plan(drm_songs, destination_folder=destination)

    drm_plan = st.session_state.get(
        "drm_plan", {"total_files": 0, "destination_folder": destination, "changes": []}
    )

    if drm_plan["total_files"] == 0:
        st.success("✅ No DRM-protected files found.")
        return

    st.info(
        f"Found {drm_plan['total_files']} DRM-protected file(s). Will move to "
        f"{drm_plan['destination_folder']}."
    )

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

        message = f"Moved {moved} file(s) to {drm_plan['destination_folder']}."
        if failed:
            message += f" {failed} failed."

        st.success(message)
        _render_failure_details(drm_results, "source", verb="moved")

        with st.spinner("Refreshing library data..."):
            _refresh_library_state()

        st.caption(
            "Every other tool's data has been refreshed to match — moved "
            "files won't show up as stale entries elsewhere."
        )


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
        "The copy judged the best (not DRM, not an auto-renamed \" 1\"/\"(1)\" "
        "file) is kept in place — nothing is deleted, duplicates are moved."
    )

    destination = _folder_picker_input(
        "Destination folder",
        key="duplicate_files_destination",
        default_value="data/output/duplicates_review",
        prompt="Select a destination folder",
    )
    st.caption("Change the destination then click \"Re-scan\" to use it.")

    if st.button("Re-scan for Duplicate Files", key="rescan_duplicates"):
        with st.spinner("Scanning library..."):
            duplicate_songs = scan_library(
                st.session_state["library_path"], extensions=DUPLICATE_SCAN_EXTENSIONS
            )
            _, duplicate_artist_songs = analyzer.analyze_artists(duplicate_songs)
            duplicate_groups = find_duplicate_songs(duplicate_artist_songs)
            st.session_state["duplicate_plan"] = build_duplicate_plan(
                duplicate_groups, destination_folder=destination
            )

    duplicate_plan = st.session_state.get(
        "duplicate_plan", {"total_files": 0, "destination_folder": destination, "changes": []}
    )

    if duplicate_plan["total_files"] == 0:
        st.success("✅ No duplicate songs found.")
        return

    st.info(
        f"Found {duplicate_plan['total_files']} duplicate file(s) to review. Will move to "
        f"{duplicate_plan['destination_folder']}."
    )

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

        message = f"Moved {moved} file(s) to {duplicate_plan['destination_folder']}."
        if failed:
            message += f" {failed} failed."

        st.success(message)
        _render_failure_details(duplicate_results, "source", verb="moved")

        with st.spinner("Refreshing library data..."):
            _refresh_library_state()

        st.caption(
            "Every other tool's data has been refreshed to match — moved "
            "files won't show up as stale entries elsewhere."
        )


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
                feature_changes = build_feature_choice(group, primary_index)

                st.caption(f'Preview: Artist → "{primary_name}"')
                for change in feature_changes:
                    st.caption(f'"{change["current_title"]}" → "{change["new_title"]}"')

                multi_artist_changes.extend(feature_changes)

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
            multi_artist_plan, dry_run=False, library_path=st.session_state["library_path"]
        )
        st.rerun()

    results = st.session_state.get("multi_artist_apply_results")

    if results:
        _print_apply_results(results)


def _render_title_feat_consistency_tool():
    st.subheader("Featured-Credit Spelling")
    st.write(
        "Finds every spelling of an artist used anywhere in your library — "
        "as a primary Artist tag, or as a featured credit inside another "
        "song's Title (e.g. \"(feat. Missy Elliot)\") — and lets you pick "
        "one preferred spelling to apply everywhere."
    )

    artist_songs = st.session_state["report"]["artist_songs"]
    groups = st.session_state.get("artist_spelling_groups", [])

    if not groups:
        st.success("✅ No spelling inconsistencies found.")
        return

    all_changes = []

    for i, group in enumerate(groups):
        needs_review = group["confidence"] < DEDUP_REVIEW_THRESHOLD
        spelling_names = [s["spelling"] for s in group["spellings"]]
        variants_preview = " / ".join(spelling_names)
        label = (
            f'{variants_preview} — {group["total_count"]} song(s) — '
            f'{group["confidence"]}% confidence ({group["reason"]})'
        )

        with st.expander(label, expanded=needs_review):
            if needs_review:
                st.caption(
                    "⚠️ Lower-confidence match — double-check these are really "
                    "the same artist before including it."
                )

            before_col, choose_col, after_col = st.columns([2, 2, 2])

            with before_col:
                st.write("**Before**")
                for spelling in group["spellings"]:
                    count = len(spelling["mentions"])
                    plural = "s" if count != 1 else ""
                    st.caption(f'{spelling["spelling"]} ({count} song{plural})')

            with choose_col:
                preferred_spelling = st.selectbox(
                    "Choose preferred artist spelling",
                    spelling_names,
                    key=f"title_feat_preferred_{i}",
                )

            with after_col:
                total_plural = "s" if group["total_count"] != 1 else ""
                st.write("**After**")
                st.caption(f'{preferred_spelling} ({group["total_count"]} song{total_plural})')

            with st.expander("Songs updated"):
                for spelling in group["spellings"]:
                    if spelling["spelling"] == preferred_spelling:
                        continue

                    for mention in spelling["mentions"]:
                        source_label = (
                            "Artist tag" if mention["source"] == "artist_tag" else "Title credit"
                        )
                        st.caption(
                            f'{Path(mention["file"]).name} — {source_label} — was '
                            f'"{spelling["spelling"]}"'
                        )

            include = st.checkbox(
                f'Normalize to "{preferred_spelling}"',
                value=not needs_review,
                key=f"title_feat_group_include_{i}",
            )

        if include:
            all_changes.extend(
                build_artist_spelling_changes(preferred_spelling, group, artist_songs)
            )

    plan = build_plan(all_changes)

    st.warning(f"{plan['total_changes']} file(s) will be changed.")

    confirm = st.checkbox(
        "I understand this will modify my music files (a backup is made first)",
        key="confirm_title_feat_consistency",
    )

    if st.button(
        "Apply Spelling Fixes",
        type="primary",
        disabled=not confirm or plan["total_changes"] == 0,
        key="apply_title_feat_consistency",
    ):
        st.session_state["title_feat_apply_results"] = apply_changes(
            plan, dry_run=False, library_path=st.session_state["library_path"]
        )
        st.rerun()

    results = st.session_state.get("title_feat_apply_results")

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
        "Runs in the background — feel free to switch to another tool "
        "while this finishes. Roughly 1 second per unique album/single, "
        "so it can take a while on a large library."
    )

    if st.session_state.get("artwork_search_state") is not None:
        _render_artwork_progress_fragment()

    elif st.button("Search for Missing Artwork", type="primary", key="start_artwork_tool"):
        _start_artwork_search(st.session_state["report"]["artist_songs"])
        st.rerun()

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
            library_path=st.session_state["library_path"],
        )

        embed_progress_bar.empty()

        added = sum(1 for r in artwork_results if r["status"] == "added")
        failed = sum(1 for r in artwork_results if r["status"] == "failed")

        message = f"Added artwork to {added} file(s)."
        if failed:
            message += f" {failed} failed."

        st.success(message)
        _render_failure_details(artwork_results, "file", verb="embedded")


def _render_flatten_export():
    st.write(
        "Copies every song out of its nested Artist/Album folders into one "
        "flat folder, keeping original filenames. Your library is untouched."
    )

    destination = _folder_picker_input(
        "Destination folder",
        key="flatten_destination",
        default_value="data/output/flattened",
        prompt="Select a destination folder",
    )

    if st.button("Preview Export", key="flatten_preview"):
        artist_songs = st.session_state["report"]["artist_songs"]
        file_paths = [song.path for songs in artist_songs.values() for song in songs]
        st.session_state["flatten_plan"] = build_flatten_plan(file_paths, destination)

    flatten_plan = st.session_state.get("flatten_plan")

    if flatten_plan is None:
        _render_volume_storage_info(destination)
        return

    st.info(
        f"{flatten_plan['total_files']} file(s) will be copied to "
        f"{flatten_plan['destination_folder']}"
    )

    needed_bytes = sum(Path(change["source"]).stat().st_size for change in flatten_plan["changes"])
    _render_volume_storage_info(flatten_plan["destination_folder"], needed_bytes=needed_bytes)

    with st.expander("Show files"):
        for change in flatten_plan["changes"]:
            st.caption(f"{Path(change['source']).name} → {Path(change['destination']).name}")

    if st.button("Copy Files", type="primary", key="flatten_copy"):
        copy_progress_bar = st.progress(0, text="Starting export...")

        results = apply_flatten(
            flatten_plan,
            dry_run=False,
            on_progress=_make_progress_callback(copy_progress_bar, "Copying files", "files", time.time()),
        )

        copy_progress_bar.empty()

        copied = sum(1 for r in results if r["status"] == "copied")
        failed = sum(1 for r in results if r["status"] == "failed")

        message = f"Copied {copied} file(s)."
        if failed:
            message += f" {failed} failed."

        st.success(message)
        _render_failure_details(results, "source", verb="copied")


def _render_artist_folder_export():
    st.write(
        "Copies every song into a folder per artist (Album subfolders are "
        "flattened away), so anyone browsing the export — like via a "
        "shared Google Drive folder — can jump straight to an artist "
        "instead of scrolling through everything at once."
    )

    destination = _folder_picker_input(
        "Destination folder",
        key="artist_folder_destination",
        default_value="data/output/by_artist",
        prompt="Select a destination folder",
    )

    if st.button("Preview Export", key="artist_folder_preview"):
        artist_songs = st.session_state["report"]["artist_songs"]
        st.session_state["artist_folder_plan"] = build_artist_folder_plan(artist_songs, destination)

    artist_folder_plan = st.session_state.get("artist_folder_plan")

    if artist_folder_plan is None:
        _render_volume_storage_info(destination)
        return

    st.info(
        f"{artist_folder_plan['total_files']} file(s) will be copied to "
        f"{artist_folder_plan['destination_folder']}"
    )

    needed_bytes = sum(
        Path(change["source"]).stat().st_size for change in artist_folder_plan["changes"]
    )
    _render_volume_storage_info(artist_folder_plan["destination_folder"], needed_bytes=needed_bytes)

    with st.expander("Show files"):
        for change in artist_folder_plan["changes"]:
            source_name = Path(change["source"]).name
            destination_path = Path(change["destination"])
            st.caption(f"{source_name} → {destination_path.parent.name}/{destination_path.name}")

    if st.button("Copy Files", type="primary", key="artist_folder_copy"):
        copy_progress_bar = st.progress(0, text="Starting export...")

        results = apply_flatten(
            artist_folder_plan,
            dry_run=False,
            on_progress=_make_progress_callback(copy_progress_bar, "Copying files", "files", time.time()),
        )

        copy_progress_bar.empty()

        copied = sum(1 for r in results if r["status"] == "copied")
        failed = sum(1 for r in results if r["status"] == "failed")

        message = f"Copied {copied} file(s)."
        if failed:
            message += f" {failed} failed."

        st.success(message)
        _render_failure_details(results, "source", verb="copied")


def _render_csv_export():
    st.write(
        "Exports title, artist, album, and format for every song to a "
        "single CSV file, sorted alphabetically by album — handy for "
        "browsing your library in a spreadsheet. DRM-protected files are "
        "included too (they'll show \"m4p\" as the format), since even "
        "though they can't play in a Tesla, this list is handy for finding "
        "what to re-download DRM-free."
    )

    destination_folder = _folder_picker_input(
        "Destination folder",
        key="csv_destination_folder",
        default_value="data/output",
        prompt="Select a destination folder",
    )
    filename = st.text_input("File name", value="library.csv", key="csv_filename")

    _render_volume_storage_info(destination_folder)

    if st.button("Export CSV", type="primary", key="csv_export_button"):
        csv_progress_bar = st.progress(0, text="Starting export...")

        artist_songs = st.session_state["report"]["artist_songs"]
        combined_artist_songs = {artist: list(songs) for artist, songs in artist_songs.items()}

        for song in st.session_state.get("drm_songs", []):
            combined_artist_songs.setdefault(song.artist, []).append(song)

        rows = build_csv_rows(
            combined_artist_songs,
            on_progress=_make_progress_callback(csv_progress_bar, "Gathering song info", "songs", time.time()),
        )
        destination_path = Path(destination_folder) / filename
        write_csv_export(rows, destination_path)

        csv_progress_bar.empty()

        st.session_state["csv_export_path"] = str(destination_path)
        st.session_state["csv_export_row_count"] = len(rows)

    csv_export_path = st.session_state.get("csv_export_path")

    if csv_export_path is not None:
        st.success(
            f"Wrote {st.session_state['csv_export_row_count']} row(s) to {csv_export_path}"
        )


def _render_smart_playlist_builder():
    st.write(
        "Type an artist (or any text) and every song where it appears in "
        "the Artist field *or* the Title field gets included — catching "
        "both their own tracks and any songs where they're featured."
    )

    query = st.text_input("Search for", key="smart_playlist_query")
    artist_songs = st.session_state["report"]["artist_songs"]
    matches = search_library(artist_songs, query) if query else []

    if query:
        plural = "s" if len(matches) != 1 else ""
        st.info(f'{len(matches)} song{plural} match "{query}"')

        with st.expander("Show matches", expanded=bool(matches)):
            for song in matches:
                st.caption(f"{song.artist} — {song.title}")

    name = st.text_input("Playlist name", key="smart_playlist_name")

    if st.button(
        "Save Playlist",
        type="primary",
        disabled=not name.strip() or not matches,
        key="smart_playlist_save",
    ):
        save_playlist(name.strip(), matches)
        st.success(
            f'Saved "{name.strip()}" with {len(matches)} song(s). Find it under '
            '"Your Playlists" above to export it.'
        )


def _render_manual_playlist_builder():
    st.write(
        "Search your library and add songs one at a time to build a "
        "playlist by hand — good for mixing multiple artists together, "
        "like a road trip mix."
    )

    if "playlist_builder_songs" not in st.session_state:
        st.session_state["playlist_builder_songs"] = []

    artist_songs = st.session_state["report"]["artist_songs"]
    added_paths = st.session_state["playlist_builder_songs"]
    song_by_path = {str(song.path): song for songs in artist_songs.values() for song in songs}

    query = st.text_input(
        "Search for songs to add (matches song, artist, or album)",
        key="manual_playlist_query",
    )

    if query:
        matches = search_library(artist_songs, query, fields=("artist", "title", "album"))

        if query != st.session_state.get("manual_playlist_last_query"):
            st.session_state["manual_playlist_last_query"] = query
            st.session_state["manual_playlist_page"] = 0

        if not matches:
            st.caption("No matches.")
        else:
            total_pages = -(-len(matches) // PLAYLIST_RESULTS_PER_PAGE)
            page = min(st.session_state.get("manual_playlist_page", 0), total_pages - 1)
            start = page * PLAYLIST_RESULTS_PER_PAGE
            page_matches = matches[start : start + PLAYLIST_RESULTS_PER_PAGE]

            st.caption(f"{len(matches)} match(es) — page {page + 1} of {total_pages}")

            for song in page_matches:
                path = str(song.path)
                label = f"{song.artist} — {song.title}"

                if song.album and song.album != "Unknown":
                    label += f" · {song.album}"

                result_col, button_col = st.columns([5, 1])

                with result_col:
                    st.caption(label)

                with button_col:
                    already_added = path in added_paths

                    if st.button(
                        "Added" if already_added else "Add",
                        disabled=already_added,
                        key=f"manual_playlist_add_{path}",
                    ):
                        added_paths.append(path)
                        st.rerun()

            if total_pages > 1:
                prev_col, page_col, next_col = st.columns([1, 2, 1])

                with prev_col:
                    if st.button(
                        "← Previous", disabled=page == 0, key="manual_playlist_prev_page"
                    ):
                        st.session_state["manual_playlist_page"] = page - 1
                        st.rerun()

                with page_col:
                    st.write(f"Page {page + 1} of {total_pages}")

                with next_col:
                    if st.button(
                        "Next →",
                        disabled=page >= total_pages - 1,
                        key="manual_playlist_next_page",
                    ):
                        st.session_state["manual_playlist_page"] = page + 1
                        st.rerun()

    st.divider()

    plural = "s" if len(added_paths) != 1 else ""
    st.write(f"**{len(added_paths)} song{plural} in this playlist**")

    for path in list(added_paths):
        song = song_by_path.get(path)
        label = f"{song.artist} — {song.title}" if song is not None else path

        item_col, remove_col = st.columns([5, 1])

        with item_col:
            st.caption(label)

        with remove_col:
            if st.button("Remove", key=f"manual_playlist_remove_{path}"):
                added_paths.remove(path)
                st.rerun()

    name = st.text_input("Playlist name", key="manual_playlist_name")

    save_col, clear_col = st.columns([1, 1])

    with save_col:
        if st.button(
            "Save Playlist",
            type="primary",
            disabled=not name.strip() or not added_paths,
            key="manual_playlist_save",
        ):
            songs_to_save = [song_by_path[path] for path in added_paths if path in song_by_path]
            save_playlist(name.strip(), songs_to_save)
            st.session_state["playlist_builder_songs"] = []

            st.success(
                f'Saved "{name.strip()}" with {len(songs_to_save)} song(s). Find it under '
                '"Your Playlists" above to export it.'
            )
            st.rerun()

    with clear_col:
        if st.button("Start Over", key="manual_playlist_clear"):
            st.session_state["playlist_builder_songs"] = []
            st.rerun()


def _render_date_playlist_builder():
    st.write(
        "Build a playlist from everything added to your library within a "
        "date range — handy right after a big import session, like all "
        "the CDs from a friend in one sitting."
    )

    preset = st.segmented_control(
        "Range",
        ["Today", "Last 24 hours", "Last 7 days", "Custom range"],
        default="Today",
        required=True,
        key="date_playlist_preset",
    )

    now = datetime.now()

    if preset == "Today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif preset == "Last 24 hours":
        start = now - timedelta(hours=24)
        end = now
    elif preset == "Last 7 days":
        start = now - timedelta(days=7)
        end = now
    else:
        range_col1, range_col2 = st.columns(2)

        with range_col1:
            start_date = st.date_input("From", value=now.date(), key="date_playlist_start")

        with range_col2:
            end_date = st.date_input("To", value=now.date(), key="date_playlist_end")

        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())

    artist_songs = st.session_state["report"]["artist_songs"]
    matches = find_songs_added_between(artist_songs, start, end)

    plural = "s" if len(matches) != 1 else ""
    st.info(f"{len(matches)} song{plural} added in this range")

    with st.expander("Show matches", expanded=bool(matches)):
        for song in matches:
            st.caption(f"{song.artist} — {song.title}")

    name = st.text_input("Playlist name", key="date_playlist_name")

    if st.button(
        "Save Playlist",
        type="primary",
        disabled=not name.strip() or not matches,
        key="date_playlist_save",
    ):
        save_playlist(name.strip(), matches)
        st.success(
            f'Saved "{name.strip()}" with {len(matches)} song(s). Find it under '
            '"Your Playlists" above to export it.'
        )


def _render_export_all_playlists(saved_playlists, artist_songs, destination, organize_by):
    st.write("**Export all playlists at once**, using the destination and organization above.")

    if st.button("Preview All Playlists", key="playlist_export_all_preview"):
        combined_changes = []
        skipped_names = []

        for playlist in saved_playlists:
            found_songs, _ = resolve_playlist_songs(playlist, artist_songs)

            if not found_songs:
                skipped_names.append(playlist["name"])
                continue

            plan = build_playlist_export_plan(
                found_songs, playlist["name"], destination, organize_by=organize_by
            )
            combined_changes.extend(plan["changes"])

        st.session_state["playlist_export_all_plan"] = {
            "total_files": len(combined_changes),
            "changes": combined_changes,
        }
        st.session_state["playlist_export_all_skipped"] = skipped_names

    all_plan = st.session_state.get("playlist_export_all_plan")

    if all_plan is None:
        return

    skipped_names = st.session_state.get("playlist_export_all_skipped", [])

    if skipped_names:
        st.caption(f"Skipped (no songs found): {', '.join(skipped_names)}")

    if all_plan["total_files"] == 0:
        st.warning("Nothing to export — every playlist is empty right now.")
        return

    st.info(f"{all_plan['total_files']} file(s) across all playlists will be copied to {destination}")

    needed_bytes = sum(Path(change["source"]).stat().st_size for change in all_plan["changes"])
    _render_volume_storage_info(destination, needed_bytes=needed_bytes)

    if st.button("Copy All Playlists", type="primary", key="playlist_export_all_copy"):
        copy_progress_bar = st.progress(0, text="Starting export...")

        results = apply_flatten(
            all_plan,
            dry_run=False,
            on_progress=_make_progress_callback(
                copy_progress_bar, "Copying files", "files", time.time()
            ),
        )

        copy_progress_bar.empty()

        copied = sum(1 for r in results if r["status"] == "copied")
        failed = sum(1 for r in results if r["status"] == "failed")

        message = f"Copied {copied} file(s) across all playlists."
        if failed:
            message += f" {failed} failed."

        st.success(message)
        _render_failure_details(results, "source", verb="copied")


def _render_saved_playlists():
    saved_playlists = list_playlists()

    if not saved_playlists:
        st.info(
            "No playlists saved yet — build one with \"New Smart Playlist\" or "
            "\"New Manual Playlist\" above."
        )
        return

    artist_songs = st.session_state["report"]["artist_songs"]

    destination = _folder_picker_input(
        "Destination folder for exports",
        key="playlist_shared_destination",
        default_value="data/output/playlists",
        prompt="Select a destination folder",
    )
    st.caption(
        "Shared by every playlist below — each one exports into its own "
        "subfolder here, so it's safe to reuse the same destination for all "
        "of them."
    )

    organize_by_choice = st.segmented_control(
        "Organize exported files by",
        ["Artist", "Album", "Original filenames"],
        default="Artist",
        required=True,
        key="playlist_organize_by",
    )
    st.caption(
        "Your car's USB browser lists files alphabetically by filename, not "
        "by tag — this prefixes each exported song so they group together "
        "when you browse the playlist folder in the car."
    )
    organize_by = {"Artist": "artist", "Album": "album", "Original filenames": None}[
        organize_by_choice
    ]

    st.divider()
    _render_export_all_playlists(saved_playlists, artist_songs, destination, organize_by)
    st.divider()

    for i, playlist in enumerate(saved_playlists):
        found_songs, missing_paths = resolve_playlist_songs(playlist, artist_songs)
        plural = "s" if len(found_songs) != 1 else ""
        label = f'{playlist["name"]} — {len(found_songs)} song{plural}'

        with st.expander(label):
            if missing_paths:
                missing_plural = "s" if len(missing_paths) != 1 else ""
                st.caption(
                    f"⚠️ {len(missing_paths)} song{missing_plural} in this playlist weren't "
                    "found in your current library (moved, renamed, or deleted since it "
                    "was saved)."
                )

            if not found_songs:
                st.write("Nothing left in this playlist to export.")
                _render_playlist_delete_button(i, playlist["name"])
                continue

            with st.expander("Show songs"):
                for song in found_songs:
                    st.caption(f"{song.artist} — {song.title}")

            plan_key = f"playlist_export_plan_{i}"

            if st.button("Preview Export", key=f"playlist_preview_{i}"):
                st.session_state[plan_key] = build_playlist_export_plan(
                    found_songs, playlist["name"], destination, organize_by=organize_by
                )

            export_plan = st.session_state.get(plan_key)

            if export_plan is None:
                _render_volume_storage_info(destination)
            else:
                st.info(
                    f"{export_plan['total_files']} file(s) will be copied to "
                    f"{export_plan['destination_folder']}"
                )

                needed_bytes = sum(
                    Path(change["source"]).stat().st_size for change in export_plan["changes"]
                )
                _render_volume_storage_info(
                    export_plan["destination_folder"], needed_bytes=needed_bytes
                )

                if st.button("Copy Files", type="primary", key=f"playlist_copy_{i}"):
                    copy_progress_bar = st.progress(0, text="Starting export...")

                    results = apply_flatten(
                        export_plan,
                        dry_run=False,
                        on_progress=_make_progress_callback(
                            copy_progress_bar, "Copying files", "files", time.time()
                        ),
                    )

                    copy_progress_bar.empty()

                    copied = sum(1 for r in results if r["status"] == "copied")
                    failed = sum(1 for r in results if r["status"] == "failed")

                    message = f"Copied {copied} file(s)."
                    if failed:
                        message += f" {failed} failed."

                    st.success(message)
                    _render_failure_details(results, "source", verb="copied")

            _render_playlist_delete_button(i, playlist["name"])


def _render_playlist_delete_button(i, playlist_name):
    confirm_delete = st.checkbox(
        "Yes, delete this playlist (the songs themselves aren't touched)",
        key=f"playlist_delete_confirm_{i}",
    )

    if st.button(
        "Delete Playlist", disabled=not confirm_delete, key=f"playlist_delete_{i}"
    ):
        delete_playlist(playlist_name)

        # Deleting shifts every later playlist's index down by one, so any
        # stale confirm-checkbox or cached export plan at those indices has
        # to go too -- otherwise a checked "confirm" box could carry over
        # onto a completely different playlist that now occupies that slot.
        for key in list(st.session_state.keys()):
            if key.startswith("playlist_delete_confirm_") or key.startswith(
                "playlist_export_plan_"
            ):
                del st.session_state[key]

        st.rerun()


def _render_playlist_export():
    st.write(
        "Build a named playlist from your library, then export it as its "
        "own folder — shuffle it once you're in the car, so song order "
        "doesn't matter here."
    )

    playlist_mode = st.segmented_control(
        "Playlist option",
        ["Your Playlists", "New Smart Playlist", "New Manual Playlist", "New Playlist by Date"],
        default="Your Playlists",
        required=True,
        key="playlist_export_mode",
    )

    st.divider()

    if playlist_mode == "Your Playlists":
        _render_saved_playlists()
    elif playlist_mode == "New Smart Playlist":
        _render_smart_playlist_builder()
    elif playlist_mode == "New Manual Playlist":
        _render_manual_playlist_builder()
    else:
        _render_date_playlist_builder()


EXPORT_MODES = {
    "Flattened files": _render_flatten_export,
    "Artist folders": _render_artist_folder_export,
    "CSV file info": _render_csv_export,
    "Playlists": _render_playlist_export,
}


CLEAN_UP_TOOLS = {
    "Normalize": _render_normalize_tool,
    "Duplicate Artist": _render_duplicate_artist_tool,
    "Genre": _render_genre_tool,
    "DRM Files": _render_drm_tool,
    "Duplicate Files": _render_duplicate_files_tool,
    "Multi-Artist Credits": _render_multi_artist_tool,
    "Featured-Credit Spelling": _render_title_feat_consistency_tool,
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

    _folder_picker_input(
        "Library folder",
        key="library_path_input",
        default_value=DEFAULT_LIBRARY_PATH,
        prompt="Select your music library folder",
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
            _run_import(library_path)

            songs_scanned = st.session_state["report"]["songs_scanned"]
            drm_count = st.session_state.get("drm_plan", {"total_files": 0})["total_files"]

            message = f"Import complete! Found {songs_scanned} playable song(s)"

            if drm_count:
                message += (
                    f" and {drm_count} DRM-protected file(s) — these can't play in "
                    "a Tesla, but you can review them in Clean Up Tools → DRM Files."
                )
            else:
                message += "."

            message += " Head to the Review tab for a full summary."

            st.success(message)

    if st.session_state.get("report") is not None:
        songs_scanned = st.session_state["report"]["songs_scanned"]
        drm_count = st.session_state.get("drm_plan", {"total_files": 0})["total_files"]

        info_text = (
            f"Currently imported: {st.session_state['library_path']} "
            f"({songs_scanned} playable song(s)"
        )

        if drm_count:
            info_text += f", {drm_count} DRM-protected"

        info_text += ")"

        st.info(info_text)

with tab_review:
    st.header("Review")

    report = st.session_state.get("report")

    if report is None:
        st.info("Import a library first on the Import tab.")

    else:
        st.subheader("Summary")

        format_counts = list(report["formats"].most_common())
        drm_count = st.session_state.get("drm_plan", {"total_files": 0})["total_files"]

        if drm_count:
            format_counts.append(("m4p", drm_count))
            format_counts.sort(key=lambda item: item[1], reverse=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Songs scanned", report["songs_scanned"])
        col2.metric("Unique artists", len(report["artists"]))
        col3.metric("File formats", len(format_counts))

        _render_volume_storage_info(st.session_state["library_path"])

        with st.expander("File formats"):
            for extension, count in format_counts:
                note = (
                    " — DRM-protected, can't play in a Tesla" if extension == "m4p" else ""
                )
                st.write(f"**{extension.upper()}**: {count} songs{note}")

        st.subheader("Audio quality")

        quality_summary = summarize_bitrate_quality(report["artist_songs"])
        quality_counts = quality_summary["counts"]

        quality_cols = st.columns(3)
        quality_cols[0].metric(
            f"Low quality (<{LOW_BITRATE_THRESHOLD_KBPS}kbps)", quality_counts["low"]
        )
        quality_cols[1].metric("Standard quality", quality_counts["standard"])
        quality_cols[2].metric(
            f"High quality (>{HIGH_BITRATE_THRESHOLD_KBPS}kbps)", quality_counts["high"]
        )

        if quality_counts["unknown"]:
            st.caption(f"{quality_counts['unknown']} song(s) had no readable bitrate.")

        if quality_counts["low"]:
            with st.expander(f"Show low-quality songs ({quality_counts['low']})"):
                for song in quality_summary["low_quality_songs"]:
                    st.caption(f"{song.artist} — {song.title} ({song.bitrate} kbps)")

        st.subheader("What the tool found")

        st.caption(f"{len(st.session_state.get('genre_counts', {}))} distinct genre(s) found.")

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
                "Duplicate genre spellings",
                len(st.session_state.get("genre_recommendations", [])),
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

        st.subheader("Album artwork")

        artwork_running_state = _finish_artwork_search_if_done()

        if artwork_running_state is not None:
            percent = (
                round(artwork_running_state.completed / artwork_running_state.total * 100)
                if artwork_running_state.total
                else 0
            )
            st.info(
                f"🎨 Artwork check running in the background — "
                f"{artwork_running_state.completed}/{artwork_running_state.total} "
                f"({percent}%). Feel free to use Clean Up Tools while this "
                "finishes — there's a live progress bar in "
                "Clean Up Tools → Artwork."
            )

        elif st.session_state.get("artwork_plan") is not None:
            artwork_plan_summary = st.session_state["artwork_plan"]
            st.success(
                f"✅ Artwork check complete — "
                f"{artwork_plan_summary['total_files']} song(s) without artwork. "
                "Review potential artwork matches in Clean Up Tools → Artwork."
            )

        else:
            st.write(
                "Not checked yet. This needs live network lookups and can "
                "take a while on a large library, so it isn't run "
                "automatically at import."
            )

            if st.button("Start Album Artwork Check"):
                _start_artwork_search(report["artist_songs"])
                st.rerun()

            st.caption(
                "Runs in the background, so you can keep using Clean Up "
                "Tools while it finishes — there's a live progress bar in "
                "Clean Up Tools → Artwork."
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
        current_library_path = None
        if st.session_state.get("library_path"):
            current_library_path = str(Path(st.session_state["library_path"]).resolve())

        matching_sessions = (
            [s for s in sessions if get_backup_library_path(s) == current_library_path]
            if current_library_path is not None
            else []
        )
        earliest_session_for_current_library = min(matching_sessions) if matching_sessions else None

        session = st.selectbox(
            "Backup session",
            sessions,
            format_func=lambda s: _format_backup_session_label(
                s, current_library_path, earliest_session_for_current_library
            ),
        )

        if st.button("Preview Restore"):
            st.session_state["restore_plan"] = build_restore_plan(session)

        restore_plan = st.session_state.get("restore_plan")

        if restore_plan is not None:
            st.info(
                f"{restore_plan['total_files']} file(s) will be restored from "
                f"{_format_backup_session_label(restore_plan['backup_session'], current_library_path, earliest_session_for_current_library)}"
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

    if st.session_state.get("report") is None:
        st.info("Import a library first on the Import tab.")

    else:
        export_mode = st.segmented_control(
            "Export as",
            list(EXPORT_MODES.keys()),
            default="Flattened files",
            required=True,
            key="export_mode",
        )

        st.divider()

        EXPORT_MODES[export_mode]()
