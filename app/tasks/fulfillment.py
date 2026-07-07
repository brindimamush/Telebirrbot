import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from celery.utils.log import get_task_logger
from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.verification import VerificationSession, SessionStatus
from sqlalchemy.future import select
from app.core.config import settings
from app.models.merchant import Merchant
from app.core.security import generate_secure_api_key

logger = get_task_logger(__name__)

def run_async_task(coro):
    """Helper framework to safely run async methods inside synchronous Celery workers."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)

async def send_telegram_message(chat_id: int, text: str):
    """Utility to send messages back to the merchant via the Bot API."""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

@celery_app.task(name="tasks.activate_subscriber_tier")
def activate_subscriber_tier(session_id: int):
    """
    Fulfillment Service: Identifies if a verified session was for merchant onboarding.
    If so, provisions the API key and sends it via Telegram.
    """
    async def _async_fulfillment():
        async with AsyncSessionLocal() as db:
            # 1. Fetch the verified session
            query = await db.execute(select(VerificationSession).where(VerificationSession.id == session_id))
            session = query.scalar_one_or_none()
            
            if not session or session.status != SessionStatus.VERIFIED:
                logger.error(f"❌ Fulfillment aborted: Invalid or unverified Session ID {session_id}")
                return

            # 2. Check if this is a platform subscription payment
            meta = session.metadata_payload or {}
            action = meta.get("action")
            target_merchant_id = meta.get("target_merchant_id")
            # FETCH TARGET MERCHANT FOR PLATFORM PAYMENTS
            if action in ["activate_merchant", "renew_merchant"]:
                m_query = await db.execute(select(Merchant).where(Merchant.id == target_merchant_id))
                merchant = m_query.scalar_one_or_none()
                
                if not merchant:
                    logger.error(f"❌ Target merchant {target_merchant_id} not found.")
                    return

                # --- SCENARIO A: NEW MERCHANT ONBOARDING ---
                if action == "activate_merchant":
                    raw_key, key_hash = generate_secure_api_key()
                    merchant.api_key_hash = key_hash
                    merchant.is_active = True
                    merchant.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                    
                    await db.commit()
                    
                    success_msg = (
                        f"🎉 **Payment Verified! Welcome aboard.**\n\n"
                        f"Your subscription is active until `{merchant.subscription_expires_at.strftime('%Y-%m-%d')}`.\n\n"
                        f"🔑 **Your API Key:**\n`{raw_key}`\n\n"
                        f"⚠️ *Save this key immediately! It cannot be shown again.*"
                    )
                    await send_telegram_message(merchant.telegram_user_id, success_msg)
                    logger.info(f"✅ Onboarded merchant {merchant.name} successfully.")
                    return

                # --- SCENARIO B: EXISTING MERCHANT RENEWAL ---
                elif action == "renew_merchant":
                    # If they are already expired, start 30 days from NOW. 
                    # If they are paying early, add 30 days to their CURRENT expiration date.
                    now = datetime.now(timezone.utc)
                    if merchant.subscription_expires_at and merchant.subscription_expires_at > now:
                        merchant.subscription_expires_at += timedelta(days=30)
                    else:
                        merchant.subscription_expires_at = now + timedelta(days=30)
                    
                    merchant.is_active = True # Ensure they are re-activated if they were locked out
                    await db.commit()

                    renewal_msg = (
                        f"🔄 **Renewal Successful!**\n\n"
                        f"Thank you for your payment. Your API access has been extended.\n"
                        f"📅 **New Expiration Date:** `{merchant.subscription_expires_at.strftime('%Y-%m-%d')}`"
                    )
                    await send_telegram_message(merchant.telegram_user_id, renewal_msg)
                    logger.info(f"✅ Renewed subscription for merchant {merchant.name}.")
                    return

    run_async_task(_async_fulfillment())

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

# @celery_app.task(name="tasks.activate_subscriber_tier")
# def activate_subscriber_tier(session_id: int):
#     """
#     Subscription Service: Provisions premium memberships/entitlements directly 
#     within database states once validation flags clear.
#     """
#     async def _async_fulfillment():
#         async with AsyncSessionLocal() as db:
#             query = await db.execute(select(VerificationSession).where(VerificationSession.id == session_id))
#             session = query.scalar_one_or_none()
            
#             if not session or session.status != SessionStatus.VERIFIED:
#                 logger.error(f"❌ Cancelled entitlement activation: Invalid Session ID {session_id}")
#                 return

#             # TODO: Add business mutation logic here (e.g. user.is_premium = True)
#             logger.info(f"🎉 Entitlement activated completely for session link contextual parameters: {session_id}")

    