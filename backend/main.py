from fastapi import FastAPI
from backend.api import sim_routes

app = FastAPI(title="SimuOrg API", version="1.0.0")

# Connect the routes
app.include_router(sim_routes.router, prefix="/api/sim", tags=["Simulation"])

@app.get("/")
def health_check():
    return {"status": "online", "message": "SimuOrg Engine is Running"}