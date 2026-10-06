"""Small in-memory ring of recent squelch-open Marine transmissions."""

from __future__ import annotations

from collections import deque
from datetime import datetime
import struct
import threading
import time
from typing import Any
from uuid import uuid4


RECORDING_COUNT = 4
PRE_ROLL_SECONDS = 0.4
POST_ROLL_SECONDS = 0.4
GAP_SECONDS = 0.7
MAX_RECORDING_SECONDS = 120.0


def float32_to_pcm16(payload: bytes) -> bytes:
    """Convert finite little-endian float audio to clipped mono PCM16."""
    usable = len(payload) - len(payload) % 4
    if not usable:
        return b""
    output = bytearray(usable // 2)
    for index, (value,) in enumerate(struct.iter_unpack("<f", payload[:usable])):
        sample = value if value == value and abs(value) != float("inf") else 0.0
        sample = max(-1.0, min(1.0, sample))
        struct.pack_into("<h", output, index * 2, round(sample * 32767.0))
    return bytes(output)


def _wav(pcm: bytes, sample_rate: int) -> bytes:
    size = len(pcm)
    return b"".join((
        b"RIFF", struct.pack("<I", 36 + size), b"WAVE",
        b"fmt ", struct.pack("<IHHIIHH", 16, 1, 1, sample_rate,
                             sample_rate * 2, 2, 16),
        b"data", struct.pack("<I", size), pcm,
    ))


class RecentRecordings:
    """Store no more than four latest receptions, each capped at two minutes."""

    def __init__(self, sample_rate: int = 16_000) -> None:
        self.sample_rate = max(1, int(sample_rate))
        self._max_bytes = int(self.sample_rate * 2 * MAX_RECORDING_SECONDS)
        self._lock = threading.RLock()
        self._history: deque[tuple[float, bytes]] = deque()
        self._done: deque[dict[str, Any]] = deque(maxlen=RECORDING_COUNT)
        self._active: dict[str, Any] | None = None

    def observe_live(self, pcm: bytes, moment: float | None = None) -> None:
        if not pcm:
            return
        received = time.monotonic() if moment is None else float(moment)
        with self._lock:
            self._history.append((received, bytes(pcm)))
            cutoff = received - PRE_ROLL_SECONDS - POST_ROLL_SECONDS - GAP_SECONDS - 1
            while self._history and self._history[0][0] < cutoff:
                self._history.popleft()
            active = self._active
            if active and received > active["last_gate"]:
                active["tail"].append((received, bytes(pcm)))

    def observe_gated(
        self, pcm: bytes, moment: float, metadata: dict[str, Any] | None = None,
    ) -> tuple[str, bool]:
        if not pcm:
            return "", False
        received = float(moment)
        with self._lock:
            if self._active and received - self._active["last_gate"] >= GAP_SECONDS:
                self._finish_locked()
            started = self._active is None
            if started:
                info = metadata or {}
                self._active = {
                    "id": uuid4().hex,
                    "started_monotonic": received,
                    "received_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "channel": str(info.get("channel") or "Marine scan · channel unknown"),
                    "frequency_mhz": info.get("frequency_mhz"),
                    "pcm": bytearray(),
                    "tail": [],
                    "last_gate": received,
                }
                for stamp, chunk in self._history:
                    if received - PRE_ROLL_SECONDS <= stamp < received:
                        self._append(chunk)
            self._append(pcm)
            self._active["tail"].clear()
            self._active["last_gate"] = received
            return self._active["id"], started

    def resolve_recent_metadata(self, metadata: dict[str, Any], moment: float | None = None) -> None:
        # Scanner messages can arrive slightly after their first UDP packet.
        received = time.monotonic() if moment is None else float(moment)
        with self._lock:
            active = self._active
            if active and 0 <= received - active["started_monotonic"] <= 0.6:
                active["channel"] = metadata["channel"]
                active["frequency_mhz"] = metadata["frequency_mhz"]

    def finish_if_idle(self, moment: float | None = None, *, force: bool = False) -> bool:
        received = time.monotonic() if moment is None else float(moment)
        with self._lock:
            if not self._active or (not force and received - self._active["last_gate"] < GAP_SECONDS):
                return False
            self._finish_locked()
            return True

    def _append(self, pcm: bytes) -> None:
        if self._active is None:
            return
        available = self._max_bytes - len(self._active["pcm"])
        if available > 0:
            self._active["pcm"].extend(pcm[:available])

    def _finish_locked(self) -> None:
        active = self._active
        if active is None:
            return
        tail_end = active["last_gate"] + POST_ROLL_SECONDS
        for stamp, chunk in active["tail"]:
            if active["last_gate"] < stamp <= tail_end:
                self._append(chunk)
        if len(active["pcm"]) >= int(self.sample_rate * 2 * 0.08):
            active["pcm"] = bytes(active["pcm"])
            active.pop("tail", None)
            active.pop("last_gate", None)
            self._done.append(active)
        self._active = None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            clips = ([self._active] if self._active else []) + list(reversed(self._done))
            result = []
            for clip in clips[:RECORDING_COUNT]:
                result.append({
                    "id": clip["id"],
                    "received_at": clip["received_at"],
                    "channel": clip["channel"],
                    "frequency_mhz": clip["frequency_mhz"],
                    "duration_seconds": round(len(clip["pcm"]) / (self.sample_rate * 2), 1),
                    "complete": "tail" not in clip,
                    "play_url": f"/api/recordings/{clip['id']}.wav" if "tail" not in clip else None,
                })
            return result

    def get_wav(self, recording_id: str) -> bytes | None:
        with self._lock:
            clip = next((item for item in self._done if item["id"] == recording_id), None)
            pcm = bytes(clip["pcm"]) if clip else None
        return _wav(pcm, self.sample_rate) if pcm is not None else None
