from __future__ import annotations

from kokoro_stream.streaming.cache import ChunkCache
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

TTFA_BUCKETS = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0)
CHUNK_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.2, 0.35, 0.5, 1.0, 2.0, 5.0)


class Metrics:
    content_type = CONTENT_TYPE_LATEST

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.ttfa = Histogram(
            "tts_time_to_first_audio_seconds",
            "Time from request start to the first audio frame leaving the service",
            buckets=TTFA_BUCKETS,
            registry=self.registry,
        )
        self.chunk_latency = Histogram(
            "tts_chunk_synthesis_seconds",
            "Wall time to synthesize one chunk",
            buckets=CHUNK_BUCKETS,
            registry=self.registry,
        )
        self.active_streams = Gauge(
            "tts_active_streams", "Streams currently being served", registry=self.registry
        )
        self.warmup_seconds = Gauge(
            "tts_warmup_seconds", "Time spent warming up the engine at startup", registry=self.registry
        )
        self.requests = Counter(
            "tts_requests_total", "Requests by endpoint and status", ["endpoint", "status"], registry=self.registry
        )
        self.audio_seconds = Counter(
            "tts_stream_audio_seconds_total", "Seconds of audio sent to stream clients", registry=self.registry
        )
        self.stream_seconds = Counter(
            "tts_stream_wall_seconds_total", "Wall time streams were open", registry=self.registry
        )
        self.rejected_streams = Counter(
            "tts_rejected_streams_total", "Streams refused because the service was full", registry=self.registry
        )
        self.stream_errors = Counter(
            "tts_stream_errors_total", "Streams that ended with an error frame", registry=self.registry
        )

    def track_cache(self, cache: ChunkCache) -> None:
        Gauge("tts_chunk_cache_hits", "Chunk cache hits", registry=self.registry).set_function(
            lambda: cache.hits
        )
        Gauge("tts_chunk_cache_misses", "Chunk cache misses", registry=self.registry).set_function(
            lambda: cache.misses
        )
        Gauge("tts_chunk_cache_bytes", "Bytes held by the chunk cache", registry=self.registry).set_function(
            lambda: cache.size_bytes
        )

    def render(self) -> bytes:
        return generate_latest(self.registry)
