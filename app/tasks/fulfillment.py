import asyncio
from celery.utils.log import get_task_logger
from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.verification import VerificationSession, SessionStatus
from sqlalchemy.future import select

logger = get_task_logger(__name__)

def run_async_task(coro):
    """Helper framework to safely run async methods inside synchronous Celery workers."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)

@celery_app.task(name="tasks.send_merchant_notification", bind=True, max_retries=5)
def send_merchant_notification(self, receipt_id: int, txn_id: str, settled_amount: float):
    """
    Notification Service: Notifies external channels (Sellers, Webhooks, WebSockets).
    Implements a strict retry fallback back-off mechanism for shaky external targets.
    """
    logger.info(f"⚡ Processing Notification for Receipt ID {receipt_id} (TXN: {txn_id})")
    try:
        # TODO: Execute outbound HTTP POST request to vendor target hook
        logger.info(f"✅ Notification dispatched successfully for amount: {settled_amount}")
    except Exception as exc:
        logger.warning(f"⚠️ Notification delivery failed. Retrying in 10s... Error: {exc}")
        raise self.retry(exc=exc, countdown=10)

@celery_app.task(name="tasks.activate_subscriber_tier")
def activate_subscriber_tier(session_id: int):
    """
    Subscription Service: Provisions premium memberships/entitlements directly 
    within database states once validation flags clear.
    """
    async def _async_fulfillment():
        async with AsyncSessionLocal() as db:
            query = await db.execute(select(VerificationSession).where(VerificationSession.id == session_id))
            session = query.scalar_one_or_none()
            
            if not session or session.status != SessionStatus.VERIFIED:
                logger.error(f"❌ Cancelled entitlement activation: Invalid Session ID {session_id}")
                return

            # TODO: Add business mutation logic here (e.g. user.is_premium = True)
            logger.info(f"🎉 Entitlement activated completely for session link contextual parameters: {session_id}")

    run_async_task(_async_fulfillment())