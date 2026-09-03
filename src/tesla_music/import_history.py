import json
from datetime import datetime
from pathlib import Path

IMPORT_HISTORY_FILE = Path("data/import_history.json")


def record_import_session(song_paths, timestamp=None):
    """
    Appends a record of the songs newly seen since the last recorded
    session -- not every song currently in the library. This gets called
    on every library scan, including internal refreshes after a Clean Up
    Tool operation (not just a user-initiated Import Library click), and
    a full scan naturally includes files that were already recorded in an
    earlier session. Recording the whole scan every time would make every
    session (including refresh-triggered ones) balloon to the size of the
    entire library, and "songs added between X and Y" would match nearly
    everything. Recording only the delta keeps each session meaning what
    it says: songs that are actually new as of that point in time.
    """
    sessions = _load_sessions()
    already_recorded = {path for session in sessions for path in session["songs"]}

    new_paths = [str(path) for path in song_paths if str(path) not in already_recorded]

    if not new_paths:
        return None

    timestamp = timestamp or datetime.now()

    session = {
        "timestamp": timestamp.isoformat(),
        "songs": new_paths,
    }

    sessions.append(session)
    _save_sessions(sessions)

    return session


def list_import_sessions():
    return _load_sessions()


def find_songs_from_sessions_between(start, end):
    """
    Returns the set of file paths (as strings) that appeared in any
    recorded import session whose timestamp falls within [start, end]
    (datetime objects, inclusive).
    """
    start_ts = start.timestamp()
    end_ts = end.timestamp()

    paths = set()

    for session in _load_sessions():
        session_ts = datetime.fromisoformat(session["timestamp"]).timestamp()

        if start_ts <= session_ts <= end_ts:
            paths.update(session["songs"])

    return paths


def _load_sessions():
    if not IMPORT_HISTORY_FILE.is_file():
        return []

    try:
        return json.loads(IMPORT_HISTORY_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def _save_sessions(sessions):
    IMPORT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    IMPORT_HISTORY_FILE.write_text(json.dumps(sessions, indent=2))
