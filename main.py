from __future__ import annotations

from typing import Optional

import requests
from bs4 import BeautifulSoup


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

        It searches for the invoice header row, then reads the next row.
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
            "payer_name": self._find_value(
                soup,
                "Payer Name"
            ),
            "credited_party_name": self._find_value(
                soup,
                "Credited Party name"
            ),
            "credited_party_account": self._find_value(
                soup,
                "Credited party account no"
            ),
            "transaction_status": self._find_value(
                soup,
                "transaction status"
            ),
            "invoice_no": invoice["invoice_no"],
            "payment_date": invoice["payment_date"],
            "settled_amount": invoice["settled_amount"],
            "total_paid_amount": self._find_value(
                soup,
                "Total Paid Amount"
            ),
        }


if __name__ == "__main__":

    parser = TelebirrReceiptParser()

    # ----------------------------
    # OPTION 1 - Parse local HTML
    # # ----------------------------
    # with open("telebirr receipt.html", "r", encoding="utf-8") as f:
    #     html = f.read()

    # data = parser.parse(html)

    # print(data)

    # ----------------------------
    # OPTION 2 - Parse from URL
    # ----------------------------
    
    url = "https://transactioninfo.ethiotelecom.et/receipt/DFM46L0Z6Q"
    html = parser.download_receipt(url)
    data = parser.parse(html)
    print(data)