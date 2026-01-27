from __future__ import annotations

import logging
import time
from typing import Iterator

from kokoro_stream.service.metrics import Metrics
from kokoro_stream.streaming.frames import FrameType

logger = logging.getLogger(__name__)


def instrument_stream(
    frames: Iterator[bytes],
    metrics: Metrics,
    started: float,
    request_id: str = "",
    detect_errors: bool = True,
) -> Iterator[bytes]:
    metrics.active_streams.inc()
    first_frame = True
    frame_count = 0
    try:
        for frame in frames:
            frame_count += 1
            if first_frame:
                metrics.ttfa.observe(time.perf_counter() - started)
                logger.info("stream %s first frame after %.0f ms", request_id, (time.perf_counter() - started) * 1000)
                first_frame = False
            if detect_errors and frame[5] == FrameType.ERROR:
                metrics.stream_errors.inc()
                logger.warning("stream %s ended with an error frame", request_id)
            yield frame
    finally:
        logger.info("stream %s closed after %d frames in %.2f s", request_id, frame_count, time.perf_counter() - started)
        metrics.active_streams.dec()
        close = getattr(frames, "close", None)
        if close:
            close()
