# app/utils/timing.py
from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager


@contextmanager
def timed(label: str, logger: logging.Logger) -> Generator[list[float], None, None]:
    """Measure wall-clock elapsed time for a block and log it at DEBUG level.

    Yields a single-element list; after the block exits, elapsed[0] holds the
    duration in milliseconds. The value is also emitted as a structured log field.

    Example:
        with timed('retrieval', logger) as elapsed:
            results = retriever.run(query)
        return Answer(..., processing_time_ms=elapsed[0])
    """
    elapsed: list[float] = [0.0]
    start = time.perf_counter()
    try:
        yield elapsed
    finally:
        elapsed[0] = round((time.perf_counter() - start) * 1000, 3)
        logger.debug(
            'stage completed',
            extra={'stage': label, 'elapsed_ms': elapsed[0]},
        )
