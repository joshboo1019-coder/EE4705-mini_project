"""
runtime.py — STUDENT B OWNS THIS FILE. Which executor serves which queue.

main.py creates the chat thread and the executor separately, both around one
CommandQueue, and only passes the queue to the chat thread. The executor
binds itself to its queue here, so the chat thread can reach it for the stop
fast path (and, from step 4, the robot state) without changing main.py.
Weak references: an executor that is gone (e.g. after a test) is never used.
"""

import threading
import weakref

_lock = threading.Lock()
_bindings = {}    # id(queue) -> (weakref(queue), weakref(executor))


def bind(queue, executor) -> None:
    with _lock:
        _bindings[id(queue)] = (weakref.ref(queue), weakref.ref(executor))


def executor_for(queue):
    """The live executor bound to exactly this queue object, or None."""
    with _lock:
        entry = _bindings.get(id(queue))
    if entry is None:
        return None
    q, ex = entry[0](), entry[1]()
    return ex if q is queue else None
