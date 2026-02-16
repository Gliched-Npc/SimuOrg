from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # <--- NEW IMPORT
from backend.api import sim_routes

app = FastAPI(title="SimuOrg API", version="1.0.0")

# --- NEW SECURITY SETTINGS (CORS) ---
# This tells the Backend: "It is safe to talk to the React App"
origins = [
    "http://localhost:5173",    # The address of your React App
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------------------

# Connect the routes
app.include_router(sim_routes.router, prefix="/api/sim", tags=["Simulation"])

@app.get("/")
def health_check():
    return {"status": "online", "message": "SimuOrg Engine is Running"}