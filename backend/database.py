from sqlmodel import SQLModel, create_engine, Session

# Hardcoded for simplicity right now - we will use .env later
DATABASE_URL = "postgresql://user:password@localhost:5435/simuorg_db"

engine = create_engine(DATABASE_URL)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    """Provide DB session"""
    with Session(engine) as session:
        yield session