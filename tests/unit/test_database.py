"""Unit tests for Stage 2 Database layer."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from database.schema import initialize
from database.repositories.job_repository import JobRepository


def _tmp_db():
    path = os.path.join(tempfile.gettempdir(), f"uagis_test_{os.getpid()}.db")
    return path


def test_database_init_and_settings():
    path = _tmp_db()
    try:
        db = Database(path)
        initialize(db)
        db.set_setting("k1", "v1")
        assert db.get_all_settings().get("k1") == "v1"
        db.close()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_job_repository_crud():
    path = _tmp_db()
    db = None
    try:
        db = Database(path)
        initialize(db)
        repo = JobRepository(db)
        job_id = "job_test_1"
        repo.create({"id": job_id, "type": "test", "status": "queued",
                     "input_payload": "{}"})
        job = repo.get(job_id)
        assert job is not None
        assert job["status"] == "queued"
        repo.update_status(job_id, "running")
        job = repo.get(job_id)
        assert job["status"] == "running"
        repo.add_event(job_id, "started", "started")
        events = repo.get_events(job_id)
        assert len(events) == 1
        repo.set_output(job_id, '{"ok": true}', "SUCCESS")
        job = repo.get(job_id)
        assert job["status"] == "completed"
        assert job["verification_state"] == "SUCCESS"
        jobs = repo.list()
        assert len(jobs) == 1
    finally:
        if db is not None:
            db.close()
        if os.path.exists(path):
            os.remove(path)


def test_job_not_found():
    path = _tmp_db()
    db = None
    try:
        db = Database(path)
        initialize(db)
        repo = JobRepository(db)
        assert repo.get("nope") is None
    finally:
        if db is not None:
            db.close()
        if os.path.exists(path):
            os.remove(path)
