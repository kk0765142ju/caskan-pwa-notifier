import sys
import os
import traceback
from fastapi import FastAPI, Query
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

@app.get("/api/therapist/data")
@app.get("/")
async def handler(name: str = Query("森永ここあ")):
    try:
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from app.main import get_therapist_data
        return await get_therapist_data(name)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e), "traceback": traceback.format_exc()}, status_code=200)
