from __future__ import annotations

import itertools
import queue
import threading
from collections import deque
from concurrent.futures import Future
from typing import Callable, Deque, Generic, Iterable, Iterator, TypeVar

Item = TypeVar("Item")
Result = TypeVar("Result")


HEAD_PRIORITY = 0
BODY_PRIORITY = 1
STOP_PRIORITY = 99


class PrefetchPool:
    def __init__(self, workers: int) -> None:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        self.workers = workers
        self._queue: queue.PriorityQueue[tuple] = queue.PriorityQueue()
        self._order = itertools.count()
        self._closed = False
        self._threads = [
            threading.Thread(target=self._run, name=f"prefetch-{index}", daemon=True)
            for index in range(workers)
        ]
        for thread in self._threads:
            thread.start()

    def submit(self, function: Callable[..., Result], *args: object, priority: int = BODY_PRIORITY) -> Future[Result]:
        if self._closed:
            raise RuntimeError("pool is shut down")
        future: Future[Result] = Future()
        self._queue.put((priority, next(self._order), future, function, args))
        return future

    def _run(self) -> None:
        while True:
            priority, _, future, function, args = self._queue.get()
            if priority == STOP_PRIORITY:
                return
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(function(*args))
            except BaseException as error:
                future.set_exception(error)

    def shutdown(self, wait: bool = True) -> None:
        self._closed = True
        while True:
            try:
                _, _, future, _, _ = self._queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(future, Future):
                future.cancel()
        for _ in self._threads:
            self._queue.put((STOP_PRIORITY, next(self._order), None, None, ()))
        if wait:
            for thread in self._threads:
                thread.join()


class StreamPrefetcher(Generic[Item, Result]):
    def __init__(
        self,
        pool: PrefetchPool,
        items: Iterable[Item],
        worker: Callable[[Item], Result],
        depth: int = 3,
        head_first: bool = True,
    ) -> None:
        self._pool = pool
        self._items: Iterator[Item] = iter(items)
        self._worker = worker
        self._depth = max(1, depth)
        self._window: Deque[Future[Result]] = deque()
        self._submitted = 0
        self._closed = False
        self._head_pending = head_first
        self._fill()

    def _fill(self) -> None:
        capacity = 1 if self._head_pending else self._depth
        while not self._closed and len(self._window) < capacity:
            try:
                item = next(self._items)
            except StopIteration:
                return
            priority = HEAD_PRIORITY if self._submitted == 0 else BODY_PRIORITY
            self._submitted += 1
            self._window.append(self._pool.submit(self._worker, item, priority=priority))

    def __iter__(self) -> "StreamPrefetcher[Item, Result]":
        return self

    def __next__(self) -> Result:
        if not self._window:
            raise StopIteration
        current = self._window.popleft()
        if self._head_pending:
            result = current.result()
            self._head_pending = False
            self._fill()
            return result
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
