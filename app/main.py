

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError

app = FastAPI(
    title="Vetty Cryptocurrency API",
    description="Authenticated API proxy for Canadian-dollar cryptocurrency market data.",
)

@app.get("/health")
async def health_check():
    return {
        "message": "Hello World",
        "status": "success"
    }

