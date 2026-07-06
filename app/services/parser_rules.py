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