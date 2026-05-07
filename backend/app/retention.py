from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from .database import SessionLocal
from .models import GenerationTrace


def delete_old_generation_traces(days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
    with SessionLocal() as db:
        result = db.execute(delete(GenerationTrace).where(GenerationTrace.created_at < cutoff))
        db.commit()
        return int(result.rowcount or 0)
