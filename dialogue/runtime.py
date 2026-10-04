"""
runtime.py — STUDENT B OWNS THIS FILE. Which executor serves which queue.

main.py creates the chat thread and the executor separately, both around one
CommandQueue, and only passes the queue to the chat thread. The executor
binds itself to its queue here, so the chat thread can reach it for the stop
fast path (and, from step 4, the robot state) without changing main.py.
Weak references: an executor that is gone (e.g. after a test) is never used.

It also tags queued commands with the utterance they came from (one
utterance = one [EXEC]...[DONE] batch). CommandQueue (core/schema.py) is
frozen, so the tag is an attribute on each command instance: push_utterance()
sets it, utterance_of() reads it. Commands pushed with plain
queue.push_many() are untagged; the executor drains contiguous untagged
commands as one batch, as before.
"""

import itertools
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


_UTTERANCE_ATTR = "_utterance"     # (utterance id, number of commands)
_utterance_ids = itertools.count(1)


def push_utterance(queue, commands) -> int:
    """Queue the commands of ONE parsed utterance, each tagged with a fresh
    utterance id and the utterance's size. Returns the id."""
    commands = list(commands)
    uid = next(_utterance_ids)
    for c in commands:
        setattr(c, _UTTERANCE_ATTR, (uid, len(commands)))
    queue.push_many(commands)
    return uid


def utterance_of(cmd):
    """(utterance id, size) set by push_utterance(), or None if untagged."""
    return getattr(cmd, _UTTERANCE_ATTR, None)
