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
@app.get("/therapists")
@app.get("/")
async def get_therapists_debug():
    try:
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from app.main import get_active_therapists
        res = await get_active_therapists()
        return res
    except Exception as e:
        err_msg = traceback.format_exc()
        return JSONResponse({"status": "error", "message": str(e), "traceback": err_msg}, status_code=200)

@app.get("/api/therapist/data")
@app.get("/therapist/data")
async def get_therapist_data_debug(name: str = "森永ここあ"):
    try:
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from app.main import get_therapist_data
        res = await get_therapist_data(name)
        return res
    except Exception as e:
        err_msg = traceback.format_exc()
        return JSONResponse({"status": "error", "message": str(e), "traceback": err_msg}, status_code=200)
