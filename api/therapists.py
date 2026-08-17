import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.main import get_active_therapists
from fastapi import FastAPI
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
    return await get_active_therapists()
