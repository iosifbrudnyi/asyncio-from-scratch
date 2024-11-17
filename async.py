import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import NamedTuple, Callable, List, Union, Generator


class FutureStatus(Enum):
    DONE = "DONE"
    SCHEDULED = "SCHEDULED"
    CANCELLED = "CANCELLED"


class Callback(NamedTuple):
    fn: Callable
    args: List


@dataclass
class Event:
    callback: Callback
    when: Union[datetime, None] = None


class Loop:
    events: List[Event]

    def __init__(self) -> None:
        self.events = []

    def call_soon(self, c: Callback):
        self.events.append(Event(c, when=datetime.now()))

    def call_later(self, c: Callback, when: datetime):
        self.events.append(Event(c, when=when))


current_loop: Loop = Loop()


@dataclass
class Future:
    callbacks: List[Callback] = field(default_factory=list)
    status: FutureStatus = FutureStatus.SCHEDULED

    @property
    def result(self):
        return getattr(self, "_result", None)

    def done(self):
        return self.status != FutureStatus.SCHEDULED

    def set_result(self, value):
        self._result = value
        self.status = FutureStatus.DONE
        self._schedule_callbacks()

    def cancel(self):
        self.status = FutureStatus.CANCELLED

    def __iter__(self):
        if self.status == FutureStatus.DONE:
            return self.result

        if self.status == FutureStatus.CANCELLED:
            return None

        yield self

    def add_done_callback(self, c: Callback):
        self.callbacks.append(c)

    def _schedule_callbacks(self):
        for callback in self.callbacks:
            current_loop.call_soon(callback)

    __await__ = __iter__


def create_future():
    return Future()


def run(*coros: List[Generator]):
    if len(coros) <= 0:
        return

    results = []

    for coro in coros:
        current_loop.call_soon(Callback(coro.send, [None]))

    while len(current_loop.events):
        current_loop.events.sort(key=lambda e: e.when)
        now = datetime.now()
        current_event = current_loop.events[0]
        print("current event", current_event, f"{now=}")
        if current_event.when <= now:
            try:
                res_or_fut = current_event.callback.fn(*current_event.callback.args)
            except StopIteration as exc:
                res_or_fut = exc.value

            if isinstance(res_or_fut, Future):
                res_or_fut.add_done_callback(
                    Callback(current_event.callback.fn, current_event.callback.args)
                )
            elif res_or_fut is None:
                results.append(res_or_fut)

            del current_loop.events[0]
        else:
            print(
                "loop sleeping ...", (current_event.when - datetime.now()).seconds + 0.5
            )
            time.sleep((current_event.when - datetime.now()).seconds + 0.5)

    return results


def sleep(delay, result=None):
    """Coroutine that completes after a given time (in seconds)."""

    future = create_future()

    current_loop.call_later(
        Callback(future.set_result, [result]),
        datetime.now() + timedelta(seconds=delay),
    )

    yield from future
    print("slept async", delay, "seconds")
    return future.result

if __name__ == '__main__':
    run(sleep(5), sleep(2), sleep(2))
