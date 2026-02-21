from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env file")

engine = create_engine(DATABASE_UR,
pool_pre_ping=True,
connect_args={"check_same_thread":False} if sqlite in DATABASE_URL else {})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
# ```

# ---

# **Step 4 — Install python-dotenv if you haven't:**
# ```
# pip install python-dotenv