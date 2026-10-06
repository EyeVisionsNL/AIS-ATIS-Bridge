from __future__ import annotations

from collections import deque
import re
import select
import socket
import subprocess
import tempfile
import threading
import time
from typing import Any

import numpy as np

from .atis import SAMPLE_RATE_HZ, decode_samples
from .audio import LiveAudio
from .recordings import RecentRecordings, float32_to_pcm16
from .smart_gain import REFERENCE_GAIN_DB, probe_receiver_gain


LIVE_AUDIO_PORT = 49555
RECORDING_AUDIO_PORT = LIVE_AUDIO_PORT + 1
SCAN_LOG = re.compile(r"Activity on\s+(\d+(?:\.\d+)?)\s+MHz(?:\s+\(([^)]*)\))?", re.IGNORECASE)


class ReceiverRuntime:
    def __init__(self) -> None:
        self.audio = LiveAudio()
        self.recordings = RecentRecordings(SAMPLE_RATE_HZ)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._latest: dict[str, Any] | None = None
        self._error: str | None = None
        self._started: float | None = None
        self._packets = 0
        self._gain_status: dict[str, Any] = {"state": "IDLE", "gain_db": None, "error": None}
        self._log_tail = deque(maxlen=12)
        self._scan_events: deque[tuple[float, dict[str, Any]]] = deque(maxlen=64)

    def start(self, settings: dict[str, Any]) -> None:
        self.stop()
        if not settings.get("receiver"):
            raise ValueError("Select a second RTL-SDR first")
        self._stop.clear()
        self._error = None
        self._started = time.time()
        self._packets = 0
        with self._lock:
            self._scan_events.clear()
            self._log_tail.clear()
            self._gain_status = {"state": "PROBING" if settings.get("gain_mode") == "smart" else "MANUAL",
                                 "gain_db": None, "error": None}
        self._thread = threading.Thread(target=self._run, args=(dict(settings),),
                                        daemon=True, name="atis-receiver")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self._thread and self._thread.is_alive():
            raise RuntimeError("The previous RTL-SDR session is still stopping; try again shortly")
        with self._lock:
            self._process = None
        self.recordings.finish_if_idle(force=True)
        self.audio.clear()

    @staticmethod
    def render_airband_config(settings: dict[str, Any], resolved_gain_db: float | None = None) -> str:
        channels = settings["channels"]
        if settings["tuning_mode"] == "fixed":
            channels = [next(item for item in channels
                             if item["id"] == settings["selected_channel_id"])]
        else:
            channels = [item for item in channels if item["scan_enabled"]]
        gain = (float(resolved_gain_db) if resolved_gain_db is not None else
                (REFERENCE_GAIN_DB if settings["gain_mode"] == "smart"
                 else float(settings["gain_db"])))
        squelch = (
            f"squelch_threshold = {int(settings.get('squelch_threshold_dbfs', -47))};"
            if settings.get("squelch_mode", "auto") == "manual"
            else "squelch_snr_threshold = 4.0;"
        )
        frequencies = ", ".join(f"{item['frequency_mhz']:.6f}" for item in channels)
        labels = ", ".join('"' + item["label"].replace('"', "") + '"' for item in channels)
        return f'''log_scan_activity = true;
scan_interval_ms = {int(settings.get('scan_interval_ms', 200))};
devices:
({{
  type = "rtlsdr";
  serial = "{settings['receiver'].replace('"', '')}";
  gain = {gain:.1f};
  correction = {settings['ppm']};
  mode = "scan";
  channels:
  ({{
    modulation = "nfm";
    freqs = ( {frequencies} );
    labels = ( {labels} );
    {squelch}
    outputs: (
      {{ type = "udp_stream"; dest_address = "127.0.0.1"; dest_port = {LIVE_AUDIO_PORT}; continuous = true; }},
      {{ type = "udp_stream"; dest_address = "127.0.0.1"; dest_port = {RECORDING_AUDIO_PORT}; continuous = false; }}
    );
  }});
}});
'''

    @staticmethod
    def _selected_channels(settings: dict[str, Any]) -> list[dict[str, Any]]:
        if settings["tuning_mode"] == "fixed":
            return [next(item for item in settings["channels"]
                         if item["id"] == settings["selected_channel_id"])]
        return [item for item in settings["channels"] if item["scan_enabled"]]

    def _watch_scan_log(self, process: subprocess.Popen, channels: list[dict[str, Any]]) -> None:
        stream = process.stderr
        if stream is None:
            return
        for raw_line in iter(stream.readline, b""):
            line = raw_line.decode("utf-8", "replace") if isinstance(raw_line, bytes) else raw_line
            with self._lock:
                self._log_tail.append(line.strip())
            match = SCAN_LOG.search(line)
            if not match:
                continue
            frequency = round(float(match.group(1)), 6)
            channel = next((item for item in channels
                            if abs(float(item["frequency_mhz"]) - frequency) <= 0.0005), None)
            metadata = {"channel": (channel or {}).get("label") or (match.group(2) or "").strip() or "Marine channel",
                        "frequency_mhz": frequency}
            with self._lock:
                self._scan_events.append((time.time(), metadata))
            self.recordings.resolve_recent_metadata(metadata)

    def _recording_metadata(self, settings: dict[str, Any]) -> dict[str, Any]:
        if settings["tuning_mode"] == "fixed":
            channel = next(item for item in settings["channels"]
                           if item["id"] == settings["selected_channel_id"])
            return {"channel": channel["label"], "frequency_mhz": channel["frequency_mhz"]}
        selected = self._selected_channels(settings)
        if len(selected) == 1:
            return {"channel": selected[0]["label"], "frequency_mhz": selected[0]["frequency_mhz"]}
        now = time.time()
        with self._lock:
            candidates = [(stamp, info) for stamp, info in self._scan_events if now - stamp <= 20]
        if candidates:
            return dict(max(candidates, key=lambda item: item[0])[1])
        return {"channel": "Marine scan · channel unknown", "frequency_mhz": None}

    def _run(self, settings: dict[str, Any]) -> None:
        process = None
        try:
            channels = self._selected_channels(settings)
            if not channels:
                raise ValueError("Enable at least one channel before starting the scanner")
            resolved_gain = float(settings["gain_db"])
            if settings["gain_mode"] == "smart":
                try:
                    measured = probe_receiver_gain(
                        str(settings["receiver"]),
                        [float(item["frequency_mhz"]) for item in channels],
                        self._stop,
                    )
                    resolved_gain = float(measured["gain_db"])
                    with self._lock:
                        self._gain_status = {"state": "READY", **measured, "error": None}
                except Exception as error:
                    # A missing or busy tuner must not prevent listening. Stay
                    # at the conservative SDRCC reference and report fallback.
                    resolved_gain = REFERENCE_GAIN_DB
                    with self._lock:
                        self._gain_status = {
                            "state": "FALLBACK", "gain_db": resolved_gain,
                            "probed_channels": 0, "error": str(error),
                        }
            else:
                with self._lock:
                    self._gain_status = {"state": "MANUAL", "gain_db": resolved_gain, "error": None}
            if self._stop.is_set():
                return

            with tempfile.NamedTemporaryFile("w", suffix=".conf") as config_file, \
                    socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as live_socket, \
                    socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as recording_socket:
                for server in (live_socket, recording_socket):
                    server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
                    server.bind(("127.0.0.1", LIVE_AUDIO_PORT if server is live_socket else RECORDING_AUDIO_PORT))
                live_socket.setblocking(False)
                recording_socket.setblocking(False)
                config_file.write(self.render_airband_config(settings, resolved_gain))
                config_file.flush()
                process = subprocess.Popen(
                    ["rtl_airband", "-F", "-e", "-c", config_file.name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                )
                with self._lock:
                    self._process = process
                threading.Thread(target=self._watch_scan_log, args=(process, channels),
                                 daemon=True, name="atis-scan-log").start()
                buffer = np.empty(0, dtype=np.float32)
                last_decode = 0.0
                while not self._stop.is_set() and process.poll() is None:
                    ready, _, _ = select.select((live_socket, recording_socket), (), (), 0.2)
                    if not ready:
                        self.recordings.finish_if_idle()
                        continue
                    self.recordings.finish_if_idle()
                    for server in ready:
                        try:
                            raw, _address = server.recvfrom(65536)
                        except BlockingIOError:
                            continue
                        usable = len(raw) - len(raw) % 4
                        if not usable:
                            continue
                        samples = np.frombuffer(raw[:usable], dtype="<f4")
                        received_at = time.monotonic()
                        if server is live_socket:
                            self.audio.publish(samples)
                            self.recordings.observe_live(float32_to_pcm16(raw[:usable]), received_at)
                            buffer = np.concatenate((buffer, samples))[-SAMPLE_RATE_HZ:]
                            with self._lock:
                                self._packets += 1
                            if len(buffer) >= SAMPLE_RATE_HZ and time.monotonic() - last_decode >= 0.25:
                                last_decode = time.monotonic()
                                decoded = decode_samples(buffer)
                                if decoded:
                                    with self._lock:
                                        self._latest = {**decoded[-1], "received_epoch": time.time()}
                        else:
                            pcm = float32_to_pcm16(raw[:usable])
                            self.recordings.observe_gated(
                                pcm, received_at, self._recording_metadata(settings),
                            )
                if process.poll() not in (None, 0) and not self._stop.is_set():
                    with self._lock:
                        message = "\n".join(self._log_tail)[-500:] or "rtl_airband stopped"
                    raise RuntimeError(message.strip())
        except Exception as error:
            with self._lock:
                self._error = str(error)
        finally:
            self.recordings.finish_if_idle(force=True)
            if process and process.poll() is None:
                process.terminate()
            with self._lock:
                if self._process is process:
                    self._process = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            latest = dict(self._latest) if self._latest else None
            running = bool(self._process and self._process.poll() is None)
            error = self._error
            packets = self._packets
            gain = dict(self._gain_status)
        if latest:
            age = max(0.0, time.time() - latest.pop("received_epoch"))
            latest.update(age_seconds=round(age, 1), fresh=age <= 120)
        return {
            "running": running,
            "state": "DECODED" if latest and latest["fresh"] else ("SCANNING" if running else "STOPPED"),
            "latest": latest,
            "error": error,
            "started_epoch": self._started,
            "packets_received": packets,
            "smart_gain": gain,
            "recordings": self.recordings.list(),
        }


runtime = ReceiverRuntime()
