import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.settings import settings
from app.core.storage import ensure_bucket, upload_object
from app.db.models import ObservationModel

_CAPTURE_TOKEN_TTL = timedelta(hours=6)


class JourneyCaptureService:
    """Owns capture-token issuance (a stateless Fernet payload, no token table —
    planning/13-journey-capture.md) and the `observations`/voice-note upload for a
    captured human session. `participant_runs` itself stays owned by
    SimulationRunService, extended (not duplicated) for the human-run case."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def issue_capture_token(self, participant_run_id: uuid.UUID) -> str:
        payload = {
            "participant_run_id": str(participant_run_id),
            "exp": (datetime.now(UTC) + _CAPTURE_TOKEN_TTL).timestamp(),
        }
        return crypto.encrypt(json.dumps(payload))

    async def record_observation(
        self,
        participant_run_id: uuid.UUID,
        sequence_no: int,
        obs_type: str,
        screen_figma_node_id: str | None,
        element_figma_node_id: str | None,
        x: float | None,
        y: float | None,
        duration_ms: int | None,
        payload: dict | None,
    ) -> ObservationModel:
        observation = ObservationModel(
            participant_run_id=participant_run_id,
            sequence_no=sequence_no,
            type=obs_type,
            screen_figma_node_id=screen_figma_node_id,
            element_figma_node_id=element_figma_node_id,
            x=x,
            y=y,
            duration_ms=duration_ms,
            payload=payload,
        )
        self._session.add(observation)
        await self._session.flush()
        return observation

    async def upload_voice_note(
        self, participant_run_id: uuid.UUID, file_bytes: bytes, content_type: str
    ) -> str:
        # Same upload path as stimulus assets (app/services/stimulus_service.py),
        # into a voice-notes/ prefix of the same bucket.
        await ensure_bucket(settings.supabase_storage_bucket)
        return await upload_object(
            settings.supabase_storage_bucket,
            f"voice-notes/{participant_run_id}",
            file_bytes,
            content_type,
        )
