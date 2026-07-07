import asyncio
from datetime import datetime, timezone
from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.verification import VerificationSession, SessionStatus
from app.models.audit import AuditLog
from sqlalchemy.future import select
from sqlalchemy import update

logger = get_task_logger(__name__)

def run_async_job(coro):
    """Executes asynchronous database routines synchronously inside workers."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)

@celery_app.task(name="tasks.session_expiration_worker")
def session_expiration_worker():
    """
    Periodic cleanup loop that invalidates stale verification sessions.
    Transitions expired 'pending' states to 'expired' and writes to the audit trail.
    """
    async def _sweep_expired_sessions():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            
            # Find candidate IDs for target transition to inject clean audit events later
            query_stmt = select(VerificationSession.id).where(
                VerificationSession.status == SessionStatus.PENDING,
                VerificationSession.expires_at < now
            )
            result = await db.execute(query_stmt)
            expired_ids = result.scalars().all()
            
            if not expired_ids:
                logger.info("🧹 Session sweep finished: 0 stale sessions discovered.")
                return

            # Perform high-performance batch updates
            update_stmt = (
                update(VerificationSession)
                .where(VerificationSession.id.in_(expired_ids))
                .values(status=SessionStatus.EXPIRED)
            )
            await db.execute(update_stmt)
            
            # Populate immutable records tracking system automation changes
            for sid in expired_ids:
                audit = AuditLog(
                    action="SESSION_AUTO_EXPIRED",
                    entity_name="VerificationSession",
                    entity_id=str(sid),
                    payload={"reason": "Expiration timestamp passed without confirmation."}
                )
                db.add(audit)
                
            await db.commit()
            logger.info(f"💥 Successfully invalidated {len(expired_ids)} unfulfilled verification sessions.")

    run_async_job(_sweep_expired_sessions())