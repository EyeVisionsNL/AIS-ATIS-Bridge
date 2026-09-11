"""Bounded live PCM buffer. Each browser keeps its own non-consuming cursor."""
from collections import deque
import threading
import time

import numpy as np

from .atis import SAMPLE_RATE_HZ


class LiveAudio:
    def __init__(self):
        self._lock = threading.Lock()
        self._chunks = deque(maxlen=64)
        self._sequence = 0

    def clear(self):
        with self._lock:
            self._chunks.clear()

    def publish(self, samples):
        # Copy/convert only the browser output; the ATIS decoder keeps its input.
        values = np.nan_to_num(samples[-SAMPLE_RATE_HZ:], nan=0.0, posinf=1.0, neginf=-1.0)
        pcm = (np.clip(values, -1.0, 1.0) * 32767).astype('<i2').tobytes()
        if not pcm:
            return
        with self._lock:
            self._sequence += 1
            self._chunks.append((self._sequence, time.monotonic(), pcm))

    def read(self, after):
        with self._lock:
            sequence = self._sequence
            # A new listener or restarted server starts at live, never at history.
            if after is None or after > sequence:
                return sequence, b''
            cutoff = time.monotonic() - 1.0
            data = b''.join(pcm for seq, timestamp, pcm in self._chunks
                            if seq > after and timestamp >= cutoff)
            return sequence, data[-SAMPLE_RATE_HZ * 2:]
