import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from celery.utils.log import get_task_logger
from sqlalchemy.future import select
from sqlalchemy import and_, cast, Date

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.security import create_verification_token
from app.models.merchant import Merchant
from app.models.verification import VerificationSession, SessionStatus
from app.models.settings import PlatformSettings

logger = get_task_logger(__name__)

def run_async_task(coro):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)

async def send_telegram_message(chat_id: int, text: str):
    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

@celery_app.task(name="tasks.send_monthly_renewal_requests")
def send_monthly_renewal_requests():
    """
    Scans for merchants whose subscriptions expire in 3 days.
    Generates a new payment session using current platform pricing and notifies them via Telegram.
    """
    async def _process_renewals():
        async with AsyncSessionLocal() as db:
            # Get current dynamic pricing
            config_query = await db.execute(select(PlatformSettings).where(PlatformSettings.id == 1))
            platform_config = config_query.scalar_one_or_none()
            
            if not platform_config:
                logger.error("Skipping renewals: PlatformConfig not found.")
                return

            target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
            
            # Find active merchants expiring in exactly 3 days
            m_query = await db.execute(
                select(Merchant).where(
                    Merchant.is_active == True,
                    cast(Merchant.subscription_expires_at, Date) == target_date
                )
            )
            expiring_merchants = m_query.scalars().all()

            for merchant in expiring_merchants:
                # Create a 3-day verification session for renewal
                expires_at = datetime.now(timezone.utc) + timedelta(days=3)
                session = VerificationSession(
                    merchant_id=1, 
                    expected_amount=platform_config.monthly_fee,
                    status=SessionStatus.PENDING,
                    expires_at=expires_at,
                    token="PENDING_GENERATION",
                    metadata_payload={"action": "renew_merchant", "target_merchant_id": merchant.id}
                )
                db.add(session)
                await db.flush()
                
                session.token = create_verification_token(str(session.id), platform_config.monthly_fee)
                await db.commit()

                # Dispatch Telegram Notification
                msg = (
                    f"⚠️ **Subscription Expiring Soon!**\n\n"
                    f"Hi {merchant.name}, your API access will expire on `{merchant.subscription_expires_at.strftime('%Y-%m-%d')}`.\n"
                    f"To avoid service interruption, please renew your subscription.\n\n"
                    f"👤 **Account Name:** `{platform_config.receiver_name}`\n"
                    f"💰 **Current Fee:** {platform_config.monthly_fee} ETB\n"
                    f"📱 **Send to:** `{platform_config.receiver_phone}`\n\n"
                    f"Verify your payment here:\n"
                    f"🔗 `[https://verify.yourdomain.com/pay/](https://verify.yourdomain.com/pay/){session.token}`"
                )
                await send_telegram_message(merchant.telegram_user_id, msg)
                logger.info(f"Sent renewal request to merchant {merchant.name} (ID: {merchant.id})")

    run_async_task(_process_renewals())