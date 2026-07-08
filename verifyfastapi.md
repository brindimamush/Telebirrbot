This file is a merged representation of the entire codebase, combined into a single document by Repomix.

# File Summary

## Purpose
This file contains a packed representation of the entire repository's contents.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
```
app/
  bot/
    onboarding_bot.py
  core/
    celery_app.py
    config.py
    database.py
    security.py
  models/
    audit.py
    merchant.py
    settings.py
    transaction.py
    verification.py
  services/
    audit.py
    notification.py
    parser_rules.py
    subscription.py
    validation.py
    verification.py
  tasks/
    billing.py
    cleanup.py
    fulfillment.py
    renewal.py
  __init__.py
  main.py
migrations/
  versions/
    9e223f9df818_make_merchant_api_key_hash_nullable.py
    b12f37aea71b_initial_tables.py
    d829cb5d2c39_added_new_merchantand_settings_model_.py
  env.py
  README
  script.py.mako
.gitignore
alembic.ini
docker-compose.yml
old.py
production.dockerfile
requirements.txt
```

# Files

## File: app/bot/onboarding_bot.py
```python
import os
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.settings import PlatformSettings
from app.models.merchant import Merchant
from app.models.verification import VerificationSession, SessionStatus
from app.core.security import create_verification_token

# Conversation states
ASK_NAME, ASK_PHONE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the onboarding conversation."""
    await update.message.reply_text(
        "👋 Welcome to the Payment Verification Platform!\n\n"
        "I will automate your payment verifications. To get your API key, you need an active subscription.\n\n"
        "First, what is the name of your business/store?"
    )
    return ASK_NAME

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['merchant_name'] = update.message.text
    await update.message.reply_text(
        f"Great name! Now, please reply with the **Phone Number** (e.g., 0911...) that buyers will send money to.",
        parse_mode="Markdown"
    )
    return ASK_PHONE

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text
    name = context.user_data['merchant_name']
    telegram_id = update.effective_user.id

    msg = await update.message.reply_text("🔄 Setting up your account and fetching current platform pricing...")

    async with AsyncSessionLocal() as db:
        # 1. Fetch live platform settings
        settings_query = await db.execute(select(PlatformSettings).where(PlatformSettings.id == 1))
        platform_config = settings_query.scalar_one_or_none()
        
        if not platform_config:
            await msg.edit_text("⚠️ System configuration error: Platform settings not initialized.")
            return ConversationHandler.END

        # 2. Create the pending merchant
        new_merchant = Merchant(
            name=name,
            telegram_user_id=telegram_id,
            payment_phone=phone,
            is_active=False
        )
        db.add(new_merchant)
        await db.flush()

        # 3. Create a Verification Session for the dynamic Monthly Fee
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
        
        session = VerificationSession(
            merchant_id=1, # The platform's master merchant account
            expected_amount=platform_config.monthly_fee,
            status=SessionStatus.PENDING,
            expires_at=expires_at,
            token="PENDING_GENERATION",
            metadata_payload={
                "action": "activate_merchant",
                "target_merchant_id": new_merchant.id
            }
        )
        db.add(session)
        await db.flush()

        session.token = create_verification_token(str(session.id), platform_config.monthly_fee)
        await db.commit()

        # 4. Provide instructions using the live database details
        await msg.edit_text(
            f"✅ **Account Created (Pending Activation)**\n\n"
            f"To activate your API key, please pay the monthly platform fee.\n\n"
            f"💰 **Amount:** `{platform_config.monthly_fee}` ETB\n"
            f"👤 **Receiver Name:** `{platform_config.receiver_name}`\n"
            f"📱 **Send to:** `{platform_config.receiver_phone}`\n\n"
            f"After paying,\n"
            f"🔗 [Verify your payment here](https://verify.yourdomain.com/pay/{session.token})",
            parse_mode="Markdown"
        )

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Registration cancelled. Type /start to try again.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(conv_handler)
    print("🤖 Onboarding Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
```

## File: app/core/database.py
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Create the async PostgreSQL engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

async def get_db() -> AsyncSession:
    """Dependency for providing database sessions to FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session
```

## File: app/models/audit.py
```python
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import Base

class AuditLog(Base):
    """Immutable audit logs for all system actions."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True, nullable=False)  # e.g., "SESSION_CREATED", "RECEIPT_VERIFIED"
    entity_name = Column(String, nullable=False)         # e.g., "TransactionReceipt"
    entity_id = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)              # Stores the exact state/data 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

## File: app/models/merchant.py
```python
from sqlalchemy import Column, String, Integer, Boolean, DateTime, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Merchant(Base):
    """Represents a business entity authorized to manage verification sessions."""
    __tablename__ = "merchants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    #fields for automated Telegram onboarding
    telegram_user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    payment_phone = Column(String, nullable=False)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    # Store hashes of API keys in the database, never the raw values
    api_key_hash = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship linking back to sessions owned by this merchant
    sessions = relationship("VerificationSession", back_populates="merchant", cascade="all, delete-orphan")
```

## File: app/models/settings.py
```python
from sqlalchemy import Column, String, Float, DateTime, Integer
from sqlalchemy.sql import func
from app.core.database import Base

class PlatformSettings(Base):
    """Dynamic configuration for platform monetization."""
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, index=True)
    monthly_fee = Column(Float, nullable=False, default=150.00)
    receiver_phone = Column(String, nullable=False)
    receiver_name = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

## File: app/models/transaction.py
```python
from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class TransactionReceipt(Base):
    __tablename__ = "transaction_receipts"

    id = Column(Integer, primary_key=True, index=True)
    # Unique index enforces idempotency - a transaction ID can only be verified once
    txn_id = Column(String, unique=True, index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("verification_sessions.id"), nullable=False)
    
    payer_name = Column(String, nullable=True)
    credited_party_account = Column(String, nullable=True)
    settled_amount = Column(Float, nullable=False)
    transaction_status = Column(String, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

## File: app/services/audit.py
```python

```

## File: app/services/notification.py
```python

```

## File: app/services/parser_rules.py
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/parser", tags=["Parser Rules"])

class ParserRuleResponse(BaseModel):
    provider: str
    version: int
    target_url_template: str
    selectors: dict[str, str]

# Mocking a DB or Redis lookup for current active rules
CURRENT_RULES = {
    "telebirr": {
        "provider": "telebirr",
        "version": 1,
        "target_url_template": "https://transactioninfo.ethiotelecom.et/receipt/{txn_id}",
        "selectors": {
            "payer_name": ".payer-info .name", # CSS Selectors or regex patterns
            "credited_party_name": ".merchant-info .title",
            "credited_party_account": ".merchant-info .account",
            "invoice_no": "#invoice-id",
            "payment_date": ".timestamp",
            "settled_amount": ".amount .value",
            "transaction_status": ".status-badge"
        }
    }
}

@router.get("/rules/{provider}", response_model=ParserRuleResponse)
async def get_parser_rules(provider: str):
    """Flutter calls this to know HOW to parse the receipt HTML locally."""
    rule = CURRENT_RULES.get(provider.lower())
    if not rule:
        raise HTTPException(status_code=404, detail="Payment provider rules not found")
    return rule
```

## File: app/services/subscription.py
```python

```

## File: app/tasks/billing.py
```python
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
```

## File: app/tasks/cleanup.py
```python
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
```

## File: app/tasks/renewal.py
```python
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from celery.utils.log import get_task_logger
from sqlalchemy.future import select
from sqlalchemy import cast, Date

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.security import create_verification_token
from app.models.merchant import Merchant
from app.models.verification import VerificationSession, SessionStatus
from app.models.settings import PlatformSettings

logger = get_task_logger(__name__)

def run_async_task(coro):
    """Safely bridges asynchronous DB calls into the synchronous Celery worker context."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        return asyncio.ensure_future(coro)
    return loop.run_until_complete(coro)

async def send_telegram_message(chat_id: int, text: str):
    """Sends messages via the platform's Telegram Bot."""
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

@celery_app.task(name="tasks.send_monthly_renewal_requests")
def send_monthly_renewal_requests():
    """
    Daily task: Scans for subscriptions expiring in exactly 3 days.
    Generates a dynamically priced payment session and alerts the merchant.
    """
    async def _process_renewals():
        async with AsyncSessionLocal() as db:
            # 1. Get current dynamic pricing
            config_query = await db.execute(select(PlatformSettings).where(PlatformSettings.id == 1))
            platform_config = config_query.scalar_one_or_none()
            
            if not platform_config:
                logger.error("❌ Skipping renewals: PlatformSettings not found in database.")
                return

            target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
            
            # 2. Find active merchants expiring in exactly 3 days
            m_query = await db.execute(
                select(Merchant).where(
                    Merchant.is_active == True,
                    cast(Merchant.subscription_expires_at, Date) == target_date
                )
            )
            expiring_merchants = m_query.scalars().all()

            if not expiring_merchants:
                logger.info("ℹ️ No subscriptions expiring in 3 days. Renewal sweep complete.")
                return

            # 3. Process each expiring merchant
            for merchant in expiring_merchants:
                expires_at = datetime.now(timezone.utc) + timedelta(days=3)
                
                session = VerificationSession(
                    merchant_id=1, # Paid to the Platform Master Merchant account
                    expected_amount=platform_config.monthly_fee,
                    status=SessionStatus.PENDING,
                    expires_at=expires_at,
                    token="PENDING_GENERATION",
                    metadata_payload={"action": "renew_merchant", "target_merchant_id": merchant.id}
                )
                db.add(session)
                await db.flush()
                
                # Generate cryptographic verification token
                session.token = create_verification_token(str(session.id), platform_config.monthly_fee)
                await db.commit()

                # 4. Dispatch Telegram Notification
                msg = (
                    f"⚠️ **Subscription Expiring Soon!**\n\n"
                    f"Hi {merchant.name}, your verification API access will expire on `{merchant.subscription_expires_at.strftime('%Y-%m-%d')}`.\n"
                    f"To avoid service interruption, please renew your subscription.\n\n"
                    f"👤 **Account Name:** `{platform_config.receiver_name}`\n"
                    f"💰 **Current Fee:** {platform_config.monthly_fee} ETB\n"
                    f"📱 **Send to:** `{platform_config.receiver_phone}`\n\n"
                    f"Verify your payment here:\n"
                    f"🔗 `https://verify.yourdomain.com/pay/{session.token}`"
                )
                await send_telegram_message(merchant.telegram_user_id, msg)
                logger.info(f"✅ Sent renewal request to merchant {merchant.name} (ID: {merchant.id})")

    run_async_task(_process_renewals())
```

## File: app/__init__.py
```python

```

## File: migrations/versions/9e223f9df818_make_merchant_api_key_hash_nullable.py
```python
"""make merchant api_key_hash nullable

Revision ID: 9e223f9df818
Revises: d829cb5d2c39
Create Date: 2026-07-07 22:57:35.913778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e223f9df818'
down_revision: Union[str, Sequence[str], None] = 'd829cb5d2c39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('merchants', 'api_key_hash',
               existing_type=sa.VARCHAR(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('merchants', 'api_key_hash',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###
```

## File: migrations/versions/b12f37aea71b_initial_tables.py
```python
"""Initial tables

Revision ID: b12f37aea71b
Revises: 
Create Date: 2026-07-06 15:12:32.496008

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b12f37aea71b'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('entity_name', sa.String(), nullable=False),
    sa.Column('entity_id', sa.String(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_table('verification_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('expected_amount', sa.Float(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'VERIFIED', 'FAILED', 'EXPIRED', name='sessionstatus'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_sessions_id'), 'verification_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_verification_sessions_token'), 'verification_sessions', ['token'], unique=True)
    op.create_table('transaction_receipts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('txn_id', sa.String(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('payer_name', sa.String(), nullable=True),
    sa.Column('credited_party_account', sa.String(), nullable=True),
    sa.Column('settled_amount', sa.Float(), nullable=False),
    sa.Column('transaction_status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['verification_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_receipts_id'), 'transaction_receipts', ['id'], unique=False)
    op.create_index(op.f('ix_transaction_receipts_txn_id'), 'transaction_receipts', ['txn_id'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_transaction_receipts_txn_id'), table_name='transaction_receipts')
    op.drop_index(op.f('ix_transaction_receipts_id'), table_name='transaction_receipts')
    op.drop_table('transaction_receipts')
    op.drop_index(op.f('ix_verification_sessions_token'), table_name='verification_sessions')
    op.drop_index(op.f('ix_verification_sessions_id'), table_name='verification_sessions')
    op.drop_table('verification_sessions')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')
    # ### end Alembic commands ###
```

## File: migrations/versions/d829cb5d2c39_added_new_merchantand_settings_model_.py
```python
"""added new merchantand settings model modified verification model

Revision ID: d829cb5d2c39
Revises: b12f37aea71b
Create Date: 2026-07-07 22:00:33.291416

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd829cb5d2c39'
down_revision: Union[str, Sequence[str], None] = 'b12f37aea71b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('merchants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('telegram_user_id', sa.BigInteger(), nullable=False),
    sa.Column('payment_phone', sa.String(), nullable=False),
    sa.Column('subscription_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('api_key_hash', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_merchants_api_key_hash'), 'merchants', ['api_key_hash'], unique=True)
    op.create_index(op.f('ix_merchants_id'), 'merchants', ['id'], unique=False)
    op.create_index(op.f('ix_merchants_name'), 'merchants', ['name'], unique=False)
    op.create_index(op.f('ix_merchants_telegram_user_id'), 'merchants', ['telegram_user_id'], unique=True)
    op.create_table('platform_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('monthly_fee', sa.Float(), nullable=False),
    sa.Column('receiver_phone', sa.String(), nullable=False),
    sa.Column('receiver_name', sa.String(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_platform_settings_id'), 'platform_settings', ['id'], unique=False)
    op.add_column('verification_sessions', sa.Column('merchant_id', sa.Integer(), nullable=False))
    op.add_column('verification_sessions', sa.Column('metadata_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key(None, 'verification_sessions', 'merchants', ['merchant_id'], ['id'], ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'verification_sessions', type_='foreignkey')
    op.drop_column('verification_sessions', 'metadata_payload')
    op.drop_column('verification_sessions', 'merchant_id')
    op.drop_index(op.f('ix_platform_settings_id'), table_name='platform_settings')
    op.drop_table('platform_settings')
    op.drop_index(op.f('ix_merchants_telegram_user_id'), table_name='merchants')
    op.drop_index(op.f('ix_merchants_name'), table_name='merchants')
    op.drop_index(op.f('ix_merchants_id'), table_name='merchants')
    op.drop_index(op.f('ix_merchants_api_key_hash'), table_name='merchants')
    op.drop_table('merchants')
    # ### end Alembic commands ###
```

## File: migrations/README
```
Generic single-database configuration with an async dbapi.
```

## File: migrations/script.py.mako
```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
```

## File: alembic.ini
```ini
# A generic, single database configuration.

[alembic]
# path to migration scripts.
# this is typically a path given in POSIX (e.g. forward slashes)
# format, relative to the token %(here)s which refers to the location of this
# ini file
script_location = %(here)s/migrations

# template used to generate migration file names; The default value is %%(rev)s_%%(slug)s
# Uncomment the line below if you want the files to be prepended with date and time
# see https://alembic.sqlalchemy.org/en/latest/tutorial.html#editing-the-ini-file
# for all available tokens
# file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s
# Or organize into date-based subdirectories (requires recursive_version_locations = true)
# file_template = %%(year)d/%%(month).2d/%%(day).2d_%%(hour).2d%%(minute).2d_%%(second).2d_%%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
# defaults to the current working directory.  for multiple paths, the path separator
# is defined by "path_separator" below.
prepend_sys_path = .

# timezone to use when rendering the date within the migration file
# as well as the filename.
# If specified, requires the tzdata library which can be installed by adding
# `alembic[tz]` to the pip requirements.
# string value is passed to ZoneInfo()
# leave blank for localtime
# timezone =

# max length of characters to apply to the "slug" field
# truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# version location specification; This defaults
# to <script_location>/versions.  When using multiple version
# directories, initial revisions must be specified with --version-path.
# The path separator used here should be the separator specified by "path_separator"
# below.
# version_locations = %(here)s/bar:%(here)s/bat:%(here)s/alembic/versions

# path_separator; This indicates what character is used to split lists of file
# paths, including version_locations and prepend_sys_path within configparser
# files such as alembic.ini.
# The default rendered in new alembic.ini files is "os", which uses os.pathsep
# to provide os-dependent path splitting.
#
# Note that in order to support legacy alembic.ini files, this default does NOT
# take place if path_separator is not present in alembic.ini.  If this
# option is omitted entirely, fallback logic is as follows:
#
# 1. Parsing of the version_locations option falls back to using the legacy
#    "version_path_separator" key, which if absent then falls back to the legacy
#    behavior of splitting on spaces and/or commas.
# 2. Parsing of the prepend_sys_path option falls back to the legacy
#    behavior of splitting on spaces, commas, or colons.
#
# Valid values for path_separator are:
#
# path_separator = :
# path_separator = ;
# path_separator = space
# path_separator = newline
#
# Use os.pathsep. Default configuration used for new projects.
path_separator = os


# set to 'true' to search source files recursively
# in each "version_locations" directory
# new in Alembic version 1.10
# recursive_version_locations = false

# the output encoding used when revision files
# are written from script.py.mako
# output_encoding = utf-8

# database URL.  This is consumed by the user-maintained env.py script only.
# other means of configuring database URLs may be customized within the env.py
# file.
sqlalchemy.url = driver://user:pass@localhost/dbname


[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.  See the documentation for further
# detail and examples

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# lint with attempts to fix using "ruff" - use the module runner, against the "ruff" module
# hooks = ruff
# ruff.type = module
# ruff.module = ruff
# ruff.options = check --fix REVISION_SCRIPT_FILENAME

# Alternatively, use the exec runner to execute a binary found on your PATH
# hooks = ruff
# ruff.type = exec
# ruff.executable = ruff
# ruff.options = check --fix REVISION_SCRIPT_FILENAME

# Logging configuration.  This is also consumed by the user-maintained
# env.py script only.
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

## File: docker-compose.yml
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: pvp_postgres
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: verifier
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    container_name: pvp_redis
    ports:
      - "6379:6379"

  api_gateway:
    build: .
    container_name: pvp_api_gateway
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    volumes:
      - .:/workspace
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/verifier
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  celery_worker:
    build: .
    container_name: pvp_celery_worker
    command: celery -A app.core.celery_app worker --loglevel=info
    volumes:
      - .:/workspace
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/verifier
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres

volumes:
  pgdata:
```

## File: old.py
```python
from __future__ import annotations

import asyncio
import os
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables from .env file
load_dotenv()


class TelebirrReceiptParser:
    """
    Production-ready parser for Telebirr HTML receipts.
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def download_receipt(self, url: str) -> str:
        """
        Download receipt HTML from URL.
        """
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _clean(text: str) -> str:
        return " ".join(text.split())

    def _find_value(self, soup: BeautifulSoup, keyword: str) -> Optional[str]:
        """
        Generic label -> value parser.
        Works for fields outside the invoice table.
        """
        keyword = keyword.lower()

        for td in soup.find_all("td"):
            text = self._clean(td.get_text(" ", strip=True)).lower()

            if keyword in text:
                next_td = td.find_next_sibling("td")

                if next_td:
                    return self._clean(next_td.get_text(" ", strip=True))

        return None

    def _invoice_details(self, soup: BeautifulSoup) -> dict:
        """
        Extract invoice number, payment date and settled amount.
        """
        rows = soup.find_all("tr")

        for i, row in enumerate(rows):
            cells = [
                self._clean(td.get_text(" ", strip=True))
                for td in row.find_all("td")
            ]

            if len(cells) != 3:
                continue

            if (
                "Invoice No" in cells[0]
                and "Payment date" in cells[1]
                and "Settled Amount" in cells[2]
            ):

                if i + 1 >= len(rows):
                    break

                value_cells = [
                    self._clean(td.get_text(" ", strip=True))
                    for td in rows[i + 1].find_all("td")
                ]

                if len(value_cells) == 3:
                    return {
                        "invoice_no": value_cells[0],
                        "payment_date": value_cells[1],
                        "settled_amount": value_cells[2],
                    }

        return {
            "invoice_no": None,
            "payment_date": None,
            "settled_amount": None,
        }

    def parse(self, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        invoice = self._invoice_details(soup)

        return {
            "payer_name": self._find_value(soup, "Payer Name"),
            "credited_party_name": self._find_value(soup, "Credited Party name"),
            "credited_party_account": self._find_value(soup, "Credited party account no"),
            "transaction_status": self._find_value(soup, "transaction status"),
            "invoice_no": invoice["invoice_no"],
            "payment_date": invoice["payment_date"],
            "settled_amount": invoice["settled_amount"],
            "total_paid_amount": self._find_value(soup, "Total Paid Amount"),
        }


# Global instance of the parser
parser = TelebirrReceiptParser()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcoming message when the user types /start."""
    await update.message.reply_text(
        "👋 Welcome! Send me a Telebirr **Transaction ID**, and I will fetch and extract the receipt details for you."
    )


async def handle_receipt_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processes the text input, capitalizes it, strips spaces, and replies with data."""
    raw_text = update.message.text

    # "".join(text.split()) safely breaks on any spacing/newlines and rejoins without spaces.
    # .upper() ensures the code remains capitalised regardless of user entry pattern.
    txn_id = "".join(raw_text.split()).upper()

    if not txn_id:
        await update.message.reply_text("❌ Please send a valid Transaction ID.")
        return

    # Notify the user that the background extraction workflow has initialized
    status_msg = await update.message.reply_text(f"🔄 Fetching and parsing Telebirr receipt for: <code>{txn_id}</code>...", parse_mode="HTML")

    try:
        url = f"https://transactioninfo.ethiotelecom.et/receipt/{txn_id}"

        # Maintain thread safety for synchronous operations
        html = await asyncio.to_thread(parser.download_receipt, url)
        data = await asyncio.to_thread(parser.parse, html)

        # Build clean output visualization using safe HTML templates
        response_template = (
            f"<b>🧾 Telebirr Receipt Details</b>\n\n"
            f"🆔 <b>Transaction ID:</b> <code>{txn_id}</code>\n"
            f"👤 <b>Payer:</b> {data['payer_name'] or 'N/A'}\n"
            f"🏢 <b>Credited Party:</b> {data['credited_party_name'] or 'N/A'}\n"
            f"💳 <b>Account No:</b> {data['credited_party_account'] or 'N/A'}\n"
            f"🆔 <b>Invoice No:</b> {data['invoice_no'] or 'N/A'}\n"
            f"📅 <b>Payment Date:</b> {data['payment_date'] or 'N/A'}\n"
            f"💰 <b>Settled Amount:</b> {data['settled_amount'] or 'N/A'}\n"
            f"💵 <b>Total Paid:</b> {data['total_paid_amount'] or 'N/A'}\n"
            f"⚡ <b>Status:</b> {data['transaction_status'] or 'N/A'}"
        )

        await status_msg.edit_text(response_template, parse_mode="HTML")

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else "Unknown"
        await status_msg.edit_text(
            f"❌ <b>Failed to get receipt for {txn_id}.</b>\n"
            f"The Transaction ID might be incorrect, or the Ethio Telecom server rejected the request (Status: {status_code}).",
            parse_mode="HTML"
        )
    except Exception as e:
        await status_msg.edit_text(f"⚠️ An unexpected error occurred: {str(e)}")


def main() -> None:
    """Start the bot engine."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable not found in .env file.")
        return

    app = Application.builder().token(bot_token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_receipt_request))

    print("🤖 Telebirr Receipt Bot is running... Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
```

## File: production.dockerfile
```dockerfile
FROM python:3.13-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
```

## File: app/core/celery_app.py
```python
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "payment_verification_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # Explicitly load fulfillment modules
    include=["app.tasks.fulfillment", "app.tasks.cleanup", "app.tasks.billing", "app.tasks.renewal",  ],
)

celery_app.conf.beat_schedule = {
    "expire-sessions-every-60-seconds": {
        "task": "tasks.session_expiration_worker",
        "schedule": 60.0,
    },
}

# Optimize configuration for stateless APIs
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1, # Enforces strict load-balancing across worker threads
    task_acks_late=True           # Ensure tasks are re-queued if a worker crashes mid-execution
)
```

## File: app/core/config.py
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    PROJECT_NAME: str = "Payment Verification Platform"
    SECRET_KEY: str = "super-secret-jwt-key-change-in-production"
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/verifier"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## File: app/models/verification.py
```python
from sqlalchemy import Column, String, Float, DateTime, Enum, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum
from app.core.database import Base

class SessionStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class VerificationSession(Base):
    __tablename__ = "verification_sessions"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    # The signed verification token, indexed for fast lookup from Flutter
    token = Column(String, unique=True, index=True, nullable=False)
    expected_amount = Column(Float, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="sessions")
    # Stores context, e.g., {"action": "platform_subscription", "target_merchant_id": 123}
    metadata_payload = Column(JSONB, nullable=True)
```

## File: app/tasks/fulfillment.py
```python
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
```

## File: migrations/env.py
```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.

# migrations/env.py


# 1. Import your settings and models
from app.core.config import settings
from app.core.database import Base
from app.models.verification import VerificationSession
from app.models.transaction import TransactionReceipt
from app.models.audit import AuditLog
from app.models.merchant import Merchant
from app.models.settings import PlatformSettings

config = context.config
# 2. Set the target metadata
target_metadata = Base.metadata

# ... (keep the rest of the generated env.py file, but ensure the sqlalchemy.url is set)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)





# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## File: .gitignore
```
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[codz]
*$py.class

# C extensions
*.so

#repomix
repomix-output.md

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
#   Usually these files are written by a python script from a template
#   before PyInstaller builds the exe, so as to inject date/other infos into it.
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py.cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
#   For a library or package, you might want to ignore these files since the code is
#   intended to run in multiple environments; otherwise, check them in:
# .python-version

# pipenv
#   According to pypa/pipenv#598, it is recommended to include Pipfile.lock in version control.
#   However, in case of collaboration, if having platform-specific dependencies or dependencies
#   having no cross-platform support, pipenv may install dependencies that don't work, or not
#   install all needed dependencies.
# Pipfile.lock

# UV
#   Similar to Pipfile.lock, it is generally recommended to include uv.lock in version control.
#   This is especially recommended for binary packages to ensure reproducibility, and is more
#   commonly ignored for libraries.
# uv.lock

# poetry
#   Similar to Pipfile.lock, it is generally recommended to include poetry.lock in version control.
#   This is especially recommended for binary packages to ensure reproducibility, and is more
#   commonly ignored for libraries.
#   https://python-poetry.org/docs/basic-usage/#commit-your-poetrylock-file-to-version-control
# poetry.lock
# poetry.toml

# pdm
#   Similar to Pipfile.lock, it is generally recommended to include pdm.lock in version control.
#   pdm recommends including project-wide configuration in pdm.toml, but excluding .pdm-python.
#   https://pdm-project.org/en/latest/usage/project/#working-with-version-control
# pdm.lock
# pdm.toml
.pdm-python
.pdm-build/

# pixi
#   Similar to Pipfile.lock, it is generally recommended to include pixi.lock in version control.
# pixi.lock
#   Pixi creates a virtual environment in the .pixi directory, just like venv module creates one
#   in the .venv directory. It is recommended not to include this directory in version control.
.pixi

# PEP 582; used by e.g. github.com/David-OConnor/pyflow and github.com/pdm-project/pdm
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# Redis
*.rdb
*.aof
*.pid

# RabbitMQ
mnesia/
rabbitmq/
rabbitmq-data/

# ActiveMQ
activemq-data/

# SageMath parsed files
*.sage.py

# Environments
.env
.envrc
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# PyCharm
#   JetBrains specific template is maintained in a separate JetBrains.gitignore that can
#   be found at https://github.com/github/gitignore/blob/main/Global/JetBrains.gitignore
#   and can be added to the global gitignore or merged into this file.  For a more nuclear
#   option (not recommended) you can uncomment the following to ignore the entire idea folder.
# .idea/

# Abstra
#   Abstra is an AI-powered process automation framework.
#   Ignore directories containing user credentials, local state, and settings.
#   Learn more at https://abstra.io/docs
.abstra/

# Visual Studio Code
#   Visual Studio Code specific template is maintained in a separate VisualStudioCode.gitignore 
#   that can be found at https://github.com/github/gitignore/blob/main/Global/VisualStudioCode.gitignore
#   and can be added to the global gitignore or merged into this file. However, if you prefer, 
#   you could uncomment the following to ignore the entire vscode folder
# .vscode/
# Temporary file for partial code execution
tempCodeRunnerFile.py

# Ruff stuff:
.ruff_cache/

# PyPI configuration file
.pypirc

# Marimo
marimo/_static/
marimo/_lsp/
__marimo__/

# Streamlit
.streamlit/secrets.toml
```

## File: app/core/security.py
```python
from datetime import datetime, timedelta, timezone
import jwt
import secrets
import hashlib
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from app.core.database import get_db
from app.models.merchant import Merchant

# Setup secure header parsing for API keys
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)

def generate_secure_api_key() -> tuple[str, str]:
    """
    Generates a raw secure API key for the merchant and its SHA-256 storage hash.
    Returns: (raw_key, key_hash)
    """
    raw_key = f"pvp_live_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash

async def verify_merchant_api_key(
    api_key: str = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db)
) -> Merchant:
    """
    Dependency injector to enforce API key matching for programmatic merchant access.
    Hashes incoming keys and checks them against the immutable storage records.
    """
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    result = await db.execute(
        select(Merchant).where(
            Merchant.api_key_hash == api_key_hash,
            Merchant.is_active == True
        )
    )
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid or inactive API Key provider credentials."
        )
    return merchant

def create_verification_token(session_id: str, expected_amount: float) -> str:
    """Creates a signed JWT containing session requirements."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=15) # Configurable expiration
    to_encode = {
        "sub": session_id,
        "exp": expire,
        "amt": expected_amount,
        "type": "verification_session"
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

security_scheme = HTTPBearer()

async def verify_merchant_auth(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    """
    Secures upstream administrative endpoints (like session generation).
    Expects a valid Bearer token in the HTTP Authorization header.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "merchant_access":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token scope. Access denied."
            )
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

## File: app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.parser_rules import router as parser_router
from app.services.verification import router as verification_router
from app.services.validation import router as validation_router

app = FastAPI(title="Payment Verification Platform Gateway", version="1.0.0")

origins = [
    "http://localhost",
    "http://localhost:8080", # Common Flutter web local dev ports
    "*"                      # Replace with your actual frontend domain name in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mount downstream services dynamically
app.include_router(verification_router, prefix="/api/v1")
app.include_router(parser_router, prefix="/api/v1")
app.include_router(validation_router, prefix="/api/v1")

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "API Gateway"}
```

## File: app/services/validation.py
```python
import jwt
from fastapi import APIRouter, HTTPException, Depends,status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone

from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.core.database import get_db
from app.models.verification import VerificationSession, SessionStatus
from app.models.transaction import TransactionReceipt
from app.models.audit import AuditLog

from app.tasks.fulfillment import send_merchant_notification, activate_subscriber_tier

router = APIRouter(prefix="/validation", tags=["Validation Engine"])

class ReceiptSubmission(BaseModel):
    token: str
    txn_id: str
    payer_name: str
    credited_party_name: str
    credited_party_account: str
    settled_amount: float
    transaction_status: str

    @field_validator("txn_id")
    @classmethod
    def clean_transaction_id(cls, v: str) -> str:
        """Sanitizes transaction IDs matching your existing strip pattern."""
        if not v or not "".join(v.split()):
            raise ValueError("Invalid Transaction ID structure.")
        return "".join(v.split()).upper()

@router.post("/verify-receipt")
async def verify_receipt(payload: ReceiptSubmission, db: AsyncSession = Depends(get_db)):
    """
    Step 6 of Production Flow: Validates extracted data against cryptographic session claims.
    Enforces transaction idempotency across the platform.
    """
    # 1. Decode and verify the cryptographic integrity of the incoming token
    try:
        decoded_token = jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        session_id = int(decoded_token.get("sub"))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or tampered verification token.")

    # 2. Check strict transaction idempotency (Has this Telebirr TXNID been used before?)
    existing_txn = await db.execute(select(TransactionReceipt).where(TransactionReceipt.txn_id == payload.txn_id))
    if existing_txn.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This Transaction ID has already been verified.")

    # 3. Retrieve the localized verification session and check its validity state
    session_query = await db.execute(select(VerificationSession).where(VerificationSession.id == session_id))
    session: VerificationSession = session_query.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification session context missing.")
    if session.status != SessionStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Session cannot be verified. Current status: {session.status}")
    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        session.status = SessionStatus.EXPIRED
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification session has expired.")

    # 4. Cross-verify parsed values against actual financial contract terms
    if abs(payload.settled_amount - session.expected_amount) > 0.01:
        session.status = SessionStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Paid amount does not match expected session amount.")
        
    if payload.transaction_status.upper() != "SUCCESSFUL":
        session.status = SessionStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Receipt status indicates an incomplete transaction.")

    # 5. Success State: Commit the transaction receipt to the log and close out the session
    session.status = SessionStatus.VERIFIED
    
    receipt = TransactionReceipt(
        txn_id=payload.txn_id,
        session_id=session.id,
        payer_name=payload.payer_name,
        credited_party_account=payload.credited_party_account,
        settled_amount=payload.settled_amount,
        transaction_status=payload.transaction_status
    )
    db.add(receipt)
    await db.flush() # Acquire receipt ID
    
    # 6. Build the immutable audit payload
    audit = AuditLog(
        action="RECEIPT_VERIFIED",
        entity_name="TransactionReceipt",
        entity_id=str(receipt.id),
        payload={
            "txn_id": payload.txn_id,
            "session_id": session.id,
            "settled_amount": payload.settled_amount
        }
    )
    db.add(audit)
    await db.commit()
    # =========================================================================
    # Step 7 of Production Flow: Offload execution tasks to the background queue
    # =========================================================================
    send_merchant_notification.delay(
        receipt_id=receipt.id,
        txn_id=payload.txn_id,
        settled_amount=payload.settled_amount
    )
    
    activate_subscriber_tier.delay(
        session_id=session.id
    )

    # 7. Return success context to Flutter client
    return {
        "status": "success",
        "message": f"Transaction {payload.txn_id} verified successfully.",
        "session_status": session.status
    }
```

## File: app/services/verification.py
```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.security import create_verification_token, verify_merchant_api_key
from app.models.verification import VerificationSession, SessionStatus
from app.models.audit import AuditLog
from app.models.merchant import Merchant


router = APIRouter(prefix="/sessions", tags=["Verification Sessions"])

class CreateSessionRequest(BaseModel):
    expected_amount: float = Field(..., gt=0.0, description="The precise amount to pass verification.")
    expiration_minutes: int = Field(default=15, ge=5, le=1440)

class SessionResponse(BaseModel):
    session_id: int
    merchant_id: int
    token: str
    expires_at: datetime
    status: SessionStatus
    expected_amount: float

    class Config:
        from_attributes = True

class SessionPaginatedHistory(BaseModel):
    total_records: int
    page: int
    limit: int
    data: list[SessionResponse]

# --- API Routes ---

@router.post("/create", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    merchant: Merchant = Depends(verify_merchant_api_key)
):
    """Creates a cryptographic verification context owned implicitly by the calling merchant."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=request.expiration_minutes)
    
    new_session = VerificationSession(
        merchant_id=merchant.id,
        expected_amount=request.expected_amount,
        status=SessionStatus.PENDING,
        expires_at=expires_at,
        token="PENDING_GENERATION"
    )
    db.add(new_session)
    await db.flush()
    
    generated_token = create_verification_token(
        session_id=str(new_session.id), 
        expected_amount=request.expected_amount
    )
    new_session.token = generated_token
    
    audit = AuditLog(
        action="SESSION_CREATED",
        entity_name="VerificationSession",
        entity_id=str(new_session.id),
        payload={
            "merchant_id": merchant.id,
            "expected_amount": request.expected_amount, 
            "expires_at": expires_at.isoformat()
        }
    )
    db.add(audit)
    await db.commit()
    await db.refresh(new_session)
    return new_session


@router.get("/lookup/{session_id}", response_model=SessionResponse)
async def lookup_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    merchant: Merchant = Depends(verify_merchant_api_key)
):
    """Retrieves context for a single verification session while asserting strict merchant ownership."""
    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.merchant_id == merchant.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification session records not found.")
    return session


@router.post("/cancel/{session_id}", response_model=SessionResponse)
async def cancel_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    merchant: Merchant = Depends(verify_merchant_api_key)
):
    """Terminates a pending verification session manually, neutralizing downstream link validations."""
    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.merchant_id == merchant.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification session context missing.")
    if session.status != SessionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Only PENDING sessions can be cancelled. Current status is: {session.status}"
        )
        
    session.status = SessionStatus.CANCELLED
    
    audit = AuditLog(
        action="SESSION_CANCELLED",
        entity_name="VerificationSession",
        entity_id=str(session.id),
        payload={"merchant_id": merchant.id, "cancelled_at": datetime.now(timezone.utc).isoformat()}
    )
    db.add(audit)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/history", response_model=SessionPaginatedHistory)
async def get_session_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: SessionStatus = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    merchant: Merchant = Depends(verify_merchant_api_key)
):
    """Returns a cursor-paginated, filterable historical record list of sessions owned by the merchant."""
    offset = (page - 1) * limit
    
    # Assemble structured conditional statements dynamically
    base_stmt = select(VerificationSession).where(VerificationSession.merchant_id == merchant.id)
    if status_filter:
        base_stmt = base_stmt.where(VerificationSession.status == status_filter)
        
    # Query exact total matching count 
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_count_res = await db.execute(count_stmt)
    total_records = total_count_res.scalar_one()
    
    # Query data payload slice sorted chronologically
    data_stmt = base_stmt.order_by(VerificationSession.created_at.desc()).offset(offset).limit(limit)
    data_res = await db.execute(data_stmt)
    sessions = data_res.scalars().all()
    
    return {
        "total_records": total_records,
        "page": page,
        "limit": limit,
        "data": sessions
    }
```

## File: requirements.txt
```
# beautifulsoup4==4.13.5
# lxml==6.0.0
# requests==2.32.5
# python-telegram-bot==22.8
python-dotenv==1.0.1

# Core Web Framework
fastapi>=0.111.0
uvicorn[standard]>=0.30.0

# Configuration & Validation
pydantic>=2.7.0
pydantic-settings>=2.3.0

# Database & Migrations
sqlalchemy>=2.0.30
asyncpg>=0.29.0
alembic>=1.13.0

# Cache & Background Tasks
redis>=5.0.0
celery>=5.4.0

# Security & Authentication
pyjwt[crypto]>=2.8.0
passlib[bcrypt]>=1.7.4

# HTTP Client (for any external system sync/internal gateway routing)
httpx>=0.27.0
```
