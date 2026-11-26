"""
PlayerTracker backend — Railway/Render free tier
POST /heartbeat        { "id": "NICKORTID", "room": "ABCD1", "platform": "Steam" }
GET  /status/<id>      → { "id": "...", "room": "...", "last_seen": "...", "online": true/false }
GET  /ping             → 200 OK (health check)

Online = heartbeat received within ONLINE_WINDOW_SECONDS
"""

import os
import json
import time
from datetime import datetime, timezone
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

# In-memory store: id.lower() → sighting dict
# Persists to sightings.json on Railway's ephemeral disk — survives restarts
# within the same deployment, gone on redeploy (fine for a tracker)
_STORE: dict[str, dict] = {}
_PERSIST_PATH = "sightings.json"

# A player is considered "online" if their last heartbeat
# was within this window (seconds). GT rooms time out fast
# so 45s is generous — mod sends every 20s while in room.
ONLINE_WINDOW_SECONDS = 45


def _load():
    global _STORE
    if os.path.exists(_PERSIST_PATH):
        try:
            with open(_PERSIST_PATH, "r") as f:
                _STORE = json.load(f)
        except Exception:
            _STORE = {}


def _save():
    try:
        with open(_PERSIST_PATH, "w") as f:
            json.dump(_STORE, f)
    except Exception:
        pass


_load()


@app.route("/ping")
def ping():
    return "ok", 200


@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(silent=True)
    if not data:
        abort(400)

    player_id = str(data.get("id", "")).strip()
    room      = str(data.get("room", "")).strip()
    platform  = str(data.get("platform", "unknown")).strip()

    if not player_id or not room:
        abort(400)

    now = time.time()
    _STORE[player_id.lower()] = {
        "id":        player_id,
        "room":      room,
        "platform":  platform,
        "last_seen": now,
        "last_seen_readable": datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    _save()
    return jsonify({"ok": True}), 200


@app.route("/status/<player_id>")
def status(player_id: str):
    entry = _STORE.get(player_id.lower())
    if not entry:
        return jsonify({
            "id":       player_id,
            "online":   False,
            "room":     None,
            "platform": None,
            "last_seen": None,
            "last_seen_readable": None,
        }), 200

    online = (time.time() - entry["last_seen"]) < ONLINE_WINDOW_SECONDS
    return jsonify({
        "id":                player_id,
        "online":            online,
        "room":              entry["room"] if online else None,
        "platform":          entry["platform"],
        "last_seen":         entry["last_seen"],
        "last_seen_readable": entry["last_seen_readable"],
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
