# -*- coding: utf-8 -*-
from __future__ import annotations

import gc
import sys
import tempfile
import threading
import traceback
from pathlib import Path

LOG = Path("xp_writer_diagnostic.log")
CALLERS = {}
TRACKERS = {}

def emit(label, payload):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(label + " " + repr(payload) + "\n")
    print("XPDIAG " + label + " " + repr(payload), file=sys.stderr, flush=True)

def snapshot(label, nodeid=""):
    threads = list(threading.enumerate())
    writers = [t for t in threads if t.name == "nakama-xp-writer"]
    states = []
    for t in writers:
        states.append({
            "thread_id": id(t),
            "ident": t.ident,
            "native_id": getattr(t, "native_id", None),
            "alive": t.is_alive(),
            "daemon": t.daemon,
            "tracker": TRACKERS.get(id(t)),
            "caller": CALLERS.get(id(t)),
        })
    emit("SNAPSHOT", {
        "label": label,
        "nodeid": nodeid,
        "threads": len(threads),
        "writers": len(writers),
        "non_daemon": sum(not t.daemon for t in threads),
        "limbo": [(id(t), t.name, t.is_alive()) for t in getattr(threading, "_limbo", {}).values()],
        "dangling_writers": [
            (id(t), t.ident, t.name, t.is_alive())
            for t in getattr(threading, "_dangling", ())
            if t.name == "nakama-xp-writer"
        ],
        "writers_state": states,
        "tempdirs": [
            getattr(o, "name", repr(o))
            for o in gc.get_objects()
            if isinstance(o, tempfile.TemporaryDirectory)
        ],
    })

def patch():
    from bot_ia.interfaces import xp_audit
    original_init = xp_audit.PassiveXPTracker.__init__
    original_stop = xp_audit.PassiveXPTracker.stop
    original_start = threading.Thread.start

    def init(self, *args, **kwargs):
        caller = "".join(traceback.format_stack(limit=16))
        result = original_init(self, *args, **kwargs)
        thread = getattr(self, "_thread", None)
        if thread is not None:
            TRACKERS[id(thread)] = {
                "tracker_id": id(self),
                "path": str(getattr(self, "path", "")),
                "created_by": caller,
            }
            CALLERS[id(thread)] = caller
        emit("TRACKER_CREATE", {
            "tracker": id(self),
            "thread": id(thread) if thread is not None else None,
            "path": str(getattr(self, "path", "")),
        })
        return result

    def stop(self, *args, **kwargs):
        thread = getattr(self, "_thread", None)
        emit("TRACKER_STOP_BEGIN", {
            "tracker": id(self),
            "thread": id(thread) if thread is not None else None,
            "alive": thread.is_alive() if thread is not None else False,
        })
        result = original_stop(self, *args, **kwargs)
        emit("TRACKER_STOP_END", {
            "tracker": id(self),
            "thread": id(thread) if thread is not None else None,
            "alive": thread.is_alive() if thread is not None else False,
        })
        return result

    def start(self, *args, **kwargs):
        if self.name == "nakama-xp-writer":
            CALLERS[id(self)] = "".join(traceback.format_stack(limit=16))
            emit("THREAD_START", {
                "thread": id(self),
                "caller": CALLERS[id(self)],
            })
        return original_start(self, *args, **kwargs)

    xp_audit.PassiveXPTracker.__init__ = init
    xp_audit.PassiveXPTracker.stop = stop
    threading.Thread.start = start

def pytest_sessionstart(session):
    LOG.write_text("", encoding="utf-8")
    patch()
    snapshot("session_start")

def pytest_runtest_teardown(item, nextitem):
    snapshot("after_test", item.nodeid)

def pytest_keyboard_interrupt(excinfo):
    snapshot("keyboard")
    import faulthandler
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)

def pytest_unconfigure(config):
    snapshot("unconfigure")
