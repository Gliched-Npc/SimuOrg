from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import sim_routes, upload_routes, ml_routes, llm_routes
from backend.db.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="SimuOrg API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sim_routes.router)
app.include_router(upload_routes.router)
app.include_router(ml_routes.router)
app.include_router(llm_routes.router)

@app.get("/")
def health_check():
    return {"status": "online", "message": "SimuOrg Engine is Running"}