from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import llm_routes, ml_routes, sim_routes, upload_routes
from backend.config import logger, settings
from backend.db.database import init_db

# Initialize Sentry for crash reporting
if settings.sentry_dsn_backend:
    sentry_sdk.init(
        dsn=settings.sentry_dsn_backend,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=settings.environment,
    )
    logger.info("✅ Sentry Alerting Initialized for Backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Database...")
    init_db()
    logger.info("✅ Database Initialized")
    yield


app = FastAPI(title="SimuOrg API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8000",
        "https://simu-org.vercel.app",
    ],
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
