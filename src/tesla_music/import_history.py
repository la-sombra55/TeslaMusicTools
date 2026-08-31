import json
from datetime import datetime
from pathlib import Path

IMPORT_HISTORY_FILE = Path("data/import_history.json")


def record_import_session(song_paths, timestamp=None):
    """
    Appends a record of exactly which songs were included in an Import
    Library run. Playlists "by date" are built from this history rather
    than each file's own filesystem timestamps -- a file moved or copied
    in from elsewhere (e.g. an old purchased track bundled into a fresh
    batch of CD rips) can keep a much older creation date than when it
    actually entered this library, which makes filesystem timestamps
    unreliable for "when was this added here."
    """
    timestamp = timestamp or datetime.now()
    sessions = _load_sessions()

    sessions.append(
        {
            "timestamp": timestamp.isoformat(),
            "songs": [str(path) for path in song_paths],
        }
    )

    _save_sessions(sessions)

    return sessions[-1]


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
