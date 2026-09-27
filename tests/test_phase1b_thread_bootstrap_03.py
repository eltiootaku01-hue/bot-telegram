# -*- coding: utf-8 -*-
"""Phase 1B Experiment 03: worker lifecycle with SQLite."""

from __future__ import annotations

import os
import platform
import sqlite3
import sys
import tempfile
from threading import Event, Thread


def test_thread_sqlite_lifecycle():
    print(f"PYTHON_VERSION={sys.version}")
    print(f"PLATFORM={platform.platform()}")

    with tempfile.TemporaryDirectory(prefix="phase1b-sqlite-") as directory:
        database = os.path.join(directory, "worker.sqlite3")
        stop = Event()
        state = {"entered": False, "written": False}

        def worker():
            state["entered"] = True
            connection = sqlite3.connect(database, timeout=2.0)
            try:
                connection.execute("CREATE TABLE IF NOT EXISTS events (value TEXT NOT NULL)")
                connection.execute("INSERT INTO events(value) VALUES ('started')")
                connection.commit()
                state["written"] = True
                stop.wait()
            finally:
                connection.close()

        thread = Thread(target=worker, name="phase1b-sqlite-thread", daemon=True)
        thread.start()
        assert thread.is_alive() is True

        stop.set()
        thread.join()
        assert state["entered"] is True
        assert state["written"] is True
        assert thread.is_alive() is False

        connection = sqlite3.connect(database)
        try:
            row = connection.execute("SELECT COUNT(*) FROM events").fetchone()
        finally:
            connection.close()
        assert row == (1,)
