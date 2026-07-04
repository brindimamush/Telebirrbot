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