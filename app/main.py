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