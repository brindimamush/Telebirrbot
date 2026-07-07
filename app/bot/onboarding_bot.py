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