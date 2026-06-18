from sqlmodel import create_engine, Session
from sqlalchemy import text

DATABASE_URL = "postgresql://postgres:root@localhost:5432/helpdesk"

engine = create_engine(DATABASE_URL, echo=True)

def init_db():
    with engine.connect() as conn:
        conn.execute(
            text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        conn.commit()
    print("pgvector extension ready")

def get_session():
    with Session(engine) as session:
        yield session
