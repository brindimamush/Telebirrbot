from fastapi import FastAPI
from app.services.parser_rules import router as parser_router
from app.services.verification import router as verification_router
from app.services.validation import router as validation_router

app = FastAPI(title="Payment Verification Platform Gateway", version="1.0.0")

# Mount downstream services dynamically
app.include_router(verification_router, prefix="/api/v1")
app.include_router(parser_router, prefix="/api/v1")
app.include_router(validation_router, prefix="/api/v1")

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "API Gateway"}