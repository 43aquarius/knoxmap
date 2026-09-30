"""Discord Rich Presence: what KnoxMap is doing, on your Discord profile.

Discord's local client listens on a named pipe and speaks a small framed-JSON
protocol, so this needs no library: a frame is a little-endian uint32 opcode,
a little-endian uint32 length, and that many bytes of JSON. Opcode 0 is the
handshake, 1 a command, 2 a close.

Everything here fails quietly. Discord not running, a pipe that disappears
when it restarts, a permission error on the socket - none of it is the
player's problem and none of it may interrupt a map that is halfway built, so
every call is wrapped and the worst case is no presence.

It runs on its own thread: the IPC write is a blocking pipe write, and the
generator must never wait on Discord to finish a tile.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import threading
import time
import uuid

import knoxlog
import knoxpaths

log = knoxlog.log

# The Discord application the presence is published as. It carries the name
# on the profile - "Playing KnoxMap" - and the artwork. An application id is
# not a secret and is readable out of any build; it is not a token and grants
# nothing, so it lives here rather than in a config a player has to fill in.
# A build can override it with KNOXMAP_DISCORD_APP_ID or discord_app_id in
# the config file.
#
# Its art asset is named "knoxmap" and is branding/logo.png, uploaded under
# Rich Presence -> Art Assets in the Discord developer portal.
DEFAULT_APP_ID = "1554593562010845275"

# Discord refuses updates faster than about one every 15 seconds and drops
# the rest, so a build that reports every tile would mostly be talking to
# itself. The last state is kept and sent when the window opens again.
MIN_GAP_S = 15.0
# How long to wait before trying the pipe again after it refuses or vanishes.
RETRY_S = 60.0

_HANDSHAKE, _FRAME, _CLOSE = 0, 1, 2


def app_id() -> str:
    """The Discord application id, from the config file or the environment."""
    env = os.environ.get("KNOXMAP_DISCORD_APP_ID", "").strip()
    if env:
        return env
    try:
        return str(knoxpaths.load_config().get("discord_app_id", "")
                   or DEFAULT_APP_ID).strip()
    except Exception:  # noqa: BLE001 - a broken config is not worth a crash
        return DEFAULT_APP_ID


def enabled() -> bool:
    """Whether to publish presence at all. Off unless asked for.

    Presence tells everyone on your friends list what you are doing, which is
    not a thing to switch on for somebody without asking, so it is opt-in and
    needs an application id to publish as.
    """
    if os.environ.get("KNOXMAP_NO_DISCORD"):
        return False
    if not app_id():
        return False
    try:
        return bool(knoxpaths.load_config().get("discord_presence", False))
    except Exception:  # noqa: BLE001
        return False


def _pipe_paths():
    """Where Discord listens, in the order Discord itself looks."""
    if sys.platform == "win32":
        for i in range(10):
            yield rf"\\.\pipe\discord-ipc-{i}"
        return
    base = (os.environ.get("XDG_RUNTIME_DIR")
            or os.environ.get("TMPDIR")
            or os.environ.get("TMP")
            or os.environ.get("TEMP")
            or tempfile.gettempdir())
    # Flatpak and Snap Discord put their socket a level or two down.
    roots = [base,
             os.path.join(base, "app", "com.discordapp.Discord"),
             os.path.join(base, "snap.discord")]
    for root in roots:
        for i in range(10):
            yield os.path.join(root, f"discord-ipc-{i}")


class _Pipe:
    """One connection to the Discord client, or nothing."""

    def __init__(self) -> None:
        self._f = None
        self._sock = None

    def open(self, client_id: str) -> bool:
        for path in _pipe_paths():
            try:
                if sys.platform == "win32":
                    self._f = open(path, "r+b", buffering=0)
                else:
                    import socket as _socket
                    if not os.path.exists(path):
                        continue
                    self._sock = _socket.socket(_socket.AF_UNIX,
                                                _socket.SOCK_STREAM)
                    self._sock.settimeout(2.0)
                    self._sock.connect(path)
            except (OSError, ValueError):
                self.close()
                continue
            try:
                self._send(_HANDSHAKE, {"v": 1, "client_id": client_id})
                return True
            except OSError:
                self.close()
        return False

    def _send(self, op: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        frame = struct.pack("<II", op, len(body)) + body
        if self._f is not None:
            self._f.write(frame)
            self._f.flush()
        elif self._sock is not None:
            self._sock.sendall(frame)
        else:
            raise OSError("not connected")

    def activity(self, activity: dict | None) -> None:
        self._send(_FRAME, {
            "cmd": "SET_ACTIVITY",
            "nonce": str(uuid.uuid4()),
            "args": {"pid": os.getpid(), "activity": activity},
        })

    def close(self) -> None:
        for handle in (self._f, self._sock):
            try:
                if handle is not None:
                    handle.close()
            except OSError:
                pass
        self._f = self._sock = None

    @property
    def live(self) -> bool:
        return self._f is not None or self._sock is not None


class Presence:
    """The presence KnoxMap publishes, updated from whatever it is doing."""

    def __init__(self) -> None:
        self._pipe = _Pipe()
        self._lock = threading.Lock()
        self._want: dict | None = None
        self._sent: dict | None = None
        self._sent_at = 0.0
        self._next_try = 0.0
        self._started = time.time()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # -- what to show ----------------------------------------------------
    def set(self, details: str, state: str | None = None,
            *, keep_start: bool = True) -> None:
        """Say what the player is doing. Cheap, and safe from any thread."""
        if not enabled():
            return
        activity = {
            "details": details[:128],
            "assets": {"large_image": "knoxmap", "large_text": "KnoxMap"},
        }
        if state:
            activity["state"] = state[:128]
        if keep_start:
            activity["timestamps"] = {"start": int(self._started)}
        with self._lock:
            self._want = activity
        self._ensure_thread()

    def clear(self) -> None:
        with self._lock:
            self._want = None
        self._ensure_thread()

    # -- the thread ------------------------------------------------------
    def _ensure_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="discord",
                                        daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self._tick()
            except Exception as exc:  # noqa: BLE001 - never leaves this thread
                log.debug("discord presence: %s", exc)
                self._pipe.close()
                self._next_try = time.time() + RETRY_S

    def _tick(self) -> None:
        with self._lock:
            want = self._want
        if want == self._sent and self._pipe.live:
            return
        now = time.time()
        if now - self._sent_at < MIN_GAP_S:
            return
        if not self._pipe.live:
            if now < self._next_try:
                return
            if not self._pipe.open(app_id()):
                self._next_try = now + RETRY_S
                return
            # A fresh connection has nothing on it, so resend whatever the
            # state is rather than trusting what was sent down the old one.
            self._sent = object()          # never equal to an activity dict
        self._pipe.activity(want)
        self._sent = want
        self._sent_at = now

    def close(self) -> None:
        self._stop.set()
        try:
            if self._pipe.live:
                self._pipe.activity(None)
        except Exception:  # noqa: BLE001
            pass
        self._pipe.close()


# One per process. Importing this module costs a lock and nothing else; no
# pipe is opened until something actually sets a presence.
presence = Presence()


# What each stage of the pipeline says on the profile, in the author's own
# words. Three of them cover the whole pipeline: the two download stages read
# the same, and so do the two that write the map out.
#
# There is deliberately no entry for "error": a failed build is not something
# to announce to somebody's friends list. A stage with no entry here leaves
# the presence as it was rather than replacing it - except the ones in
# STAGE_CLEARS, which take it down.
STAGE_TEXT = {
    "osm": "Scooping data from osm",
    "overture": "Scooping data from osm",
    "render": "Mapping",
    "buildings": "Mapping",
    "compile": "Compiling",
    "install": "Compiling",
}
# The run is over: show nothing rather than leave "Compiling" up all evening.
STAGE_CLEARS = {"done", "stopped", "stopping", "error"}


def stage(name: str, map_name: str = "") -> None:
    """Publish one pipeline stage. Safe to call from a worker thread."""
    if name in STAGE_CLEARS:
        presence.clear()
        return
    text = STAGE_TEXT.get(name)
    if not text:
        return
    presence.set(text, map_name or None)
