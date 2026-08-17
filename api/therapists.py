import sys
import os
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/therapists")
@app.get("/")
async def handler():
    try:
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from app.main import get_active_therapists
        return await get_active_therapists()
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e), "traceback": traceback.format_exc()}, status_code=200)
