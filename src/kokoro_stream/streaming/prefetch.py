from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Deque, Generic, Iterable, Iterator, TypeVar

Item = TypeVar("Item")
Result = TypeVar("Result")


class PrefetchPool:
    def __init__(self, workers: int) -> None:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        self.workers = workers
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="prefetch")

    def submit(self, function: Callable[..., Result], *args: object) -> Future[Result]:
        return self._executor.submit(function, *args)

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)


class StreamPrefetcher(Generic[Item, Result]):
    def __init__(
        self,
        pool: PrefetchPool,
        items: Iterable[Item],
        worker: Callable[[Item], Result],
        depth: int = 3,
    ) -> None:
        self._pool = pool
        self._items: Iterator[Item] = iter(items)
        self._worker = worker
        self._depth = max(1, depth)
        self._window: Deque[Future[Result]] = deque()
        self._closed = False
        self._fill()

    def _fill(self) -> None:
        while not self._closed and len(self._window) < self._depth:
            try:
                item = next(self._items)
            except StopIteration:
                return
            self._window.append(self._pool.submit(self._worker, item))

    def __iter__(self) -> "StreamPrefetcher[Item, Result]":
        return self

    def __next__(self) -> Result:
        if not self._window:
            raise StopIteration
        current = self._window.popleft()
        self._fill()
        return current.result()

    def close(self) -> None:
        self._closed = True
        while self._window:
            self._window.popleft().cancel()

    def __enter__(self) -> "StreamPrefetcher[Item, Result]":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
