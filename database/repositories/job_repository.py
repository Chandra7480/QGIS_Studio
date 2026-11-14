"""Repository for jobs and job_events."""

from ..db import Database
from core.exceptions import DatabaseError, NotFoundError


class JobRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, job: dict) -> None:
        self.db.execute(
            """
            INSERT INTO jobs(id, type, status, agent_id, tool_id, request_id,
                             input_payload, output_payload, verification_state,
                             started_at, completed_at, error_message)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["id"], job["type"], job.get("status", "queued"),
                job.get("agent_id"), job.get("tool_id"), job.get("request_id"),
                job.get("input_payload"), job.get("output_payload"),
                job.get("verification_state"),
                job.get("started_at"), job.get("completed_at"),
                job.get("error_message"),
            ),
        )

    def get(self, job_id: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return dict(row) if row else None

    def update_status(self, job_id: str, status: str, error_message: str | None = None) -> None:
        self.db.execute(
            "UPDATE jobs SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, job_id),
        )

    def set_output(self, job_id: str, output_payload: str, verification_state: str) -> None:
        self.db.execute(
            "UPDATE jobs SET output_payload = ?, verification_state = ?, status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (output_payload, verification_state, job_id),
        )

    def cancel(self, job_id: str) -> None:
        self.db.execute(
            "UPDATE jobs SET status = 'cancelled', completed_at = datetime('now') WHERE id = ?",
            (job_id,),
        )

    def list(self, status: str | None = None, limit: int = 100) -> list:
        if status:
            rows = self.db.fetchall(
                "SELECT * FROM jobs WHERE status = ? ORDER BY started_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            rows = self.db.fetchall("SELECT * FROM jobs ORDER BY started_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def add_event(self, job_id: str, event_type: str, message: str) -> None:
        self.db.execute(
            "INSERT INTO job_events(job_id, event_type, message) VALUES(?, ?, ?)",
            (job_id, event_type, message),
        )

    def get_events(self, job_id: str) -> list:
        rows = self.db.fetchall(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY timestamp ASC", (job_id,)
        )
        return [dict(r) for r in rows]

    def update_progress(self, job_id: str, progress: int) -> None:
        """Update job progress (0-100). Stored as a progress event."""
        self.db.execute(
            "INSERT INTO job_events(job_id, event_type, message) VALUES(?, 'progress', ?)",
            (job_id, str(progress)),
        )

    def get_progress(self, job_id: str) -> int:
        """Get latest progress value for a job (0-100)."""
        row = self.db.fetchone(
            "SELECT message FROM job_events WHERE job_id = ? AND event_type = 'progress' ORDER BY timestamp DESC LIMIT 1",
            (job_id,),
        )
        if row and row["message"]:
            try:
                return int(row["message"])
            except ValueError:
                return 0
        return 0
