"""Universal AI GIS Studio — Job Manager.

Manages the lifecycle of long-running jobs: creation, status updates,
cancellation, events, and persistence via JobRepository.
Integrates with resource quota management for per-job limits.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from core.logging import get_logger
from core.exceptions import NotFoundError, ExecutionError
from database.repositories.job_repository import JobRepository
from core.emergency_stop import EmergencyStop
from core.resource_quota import get_resource_quota_manager, ResourceQuota, QuotaExceededAction
from core.event_bus import EventBus

logger = get_logger("job_manager")


class JobManager:
    def __init__(self, db, default_quota: ResourceQuota | None = None):
        self.repo = JobRepository(db)
        self._quota_manager = get_resource_quota_manager()
        self._quota_manager.set_kill_callback(self._kill_job_for_quota)
        self._default_quota = default_quota or ResourceQuota()
        self._event_bus = EventBus()
        self._register_emergency_stop()

    def _kill_job_for_quota(self, job_id: str) -> None:
        """Callback to kill a job that exceeded its quota."""
        try:
            job = self.repo.get(job_id)
            if job and job["status"] == "running":
                self.fail_job(job_id, "QUOTA_EXCEEDED: Resource limit exceeded")
                logger.error("Job %s killed due to quota exceeded", job_id)
        except Exception as exc:
            logger.error("Failed to kill job %s for quota: %s", job_id, exc)

    def _register_emergency_stop(self):
        """Register emergency stop callback."""
        try:
            emergency_stop = EmergencyStop()
            emergency_stop.register(
                name="job_manager",
                callback=self._emergency_stop_callback,
                priority=100,  # High priority - stop jobs first
                description="Cancel all running and queued jobs"
            )
        except Exception as exc:
            logger.warning("Failed to register emergency stop for job manager: %s", exc)

    def _emergency_stop_callback(self):
        """Emergency stop callback - cancel all jobs."""
        logger.warning("JobManager emergency stop triggered - cancelling all jobs")
        self.cancel_all_jobs()

    def cancel_all_jobs(self) -> Dict[str, Any]:
        """Cancel all running and queued jobs."""
        try:
            jobs = self.repo.list(status=None, limit=1000)
            cancelled = 0
            failed = 0
            for job in jobs:
                if job["status"] in ("queued", "running"):
                    try:
                        self.cancel_job(job["id"])
                        cancelled += 1
                    except Exception as exc:
                        logger.error("Failed to cancel job %s: %s", job["id"], exc)
                        failed += 1
            logger.info("Emergency stop: cancelled %d jobs, %d failed", cancelled, failed)
            return {"cancelled": cancelled, "failed": failed}
        except Exception as exc:
            logger.exception("cancel_all_jobs failed: %s", exc)
            return {"cancelled": 0, "failed": 0, "error": str(exc)}

    def create_job(self, job_type: str, input_payload: str = "{}",
                   agent_id: str | None = None, tool_id: str | None = None,
                   request_id: str | None = None,
                   quota: ResourceQuota | None = None) -> str:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        job = {
            "id": job_id,
            "type": job_type,
            "status": "queued",
            "agent_id": agent_id,
            "tool_id": tool_id,
            "request_id": request_id,
            "input_payload": input_payload,
            "output_payload": None,
            "verification_state": None,
            "started_at": None,
            "completed_at": None,
            "error_message": None,
        }
        self.repo.create(job)
        self.repo.add_event(job_id, "created", f"Job {job_type} created")
        
        # Set up resource quota tracking
        effective_quota = quota or self._default_quota
        self._quota_manager.set_quota(job_id, effective_quota)
        
        # Publish EventBus event
        self._event_bus.publish("job.created", {"job_id": job_id, "job_type": job_type, "agent_id": agent_id})
        
        logger.info("Job created: %s (%s)", job_id, job_type)
        return job_id

    def start_job(self, job_id: str) -> None:
        job = self.repo.get(job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        now = datetime.utcnow().isoformat()
        self.db().execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
            (now, job_id),
        )
        self.repo.add_event(job_id, "started", "Job started")
        
        # Start resource tracking
        quota = self._quota_manager.get_quota(job_id)
        self._quota_manager.start_tracking(job_id, quota)
        
        # Publish EventBus event
        self._event_bus.publish("job.started", {"job_id": job_id})
        
        logger.info("Job started: %s", job_id)

    def complete_job(self, job_id: str, output_payload: str,
                     verification_state: str = "SUCCESS") -> None:
        job = self.repo.get(job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        self.repo.set_output(job_id, output_payload, verification_state)
        self.repo.add_event(job_id, "completed", f"Job completed (verification: {verification_state})")
        
        # Stop resource tracking
        usage = self._quota_manager.stop_tracking(job_id)
        if usage:
            logger.info("Job %s completed - peak memory: %.1f MB, CPU: %.1f s, duration: %.1f s",
                        job_id, usage.peak_memory_mb, usage.peak_cpu_seconds, usage.duration_seconds)
        
        # Publish EventBus event
        self._event_bus.publish("job.completed", {"job_id": job_id, "verification_state": verification_state})
        
        logger.info("Job completed: %s (verification=%s)", job_id, verification_state)

    def fail_job(self, job_id: str, error_message: str) -> None:
        job = self.repo.get(job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        now = datetime.utcnow().isoformat()
        self.db().execute(
            "UPDATE jobs SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?",
            (error_message, now, job_id),
        )
        self.repo.add_event(job_id, "failed", error_message)
        
        # Stop resource tracking
        usage = self._quota_manager.stop_tracking(job_id)
        if usage:
            logger.info("Job %s failed - peak memory: %.1f MB, CPU: %.1f s, duration: %.1f s",
                        job_id, usage.peak_memory_mb, usage.peak_cpu_seconds, usage.duration_seconds)
        
        # Publish EventBus event
        self._event_bus.publish("job.failed", {"job_id": job_id, "error": error_message})
        
        logger.error("Job failed: %s — %s", job_id, error_message)

    def cancel_job(self, job_id: str) -> None:
        job = self.repo.get(job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        self.repo.cancel(job_id)
        self.repo.add_event(job_id, "cancelled", "Job cancelled")
        
        # Stop resource tracking
        usage = self._quota_manager.stop_tracking(job_id)
        if usage:
            logger.info("Job %s cancelled - peak memory: %.1f MB, CPU: %.1f s, duration: %.1f s",
                        job_id, usage.peak_memory_mb, usage.peak_cpu_seconds, usage.duration_seconds)
        
        # Publish EventBus event
        self._event_bus.publish("job.cancelled", {"job_id": job_id})
        
        logger.info("Job cancelled: %s", job_id)

    def get_job(self, job_id: str) -> dict:
        job = self.repo.get(job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found")
        job["events"] = self.repo.get_events(job_id)
        return job

    def list_jobs(self, status: str | None = None, limit: int = 100) -> list:
        return self.repo.list(status=status, limit=limit)

    def db(self):
        return self.repo.db
